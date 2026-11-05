-- Camada de integracao do site em banco separado. Executar como administrador
-- depois de carregar o banco multiplikar. Senhas sao injetadas pelo setup.
CREATE DATABASE IF NOT EXISTS app CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE app;
CREATE USER IF NOT EXISTS 'app_definer'@'localhost' ACCOUNT LOCK;

CREATE TABLE IF NOT EXISTS registro_site (
    id_atendimento BIGINT PRIMARY KEY,
    formulario VARCHAR(20) NOT NULL CHECK (formulario IN ('ORCAMENTO','CONTATO')),
    recebido_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    aceite_termos BOOLEAN NOT NULL CHECK (aceite_termos = TRUE),
    dados_formulario JSON NOT NULL,
    CONSTRAINT fk_registro_site_atendimento FOREIGN KEY (id_atendimento)
        REFERENCES multiplikar.atendimento(id_atendimento)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS mensagem_contato (
    id_mensagem BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    recebida_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assunto VARCHAR(20) NOT NULL CHECK (assunto IN ('GARANTIA','OUTROS')),
    nome VARCHAR(100) NOT NULL CHECK (TRIM(nome) <> ''),
    documento VARCHAR(18) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL,
    cidade VARCHAR(80) NOT NULL,
    estado_uf CHAR(2) NOT NULL,
    mensagem VARCHAR(1000) NOT NULL CHECK (TRIM(mensagem) <> ''),
    preferencia_contato VARCHAR(20) NOT NULL,
    aceite_termos BOOLEAN NOT NULL CHECK (aceite_termos = TRUE),
    lida_em DATETIME NULL,
    id_funcionario_leitura BIGINT NULL,
    CONSTRAINT ck_mensagem_leitura CHECK ((lida_em IS NULL) = (id_funcionario_leitura IS NULL)),
    CONSTRAINT fk_mensagem_funcionario FOREIGN KEY (id_funcionario_leitura)
        REFERENCES multiplikar.funcionario(id_funcionario)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS veiculo_ofertado (
    id_oferta BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_atendimento BIGINT NOT NULL,
    id_veiculo BIGINT NOT NULL,
    recebido_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modalidade_pretendida VARCHAR(20) NOT NULL CHECK (modalidade_pretendida IN ('COMPRA_PROPRIA','CONSIGNACAO','TROCA')),
    quilometragem_informada INT NOT NULL CHECK (quilometragem_informada >= 0),
    proprietarios_informados INT NULL CHECK (proprietarios_informados >= 0),
    valor_pretendido DECIMAL(14,2) NULL CHECK (valor_pretendido >= 0),
    observacoes VARCHAR(500) NULL,
    CONSTRAINT fk_ofertado_atendimento FOREIGN KEY (id_atendimento) REFERENCES multiplikar.atendimento(id_atendimento),
    CONSTRAINT fk_ofertado_veiculo FOREIGN KEY (id_veiculo) REFERENCES multiplikar.veiculo(id_veiculo),
    INDEX ix_ofertado_veiculo (id_veiculo)
) ENGINE=InnoDB;

CREATE OR REPLACE VIEW vw_veiculo_situacao_publica AS
SELECT s.* FROM multiplikar.vw_veiculo_situacao s
WHERE NOT (s.situacao_atual = 'FORA_DO_ESTOQUE'
 AND EXISTS (SELECT 1 FROM veiculo_ofertado o WHERE o.id_veiculo=s.id_veiculo));

DROP PROCEDURE IF EXISTS exigir_lead_site;
DROP PROCEDURE IF EXISTS exigir_funcionario_ativo;
DROP PROCEDURE IF EXISTS cadastrar_lead;
DROP PROCEDURE IF EXISTS registrar_mensagem;
DROP PROCEDURE IF EXISTS revisar_lead;
DROP PROCEDURE IF EXISTS registrar_interacao;
DROP PROCEDURE IF EXISTS reclassificar_lead;
DROP PROCEDURE IF EXISTS registrar_desfecho;
DROP PROCEDURE IF EXISTS marcar_mensagem_lida;
DELIMITER $$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE exigir_lead_site(IN p_id_atendimento BIGINT)
SQL SECURITY DEFINER
BEGIN
 IF NOT EXISTS (SELECT 1 FROM app.registro_site WHERE id_atendimento=p_id_atendimento) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Lead da massa de demonstracao e somente leitura';
 END IF;
 IF EXISTS (SELECT 1 FROM multiplikar.atendimento_desfecho WHERE id_atendimento=p_id_atendimento) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Atendimento ja tem desfecho registrado';
 END IF;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE exigir_funcionario_ativo(IN p_id_funcionario BIGINT)
SQL SECURITY DEFINER
BEGIN
 IF NOT EXISTS (SELECT 1 FROM multiplikar.funcionario WHERE id_funcionario=p_id_funcionario AND situacao='ATIVO') THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Funcionario inexistente ou inativo';
 END IF;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE cadastrar_lead(IN p JSON, OUT p_id_atendimento BIGINT)
SQL SECURITY DEFINER
proc: BEGIN
 DECLARE v_doc VARCHAR(18); DECLARE v_tipo_doc VARCHAR(4); DECLARE v_pessoa BIGINT;
 DECLARE v_funcionario BIGINT; DECLARE v_atendimento BIGINT; DECLARE v_veiculo BIGINT;
 DECLARE v_entrada BIGINT; DECLARE v_classificacao BIGINT; DECLARE v_novo BOOLEAN DEFAULT FALSE;
 DECLARE v_placa VARCHAR(10); DECLARE v_obs VARCHAR(500); DECLARE v_marca VARCHAR(40);
 DECLARE v_modelo VARCHAR(60); DECLARE v_ano INT; DECLARE v_cor VARCHAR(30);
 DECLARE v_combustivel VARCHAR(30); DECLARE v_cambio VARCHAR(30); DECLARE v_modalidade VARCHAR(20);
 DECLARE v_agora DATETIME;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 SET v_agora=CURRENT_TIMESTAMP;
 SET v_doc=REGEXP_REPLACE(JSON_UNQUOTE(JSON_EXTRACT(p,'$.documento')),'[^0-9]','');
 SET v_tipo_doc=CASE CHAR_LENGTH(v_doc) WHEN 11 THEN 'CPF' WHEN 14 THEN 'CNPJ' END;
 IF v_tipo_doc IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Documento deve ter 11 (CPF) ou 14 (CNPJ) digitos'; END IF;
 INSERT INTO multiplikar.pessoa(nome,tipo_documento,numero_documento,telefone,email,logradouro,numero,complemento,bairro,cidade,estado_uf)
 VALUES(JSON_UNQUOTE(JSON_EXTRACT(p,'$.nome')),v_tipo_doc,v_doc,
        JSON_UNQUOTE(JSON_EXTRACT(p,'$.telefone')),LOWER(JSON_UNQUOTE(JSON_EXTRACT(p,'$.email'))),
        JSON_UNQUOTE(JSON_EXTRACT(p,'$.logradouro')),JSON_UNQUOTE(JSON_EXTRACT(p,'$.numero')),
        NULLIF(TRIM(JSON_UNQUOTE(JSON_EXTRACT(p,'$.complemento'))),''),
        JSON_UNQUOTE(JSON_EXTRACT(p,'$.bairro')),JSON_UNQUOTE(JSON_EXTRACT(p,'$.cidade')),
        UPPER(JSON_UNQUOTE(JSON_EXTRACT(p,'$.estado_uf'))))
 ON DUPLICATE KEY UPDATE id_pessoa=LAST_INSERT_ID(id_pessoa);
 SET v_pessoa=LAST_INSERT_ID();

 SET v_atendimento=COALESCE((SELECT a.id_atendimento FROM multiplikar.atendimento a
   JOIN app.registro_site r ON r.id_atendimento=a.id_atendimento
   JOIN multiplikar.pessoa pe ON pe.id_pessoa=a.id_pessoa
   WHERE a.id_pessoa=v_pessoa AND a.tipo_interesse=JSON_UNQUOTE(JSON_EXTRACT(p,'$.tipo_interesse'))
    AND a.descricao_interesse=JSON_UNQUOTE(JSON_EXTRACT(p,'$.descricao_interesse'))
    AND (pe.telefone=JSON_UNQUOTE(JSON_EXTRACT(p,'$.telefone')) OR LOWER(pe.email)=LOWER(JSON_UNQUOTE(JSON_EXTRACT(p,'$.email'))))
    AND a.situacao IN('ABERTO','EM_NEGOCIACAO')
    AND NOT EXISTS(SELECT 1 FROM multiplikar.atendimento_desfecho d WHERE d.id_atendimento=a.id_atendimento)
   ORDER BY a.data DESC LIMIT 1),0);
 IF v_atendimento>0 THEN
  SET v_funcionario=(SELECT id_funcionario FROM multiplikar.atendimento WHERE id_atendimento=v_atendimento);
  INSERT INTO multiplikar.interacao(id_atendimento,id_funcionario,data_hora,canal,direcao,resumo,proximo_passo,data_proximo_passo)
  VALUES(v_atendimento,v_funcionario,v_agora,'OUTRO','RECEBIDA',
   CONCAT('Novo envio pelo site: ',JSON_UNQUOTE(JSON_EXTRACT(p,'$.descricao_interesse')),'. ',JSON_UNQUOTE(JSON_EXTRACT(p,'$.resumo'))),
   CONCAT('Retornar o contato por ',JSON_UNQUOTE(JSON_EXTRACT(p,'$.preferencia_contato'))),DATE_ADD(v_agora,INTERVAL 1 DAY));
 ELSE
  SET v_funcionario=COALESCE((SELECT f.id_funcionario FROM multiplikar.funcionario f
   WHERE f.situacao='ATIVO' AND f.cargo='Vendas'
   ORDER BY (SELECT COUNT(*) FROM multiplikar.atendimento a WHERE a.id_funcionario=f.id_funcionario
      AND a.situacao IN('ABERTO','EM_NEGOCIACAO')
      AND NOT EXISTS(SELECT 1 FROM multiplikar.atendimento_desfecho d WHERE d.id_atendimento=a.id_atendimento)),f.id_funcionario LIMIT 1),0);
  IF v_funcionario=0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Nenhum vendedor ativo para receber o atendimento'; END IF;
  INSERT INTO multiplikar.atendimento(id_pessoa,id_funcionario,data,tipo_interesse,descricao_interesse,situacao,observacoes)
  VALUES(v_pessoa,v_funcionario,v_agora,JSON_UNQUOTE(JSON_EXTRACT(p,'$.tipo_interesse')),
   JSON_UNQUOTE(JSON_EXTRACT(p,'$.descricao_interesse')),'ABERTO',NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p,'$.observacoes')),''));
  SET v_atendimento=LAST_INSERT_ID();
  INSERT INTO multiplikar.interacao(id_atendimento,id_funcionario,data_hora,canal,direcao,resumo,proximo_passo,data_proximo_passo)
  VALUES(v_atendimento,v_funcionario,v_agora,'OUTRO','RECEBIDA',JSON_UNQUOTE(JSON_EXTRACT(p,'$.resumo')),
   CONCAT('Retornar o contato por ',JSON_UNQUOTE(JSON_EXTRACT(p,'$.preferencia_contato'))),DATE_ADD(v_agora,INTERVAL 1 DAY));
  SET v_novo=TRUE;
  INSERT INTO app.registro_site(id_atendimento,formulario,aceite_termos,dados_formulario)
  VALUES(v_atendimento,JSON_UNQUOTE(JSON_EXTRACT(p,'$.formulario')),
   JSON_UNQUOTE(JSON_EXTRACT(p,'$.aceite_termos')) IN ('true','1'),p);
 END IF;

 IF JSON_CONTAINS_PATH(p,'one','$.veiculo_cliente') THEN
  SET v_placa=NULLIF(UPPER(REGEXP_REPLACE(JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.placa')),'[^A-Za-z0-9]','')),'');
  SET v_obs='';
  IF v_placa IS NOT NULL AND EXISTS(SELECT 1 FROM multiplikar.veiculo WHERE placa=v_placa) THEN
   SET v_obs=CONCAT('Placa informada ',v_placa,' ja consta no cadastro; conferir na avaliacao. '); SET v_placa=NULL;
  END IF;
  SET v_marca=JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.marca'));
  SET v_modelo=JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.modelo'));
  SET v_ano=CAST(JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.ano_modelo')) AS UNSIGNED);
  SET v_cor=JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.cor'));
  SET v_combustivel=JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.combustivel'));
  SET v_cambio=JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.cambio'));
  SET v_modalidade=JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.modalidade'));
  INSERT INTO multiplikar.veiculo(marca,modelo,ano_modelo,cor,placa,combustivel,cambio,categoria_comercial)
  VALUES(v_marca,v_modelo,v_ano,v_cor,v_placa,v_combustivel,v_cambio,IF(v_ano>=2023,'SEMINOVO','USADO'));
  SET v_veiculo=LAST_INSERT_ID();
  INSERT INTO app.veiculo_ofertado(id_atendimento,id_veiculo,modalidade_pretendida,quilometragem_informada,proprietarios_informados,valor_pretendido,observacoes)
  VALUES(v_atendimento,v_veiculo,v_modalidade,CAST(JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.quilometragem')) AS UNSIGNED),
   CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.proprietarios')),'null') AS UNSIGNED),
   CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.valor_pretendido')),'null') AS DECIMAL(14,2)),
   NULLIF(CONCAT(v_obs,COALESCE(JSON_UNQUOTE(JSON_EXTRACT(p,'$.veiculo_cliente.observacoes')),'')),''));
 END IF;

 IF JSON_CONTAINS_PATH(p,'one','$.intencao') THEN
  SET v_entrada=(SELECT e.id_entrada FROM multiplikar.entrada e
   WHERE e.id_veiculo=CAST(JSON_UNQUOTE(JSON_EXTRACT(p,'$.intencao.id_veiculo')) AS UNSIGNED) AND e.situacao='ATIVA'
   ORDER BY e.data_entrada DESC,e.id_entrada DESC LIMIT 1);
  INSERT INTO multiplikar.intencao_compra(id_atendimento,id_entrada,valor_disponivel,codigo_forma,data_registro,origem)
  VALUES(v_atendimento,v_entrada,
   CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p,'$.intencao.valor_disponivel')),'null') AS DECIMAL(14,2)),
   NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p,'$.intencao.codigo_forma')),'null'),v_agora,'SITE')
  ON DUPLICATE KEY UPDATE id_entrada=VALUES(id_entrada),valor_disponivel=VALUES(valor_disponivel),
   codigo_forma=VALUES(codigo_forma),data_registro=VALUES(data_registro);
 END IF;
 IF v_novo THEN CALL multiplikar.registrar_classificacao_lead(v_atendimento,'REGRA-V2',v_agora,v_classificacao); END IF;
 SET p_id_atendimento=v_atendimento;
 COMMIT;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE registrar_mensagem(IN p JSON, OUT p_id_mensagem BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 INSERT INTO app.mensagem_contato(assunto,nome,documento,telefone,email,cidade,estado_uf,mensagem,preferencia_contato,aceite_termos)
 VALUES(JSON_UNQUOTE(JSON_EXTRACT(p,'$.assunto')),TRIM(JSON_UNQUOTE(JSON_EXTRACT(p,'$.nome'))),
  REGEXP_REPLACE(JSON_UNQUOTE(JSON_EXTRACT(p,'$.documento')),'[^0-9]',''),JSON_UNQUOTE(JSON_EXTRACT(p,'$.telefone')),
  LOWER(JSON_UNQUOTE(JSON_EXTRACT(p,'$.email'))),JSON_UNQUOTE(JSON_EXTRACT(p,'$.cidade')),
  UPPER(JSON_UNQUOTE(JSON_EXTRACT(p,'$.estado_uf'))),JSON_UNQUOTE(JSON_EXTRACT(p,'$.mensagem')),
  JSON_UNQUOTE(JSON_EXTRACT(p,'$.preferencia_contato')),JSON_UNQUOTE(JSON_EXTRACT(p,'$.aceite_termos')) IN ('true','1'));
 SET p_id_mensagem=LAST_INSERT_ID(); COMMIT;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE revisar_lead(IN p_id_atendimento BIGINT,IN p_temperatura VARCHAR(10),IN p_id_revisor BIGINT,IN p_justificativa VARCHAR(500),OUT p_id_classificacao BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 CALL app.exigir_lead_site(p_id_atendimento); CALL app.exigir_funcionario_ativo(p_id_revisor);
 SET p_id_classificacao=(SELECT id_classificacao FROM multiplikar.vw_lead_atual WHERE id_atendimento=p_id_atendimento);
 UPDATE multiplikar.classificacao_lead SET temperatura_final=p_temperatura,id_revisor=p_id_revisor,
  data_revisao=CURRENT_TIMESTAMP,justificativa_revisao=NULLIF(TRIM(p_justificativa),'') WHERE id_classificacao=p_id_classificacao;
 COMMIT;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE registrar_interacao(IN p_id_atendimento BIGINT,IN p_id_funcionario BIGINT,IN p_canal VARCHAR(20),IN p_direcao VARCHAR(20),IN p_resumo VARCHAR(1000),IN p_proximo_passo VARCHAR(200),IN p_data_proximo DATETIME,OUT p_id_interacao BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION; CALL app.exigir_lead_site(p_id_atendimento); CALL app.exigir_funcionario_ativo(p_id_funcionario);
 INSERT INTO multiplikar.interacao(id_atendimento,id_funcionario,data_hora,canal,direcao,resumo,proximo_passo,data_proximo_passo)
 VALUES(p_id_atendimento,p_id_funcionario,CURRENT_TIMESTAMP,p_canal,p_direcao,p_resumo,NULLIF(TRIM(p_proximo_passo),''),p_data_proximo);
 SET p_id_interacao=LAST_INSERT_ID(); COMMIT;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE reclassificar_lead(IN p_id_atendimento BIGINT,OUT p_id_classificacao BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION; CALL app.exigir_lead_site(p_id_atendimento);
 CALL multiplikar.registrar_classificacao_lead(p_id_atendimento,'REGRA-V2',CURRENT_TIMESTAMP,p_id_classificacao);
 COMMIT;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE registrar_desfecho(IN p_id_atendimento BIGINT,IN p_id_funcionario BIGINT,IN p_tipo VARCHAR(10),IN p_motivo VARCHAR(300),IN p_detalhe VARCHAR(800),OUT p_id BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION; CALL app.exigir_lead_site(p_id_atendimento); CALL app.exigir_funcionario_ativo(p_id_funcionario);
 INSERT INTO multiplikar.atendimento_desfecho(id_atendimento,id_funcionario,data_hora,tipo_desfecho,motivo,detalhe)
 VALUES(p_id_atendimento,p_id_funcionario,CURRENT_TIMESTAMP,p_tipo,p_motivo,NULLIF(TRIM(p_detalhe),''));
 SET p_id=p_id_atendimento; COMMIT;
END$$

CREATE DEFINER='app_definer'@'localhost' PROCEDURE marcar_mensagem_lida(IN p_id_mensagem BIGINT,IN p_id_funcionario BIGINT,OUT p_id BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION; CALL app.exigir_funcionario_ativo(p_id_funcionario);
 UPDATE app.mensagem_contato SET lida_em=CURRENT_TIMESTAMP,id_funcionario_leitura=p_id_funcionario
 WHERE id_mensagem=p_id_mensagem AND lida_em IS NULL;
 IF ROW_COUNT()<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Mensagem inexistente ou ja lida'; END IF;
 SET p_id=p_id_mensagem; COMMIT;
END$$
DELIMITER ;

-- Utilizador bloqueado, usado apenas como DEFINER das rotinas SECURITY DEFINER.
GRANT SELECT ON app.* TO 'app_definer'@'localhost';
GRANT INSERT,UPDATE ON app.registro_site TO 'app_definer'@'localhost';
GRANT INSERT,SELECT,UPDATE ON app.mensagem_contato TO 'app_definer'@'localhost';
GRANT INSERT,SELECT ON app.veiculo_ofertado TO 'app_definer'@'localhost';
GRANT SELECT ON multiplikar.* TO 'app_definer'@'localhost';
GRANT EXECUTE ON app.* TO 'app_definer'@'localhost';
GRANT INSERT ON multiplikar.pessoa TO 'app_definer'@'localhost';
GRANT UPDATE (id_pessoa) ON multiplikar.pessoa TO 'app_definer'@'localhost';
GRANT INSERT ON multiplikar.atendimento TO 'app_definer'@'localhost';
GRANT INSERT ON multiplikar.interacao TO 'app_definer'@'localhost';
GRANT INSERT ON multiplikar.veiculo TO 'app_definer'@'localhost';
GRANT INSERT,UPDATE ON multiplikar.intencao_compra TO 'app_definer'@'localhost';
GRANT INSERT,UPDATE ON multiplikar.classificacao_lead TO 'app_definer'@'localhost';
GRANT INSERT ON multiplikar.classificacao_fator TO 'app_definer'@'localhost';
GRANT INSERT ON multiplikar.atendimento_desfecho TO 'app_definer'@'localhost';
GRANT EXECUTE ON PROCEDURE multiplikar.registrar_classificacao_lead TO 'app_definer'@'localhost';
GRANT EXECUTE ON PROCEDURE app.exigir_lead_site TO 'app_definer'@'localhost';
GRANT EXECUTE ON PROCEDURE app.exigir_funcionario_ativo TO 'app_definer'@'localhost';

-- Placeholders substituidos pelo setup-mysql-vm.sh a partir de variaveis de ambiente.
CREATE USER IF NOT EXISTS 'api_leitura'@'127.0.0.1' IDENTIFIED BY '__API_LEITURA_PASSWORD__';
CREATE USER IF NOT EXISTS 'api_cadastro'@'127.0.0.1' IDENTIFIED BY '__API_CADASTRO_PASSWORD__';
CREATE USER IF NOT EXISTS 'api_crm'@'127.0.0.1' IDENTIFIED BY '__API_CRM_PASSWORD__';
CREATE USER IF NOT EXISTS 'api_demo'@'127.0.0.1' IDENTIFIED BY '__API_DEMO_PASSWORD__';
GRANT SELECT ON multiplikar.* TO 'api_leitura'@'127.0.0.1';
GRANT SELECT ON app.registro_site TO 'api_leitura'@'127.0.0.1';
GRANT SELECT ON app.mensagem_contato TO 'api_leitura'@'127.0.0.1';
GRANT SELECT ON app.veiculo_ofertado TO 'api_leitura'@'127.0.0.1';
GRANT SELECT ON app.vw_veiculo_situacao_publica TO 'api_leitura'@'127.0.0.1';
GRANT EXECUTE ON FUNCTION multiplikar.data_referencia TO 'api_leitura'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE multiplikar.fn_previsao_caixa_cenario TO 'api_leitura'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.cadastrar_lead TO 'api_cadastro'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.registrar_mensagem TO 'api_cadastro'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.revisar_lead TO 'api_crm'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.registrar_interacao TO 'api_crm'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.reclassificar_lead TO 'api_crm'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.registrar_desfecho TO 'api_crm'@'127.0.0.1';
GRANT EXECUTE ON PROCEDURE app.marcar_mensagem_lida TO 'api_crm'@'127.0.0.1';
-- api_demo so conecta na rota de regras, dentro de transacoes revertidas; so
-- consulta os identificadores usados nos predicados das tentativas invalidas.
GRANT SELECT (id_venda) ON multiplikar.venda TO 'api_demo'@'127.0.0.1';
GRANT SELECT (id_atendimento) ON multiplikar.atendimento TO 'api_demo'@'127.0.0.1';
GRANT SELECT (id_proposta) ON multiplikar.proposta TO 'api_demo'@'127.0.0.1';
GRANT SELECT (id_simulacao) ON multiplikar.simulacao_financiamento TO 'api_demo'@'127.0.0.1';
GRANT SELECT (id_obrigacao) ON multiplikar.obrigacao_financeira TO 'api_demo'@'127.0.0.1';
GRANT SELECT (id_interacao) ON multiplikar.interacao TO 'api_demo'@'127.0.0.1';
GRANT SELECT (id_classificacao) ON multiplikar.classificacao_lead TO 'api_demo'@'127.0.0.1';
GRANT INSERT ON multiplikar.pessoa TO 'api_demo'@'127.0.0.1';
GRANT UPDATE ON multiplikar.atendimento TO 'api_demo'@'127.0.0.1';
GRANT DELETE ON multiplikar.venda TO 'api_demo'@'127.0.0.1';
GRANT UPDATE ON multiplikar.proposta TO 'api_demo'@'127.0.0.1';
GRANT UPDATE ON multiplikar.simulacao_financiamento TO 'api_demo'@'127.0.0.1';
GRANT UPDATE ON multiplikar.obrigacao_financeira TO 'api_demo'@'127.0.0.1';
GRANT DELETE ON multiplikar.interacao TO 'api_demo'@'127.0.0.1';
GRANT UPDATE ON multiplikar.classificacao_lead TO 'api_demo'@'127.0.0.1';
FLUSH PRIVILEGES;
