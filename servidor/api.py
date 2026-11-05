"""API do banco Multiplikar (demonstração acadêmica).

Duas chaves, dois níveis de acesso:
- chave pública (site): consultas da demonstração, testes de regras e os
  formulários de orçamento e contato;
- chave do vendedor (painel): tudo acima, mais o CRM (leads, revisão humana,
  interações, desfecho e mensagens).

Não recebe SQL do cliente. Consultas são fixas; gravações passam por funções do
esquema app, executadas por usuários do banco que só podem chamar essas funções.
"""
import datetime
import decimal
import hmac
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pymysql
from pymysql.cursors import DictCursor

CHAVE_PUBLICA = os.environ["MULTIPLIKAR_API_KEY"]
CHAVE_VENDEDOR = os.environ["MULTIPLIKAR_API_KEY_VENDEDOR"]
DSN_LEITURA = os.environ["MULTIPLIKAR_MYSQL_LEITURA"]
DSN_DEMO = os.environ["MULTIPLIKAR_MYSQL_DEMO"]
DSN_CADASTRO = os.environ["MULTIPLIKAR_MYSQL_CADASTRO"]
DSN_CRM = os.environ["MULTIPLIKAR_MYSQL_CRM"]
TAMANHO_MAXIMO_CORPO = 16 * 1024
FUSO_MYSQL = os.environ.get("MULTIPLIKAR_MYSQL_TIME_ZONE", "America/Sao_Paulo")

# Veículos que o formulário de orçamento oferece: situação DISPONIVEL calculada pela
# view do projeto (vw_veiculo_situacao) e preço anunciado da entrada mais recente.
SQL_DISPONIVEIS = """
    SELECT s.id_veiculo, s.marca, s.modelo, s.ano_modelo, s.cor, s.categoria_comercial, e.preco_anunciado
    FROM vw_veiculo_situacao s
    JOIN LATERAL (SELECT x.preco_anunciado FROM entrada x WHERE x.id_veiculo = s.id_veiculo
                  ORDER BY x.data_entrada DESC, x.id_entrada DESC LIMIT 1) AS e ON TRUE
    WHERE s.situacao_atual = 'DISPONIVEL'
    ORDER BY s.marca, s.modelo, s.id_veiculo"""

CONSULTAS_PUBLICAS = {
    # Mesma view do modelo, sem os carros oferecidos pelo site que ainda não entraram no estoque.
    "estoque": "SELECT id_veiculo, marca, modelo, ano_modelo, cor, categoria_comercial, situacao_atual "
               "FROM app.vw_veiculo_situacao_publica ORDER BY id_veiculo",
    "propostas": "SELECT rotulo, situacao, valor_total, caixa_d0, caixa_posterior, valor_em_troca, "
                 "margem_estimada, retorno_banco, margem_com_retorno "
                 "FROM vw_proposta_comparativo ORDER BY rotulo",
    "simulacoes": "SELECT id_simulacao, tabela_retorno, taxa_cliente_mensal, parcela_calculada, "
                  "custo_total_cliente, cet_aproximado_anual, retorno_loja "
                  "FROM vw_simulacao_parcela ORDER BY id_simulacao",
    "previsao": "SELECT semana, realizado, obrigacoes, funil_ponderado, saldo_projetado "
                "FROM vw_previsao_caixa ORDER BY semana",
    "fila": "SELECT * FROM vw_fila_acoes",
    "disponiveis": SQL_DISPONIVEIS,
}

# Leads do site usam o relógio real para "dias sem contato"; os da massa de
# demonstração seguem a data de referência do projeto (data_referencia()).
CONSULTAS_VENDEDOR = {
    "painel/leads": """
        SELECT l.id_atendimento, l.nome_cliente, l.telefone, p.email, l.tipo_interesse,
               l.descricao_interesse, l.data_abertura, l.situacao_atendimento,
               l.tipo_desfecho, l.motivo_desfecho, l.temperatura_sugerida, l.pontuacao,
               l.temperatura_final, l.revisado, l.justificativa_revisao, l.temperatura_atual,
               l.total_interacoes, l.data_ultima_interacao, l.versao_regra,
               (r.id_atendimento IS NOT NULL) AS do_site, r.formulario,
               pv.nome AS vendedor,
               CASE WHEN r.id_atendimento IS NOT NULL
                    THEN DATEDIFF(CURRENT_DATE, DATE(COALESCE(l.data_ultima_interacao, l.data_abertura)))
                    ELSE l.dias_sem_contato END AS dias_sem_contato
        FROM vw_lead_atual l
        JOIN pessoa p ON p.id_pessoa = l.id_pessoa
        JOIN funcionario f ON f.id_funcionario = l.id_funcionario
        JOIN pessoa pv ON pv.id_pessoa = f.id_pessoa
        LEFT JOIN app.registro_site r ON r.id_atendimento = l.id_atendimento
        ORDER BY do_site DESC, COALESCE(l.data_ultima_interacao, l.data_abertura) DESC""",
    "painel/funcionarios": """
        SELECT f.id_funcionario, p.nome, f.cargo FROM funcionario f
        JOIN pessoa p ON p.id_pessoa = f.id_pessoa
        WHERE f.situacao = 'ATIVO' ORDER BY f.id_funcionario""",
    "painel/mensagens": """
        SELECT m.id_mensagem, m.recebida_em, m.assunto, m.nome, m.telefone, m.email, m.cidade,
               m.estado_uf, m.mensagem, m.preferencia_contato, m.lida_em, p.nome AS lida_por
        FROM app.mensagem_contato m
        LEFT JOIN funcionario f ON f.id_funcionario = m.id_funcionario_leitura
        LEFT JOIN pessoa p ON p.id_pessoa = f.id_pessoa
        ORDER BY (m.lida_em IS NULL) DESC, m.recebida_em DESC""",
}
DETALHE_LEAD = {
    "classificacoes": """
        SELECT c.id_classificacao, c.data_hora, c.origem, c.versao_regra, c.temperatura_sugerida,
               c.pontuacao, c.temperatura_final, c.data_revisao, c.justificativa_revisao,
               pr.nome AS revisor,
               (SELECT CAST(CONCAT('[', COALESCE(GROUP_CONCAT(
                       JSON_OBJECT('fator',fa.codigo_fator,'pontos',fa.pontos,'evidencia',fa.evidencia)
                       ORDER BY fa.codigo_fator SEPARATOR ','),''),']') AS JSON)
                  FROM classificacao_fator fa WHERE fa.id_classificacao = c.id_classificacao) AS fatores
        FROM classificacao_lead c
        LEFT JOIN funcionario f ON f.id_funcionario = c.id_revisor
        LEFT JOIN pessoa pr ON pr.id_pessoa = f.id_pessoa
        WHERE c.id_atendimento = %s ORDER BY c.data_hora DESC, c.id_classificacao DESC""",
    "interacoes": """
        SELECT i.id_interacao, i.data_hora, i.canal, i.direcao, i.resumo, i.proximo_passo,
               i.data_proximo_passo, p.nome AS funcionario
        FROM interacao i JOIN funcionario f ON f.id_funcionario = i.id_funcionario
        JOIN pessoa p ON p.id_pessoa = f.id_pessoa
        WHERE i.id_atendimento = %s ORDER BY i.data_hora DESC, i.id_interacao DESC""",
    "veiculos_oferecidos": """
        SELECT v.marca, v.modelo, v.ano_modelo, v.cor, v.placa, v.combustivel, v.cambio, s.situacao_atual,
               o.modalidade_pretendida, o.quilometragem_informada, o.proprietarios_informados,
               o.valor_pretendido, o.observacoes, o.recebido_em
        FROM app.veiculo_ofertado o JOIN veiculo v USING (id_veiculo)
        JOIN vw_veiculo_situacao s USING (id_veiculo)
        WHERE o.id_atendimento = %s ORDER BY o.recebido_em DESC""",
    "desfecho": """
        SELECT d.tipo_desfecho, d.motivo, d.detalhe, d.data_hora, p.nome AS funcionario
        FROM atendimento_desfecho d JOIN funcionario f ON f.id_funcionario = d.id_funcionario
        JOIN pessoa p ON p.id_pessoa = f.id_pessoa WHERE d.id_atendimento = %s""",
}
CENARIOS = ("BASE", "BANCO_ATRA_15_DIAS", "LEADS_QUENTES_NAO_FECHAM")

# Operações inválidas de propósito: o banco deve recusar cada uma.
# Rodam numa transação que é sempre desfeita.
TESTES = [
    ("CPF repetido",
     "INSERT INTO pessoa (nome,tipo_documento,numero_documento,telefone,email,logradouro,numero,bairro,cidade,estado_uf) "
     "VALUES ('Teste','CPF','00000000001','11999990000','t@example.invalid','Rua','1','Centro','Sao Paulo','SP')"),
    ("Apagar venda histórica (RN13)", "DELETE FROM venda WHERE id_venda = 4"),
    ("Situação inválida", "UPDATE atendimento SET situacao = 'PENDENTE' WHERE id_atendimento = 1"),
    ("Alterar proposta já apresentada (RN34)", "UPDATE proposta SET desconto = 5000 WHERE id_proposta = 1"),
    ("Mudar a taxa de simulação em análise (RN38)",
     "UPDATE simulacao_financiamento SET taxa_mensal = 0.01 WHERE id_simulacao = 1"),
    ("Voltar obrigação atrasada para prevista (RN39)",
     "UPDATE obrigacao_financeira SET situacao = 'PREVISTA' WHERE id_obrigacao = 1"),
    ("Apagar interação do histórico (RN40)", "DELETE FROM interacao WHERE id_interacao = 1"),
    ("Revisar de novo um lead já revisado (RN41)",
     "UPDATE classificacao_lead SET temperatura_final = 'FRIO', justificativa_revisao = 'teste' "
     "WHERE id_classificacao = 2"),
]
ERROS_TESTES_CONTRATO = {
    "CPF repetido": (1062, "23505", "uq_pessoa_documento", 'duplicate key value violates unique constraint "uq_pessoa_documento"'),
    "Apagar venda hist\u00f3rica (RN13)": (1644, "P0001", None, "Historico de venda deve ser encerrado, nunca apagado"),
    "Situa\u00e7\u00e3o inv\u00e1lida": (3819, "23514", "ck_atendimento_situacao", 'new row for relation "atendimento" violates check constraint "ck_atendimento_situacao"'),
    "Alterar proposta j\u00e1 apresentada (RN34)": (1644, "P0001", None, "Proposta apresentada e imutavel; crie nova versao"),
    "Mudar a taxa de simula\u00e7\u00e3o em an\u00e1lise (RN38)": (1644, "P0001", None, "Simulacao em analise so permite alterar situacao, data_resposta e parcela_informada"),
    "Voltar obriga\u00e7\u00e3o atrasada para prevista (RN39)": (1644, "P0001", None, "Transicao de situacao da obrigacao financeira invalida"),
    "Apagar intera\u00e7\u00e3o do hist\u00f3rico (RN40)": (1644, "P0001", None, "Registro de interacao e somente insercao; historico nao pode ser alterado ou removido"),
    "Revisar de novo um lead j\u00e1 revisado (RN41)": (1644, "P0001", None, "Classificacao ja revisada e imutavel"),
}

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
TIPO_ORCAMENTO = {"comprar": "COMPRA", "vender": "VENDA", "trocar": "TROCA"}
ASSUNTO_CONTATO = {
    "compra_veiculo": ("COMPRA", "Comprar um veículo do estoque"),
    "venda_veiculo": ("VENDA", "Vender o veículo para a loja"),
    "consignacao": ("VENDA", "Consignar o veículo"),
    "avaliacao": ("VENDA", "Avaliação ou laudo cautelar do veículo"),
    "financiamento": ("COMPRA", "Comprar com financiamento"),
}
MENSAGEM_CONTATO = {"garantia": "GARANTIA", "outros": "OUTROS"}
PREFERENCIA = {"whatsapp": "WhatsApp", "telefone": "telefone", "email": "e-mail"}
PREFERENCIA_VEICULO = {"novo": "novo", "seminovo": "seminovo", "usado": "usado", "indiferente": "indiferente"}
# Código da forma em FORMA_PAGAMENTO (intenção de compra); "combinada" fica sem código.
CODIGO_FORMA = {"dinheiro": "DINHEIRO", "pix": "PIX", "cartao": "CARTAO", "financiamento": "FINANCIAMENTO"}
PAGAMENTO = {"dinheiro": "dinheiro", "pix": "Pix", "cartao": "cartão", "financiamento": "financiamento",
             "combinada": "forma combinada"}
TEMPERATURAS = {"FRIO", "MORNO", "QUENTE"}
CANAIS = {"TELEFONE", "WHATSAPP", "EMAIL", "PRESENCIAL", "OUTRO"}
DIRECOES = {"RECEBIDA", "ENVIADA"}
DESFECHOS = {"GANHO", "PERDA"}
COMBUSTIVEIS = {"flex": "Flex", "gasolina": "Gasolina", "etanol": "Etanol", "diesel": "Diesel",
                "hibrido": "Hibrido", "eletrico": "Eletrico"}
CAMBIOS = {"manual": "Manual", "automatico": "Automatico", "semiautomatico": "Semiautomatico"}
MODALIDADE_VENDA = {"compra_propria": "COMPRA_PROPRIA", "consignacao": "CONSIGNACAO"}


ROTULOS = {
    "nome_cliente": "Nome completo", "nome_completo": "Nome completo", "documento": "CPF ou CNPJ",
    "telefone": "Telefone", "email": "E-mail", "logradouro": "Endereço", "numero": "Número",
    "complemento": "Complemento", "bairro": "Bairro", "cidade": "Cidade", "estado": "Estado",
    "tipo_atendimento": "Tipo de atendimento", "veiculo_interesse": "Veículo de interesse",
    "preferencia_veiculo": "Preferência quanto ao estado do veículo", "valor_disponivel": "Valor disponível",
    "veiculo_entrada": "Veículo para entrada", "forma_pagamento": "Forma de pagamento",
    "observacoes": "Observações", "mensagem": "Mensagem", "preferencia_contato": "Preferência de retorno",
    "assunto": "Assunto", "carro_marca": "Marca do seu veículo", "carro_modelo": "Modelo do seu veículo",
    "carro_cor": "Cor do seu veículo", "carro_combustivel": "Combustível do seu veículo",
    "carro_cambio": "Câmbio do seu veículo", "carro_modalidade": "Como prefere negociar",
    "carro_observacoes": "Observações sobre o seu veículo",
    "carro_ano": "Ano do seu veículo", "carro_km": "Quilometragem do seu veículo",
    "carro_placa": "Placa", "carro_valor": "Valor pretendido",
}


class DadoInvalido(Exception):
    pass


def para_json(valor):
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, (datetime.date, datetime.datetime)):
        if isinstance(valor, datetime.datetime) and valor.tzinfo is None:
            deslocamento = re.fullmatch(r"([+-])(\d{2}):(\d{2})", FUSO_MYSQL)
            if deslocamento:
                minutos = (int(deslocamento[2]) * 60 + int(deslocamento[3])) * (1 if deslocamento[1] == "+" else -1)
                valor = valor.replace(tzinfo=datetime.timezone(datetime.timedelta(minutes=minutos)))
            else:
                valor = valor.replace(tzinfo=ZoneInfo(FUSO_MYSQL))
        return valor.isoformat()
    return str(valor)


def conectar(dsn):
    """Abre uma conexao PyMySQL e fixa a sessao no fuso de Sao Paulo."""
    from urllib.parse import unquote, urlparse
    u = urlparse(dsn)
    if u.scheme != "mysql" or not u.hostname or not u.username:
        raise RuntimeError("DSN MySQL invalida")
    conn = pymysql.connect(host=u.hostname, port=u.port or 3306, user=unquote(u.username),
                           password=unquote(u.password or ""), database=(u.path or "/multiplikar").lstrip("/"),
                           charset="utf8mb4", cursorclass=DictCursor, autocommit=True,
                           connect_timeout=5)
    try:
        with conn.cursor() as cur:
            # Em producao, carregue as tabelas de fusos do MySQL para aceitar o nome IANA.
            # O teste local pode usar -03:00, que corresponde ao fuso de Sao Paulo em 2026.
            cur.execute("SET time_zone=%s", (FUSO_MYSQL,))
    except Exception:
        conn.close()
        raise
    return conn


def consultar(sql, params=None):
    with conectar(DSN_LEITURA) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            linhas = cur.fetchall()
            for linha in linhas:
                if isinstance(linha.get("fatores"), str):
                    linha["fatores"] = json.loads(linha["fatores"])
            return linhas


def consultar_cenario(cenario, saldo_inicial):
    with conectar(DSN_LEITURA) as conn:
        with conn.cursor() as cur:
            cur.execute("CALL multiplikar.fn_previsao_caixa_cenario(%s,%s)", (cenario, saldo_inicial))
            linhas = cur.fetchall()
            while cur.nextset():
                pass
            # O contrato publico legado devolve somente semana e saldo_projetado.
            return [{"semana": linha["semana"], "saldo_projetado": linha["saldo_projetado"]}
                    for linha in linhas]


def consultar_fila_compatibilidade():
    """Mantém as descrições compatíveis com o contrato atual da API."""
    linhas = consultar(CONSULTAS_PUBLICAS["fila"])
    for linha in linhas:
        if linha["fonte"] == "CRM":
            lead = consultar("SELECT * FROM vw_lead_atual WHERE id_atendimento=%s", (linha["id_referencia"],))[0]
            propostas = consultar("SELECT id_proposta,valor_total FROM proposta WHERE id_atendimento=%s "
                "AND situacao IN ('RASCUNHO','APRESENTADA') AND validade>=data_referencia() "
                "ORDER BY valor_total DESC,data_criacao DESC,id_proposta DESC", (linha["id_referencia"],))
            limite = 3 if lead["temperatura_atual"] == "QUENTE" else 7
            revisao = (f", revisada por funcionario {lead['id_revisor']}" if lead["revisado"] else ", sem revisao humana")
            contato = lead["data_ultima_interacao"] or "abertura do atendimento"
            if propostas:
                valor_em_risco = decimal.Decimal(propostas[0]["valor_total"])
                exposicao = (f"proposta {propostas[0]['id_proposta']}, maior valor entre {len(propostas)} "
                             f"alternativa(s) aberta(s) e valida(s) ({valor_em_risco:.2f})")
            else:
                valor_em_risco = decimal.Decimal(linha["valor_em_risco"] or 0)
                exposicao = f"veiculo anunciado a {valor_em_risco:.2f}, sem proposta aberta"
            linha["valor_em_risco"] = float(valor_em_risco)
            linha["motivo"] = (f"classificacao {lead['temperatura_atual']} (pontuacao {lead['pontuacao']}, "
                f"regra {lead['versao_regra']}{revisao}) sem novo contato desde {contato}; "
                f"limite para {lead['temperatura_atual']} = {limite} dias; valor em risco = {exposicao}")
        elif linha["fonte"] == "CAIXA":
            ob = consultar("SELECT o.*,DATEDIFF(data_referencia(),o.vencimento_atual) AS dias, "
                "(SELECT CONCAT(pp.banco,'|',pp.dias_previstos) FROM venda v JOIN parametro_prazo pp "
                "ON pp.banco=v.instituicao_financeira AND pp.tipo_obrigacao='FINANCIAMENTO_RECEBER' "
                "AND pp.vigencia<=data_referencia() WHERE v.id_venda=o.id_venda "
                "ORDER BY pp.vigencia DESC LIMIT 1) AS prazo "
                "FROM obrigacao_financeira o WHERE o.id_obrigacao=%s", (linha["id_referencia"],))[0]
            linha["descricao"] = (f"Obrigacao {ob['id_obrigacao']} (venda {ob['id_venda']}, {ob['categoria']}): "
                f"{ob['natureza'].lower()} de {ob['valor']:.2f} vencido desde {ob['vencimento_atual']} "
                f"({ob['dias']} dias de atraso)")
            prazo = f" (parametro_prazo do banco {ob['prazo'].split('|')[0]} = {ob['prazo'].split('|')[1]} dias)" if ob["prazo"] else ""
            linha["motivo"] = (f"obrigacao_financeira: situacao={ob['situacao']}, vencimento_original={ob['vencimento_original']}, "
                f"vencimento_atual={ob['vencimento_atual']}{prazo}; hoje={consultar('SELECT data_referencia() AS d')[0]['d']}")
        elif linha["fonte"] == "ESTOQUE":
            e = consultar("SELECT e.id_entrada,e.data_entrada,e.valor_acordado,v.marca,v.modelo, "
                "DATEDIFF(data_referencia(),DATE(e.data_entrada)) AS dias, "
                "(SELECT SUM(d.valor) FROM despesa d WHERE d.id_veiculo=e.id_veiculo) AS despesas "
                "FROM entrada e JOIN veiculo v ON v.id_veiculo=e.id_veiculo WHERE e.id_entrada=%s",
                (linha["id_referencia"],))[0]
            despesas = e["despesas"] if e["despesas"] is not None else 0
            linha["descricao"] = (f"Veiculo {e['marca']} {e['modelo']} (entrada {e['id_entrada']}) parado ha "
                f"{e['dias']} dias, capital de {e['valor_acordado']:.2f} mais {despesas} em despesas")
            linha["motivo"] = (f"entrada ativa sem venda nem proposta aberta associada desde {e['data_entrada']}; "
                f"despesas acumuladas desde a entrada = {despesas}; limite hipotese de \"parado\" = 30 dias")
    ordem = {"CAIXA": 0, "CRM": 1, "ESTOQUE": 2}
    return sorted(linhas, key=lambda linha: ordem.get(linha["fonte"], 9))


def chamar(dsn, funcao, *args):
    nome = funcao.rsplit(".", 1)[-1]
    with conectar(dsn) as conn:
        with conn.cursor() as cur:
            marcadores = ",".join(["%s"] * len(args) + ["@mk_api_resultado"])
            cur.execute(f"CALL `{nome}`({marcadores})", args)
            while cur.nextset():
                pass
            cur.execute("SELECT @mk_api_resultado AS resultado")
            return cur.fetchone()["resultado"]


def testar_regras():
    resultados = []
    with conectar(DSN_DEMO) as conn:
        for nome, sql in TESTES:
            try:
                conn.begin()
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.rollback()
                resultados.append({"teste": nome, "recusado": False, "mensagem": "ACEITO (não esperado)"})
            except pymysql.MySQLError as erro:
                conn.rollback()
                esperado, estado, restricao, mensagem = ERROS_TESTES_CONTRATO[nome]
                if erro.args and erro.args[0] == esperado:
                    resultados.append({"teste": nome, "recusado": True, "codigo": estado,
                                       "restricao": restricao, "mensagem": mensagem})
                else:
                    resultados.append({"teste": nome, "recusado": False, "codigo": getattr(erro, "sqlstate", None),
                                       "restricao": None, "mensagem": str(erro.args[-1]) if erro.args else str(erro)})
    return resultados


# ---------- validação dos formulários do site ----------

def texto(dados, campo, minimo=1, maximo=200, obrigatorio=True):
    valor = str(dados.get(campo) or "").strip()
    if not valor and not obrigatorio:
        return ""
    if not minimo <= len(valor) <= maximo:
        raise DadoInvalido(f"Confira o campo {ROTULOS.get(campo, campo)}")
    return valor


def opcao(dados, campo, opcoes):
    valor = str(dados.get(campo) or "").strip().lower()
    if valor not in opcoes:
        raise DadoInvalido(f"Confira o campo {ROTULOS.get(campo, campo)}")
    return opcoes[valor]


def digitos_verificadores_ok(numeros, pesos_lista):
    for pesos in pesos_lista:
        corpo = numeros[:len(pesos)]
        resto = sum(int(d) * p for d, p in zip(corpo, pesos)) % 11
        esperado = 0 if resto < 2 else 11 - resto
        if int(numeros[len(pesos)]) != esperado:
            return False
    return True


def documento_valido(valor):
    numeros = re.sub(r"\D", "", valor)
    if len(set(numeros)) == 1:
        return False
    if len(numeros) == 11:
        return digitos_verificadores_ok(numeros, [list(range(10, 1, -1)), list(range(11, 1, -1))])
    if len(numeros) == 14:
        return digitos_verificadores_ok(numeros, [[5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                                                  [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]])
    return False


def pessoa_do_formulario(dados, campo_nome):
    documento = texto(dados, "documento", 11, 18)
    if not documento_valido(documento):
        raise DadoInvalido("CPF ou CNPJ inválido")
    telefone = re.sub(r"\D", "", texto(dados, "telefone", 8, 20))
    if not 10 <= len(telefone) <= 11:
        raise DadoInvalido("Telefone inválido")
    email = texto(dados, "email", 5, 120)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise DadoInvalido("E-mail inválido")
    uf = texto(dados, "estado", 2, 2).upper()
    if uf not in UFS:
        raise DadoInvalido("Estado inválido")
    if str(dados.get("aceite_termos") or dados.get("aceite_contato") or "").lower() not in ("on", "true", "1", "sim"):
        raise DadoInvalido("É preciso aceitar o uso dos dados para o atendimento")
    return {
        "nome": texto(dados, campo_nome, 3, 100), "documento": documento, "telefone": telefone,
        "email": email, "logradouro": texto(dados, "logradouro", 3, 120),
        "numero": texto(dados, "numero", 1, 10), "complemento": texto(dados, "complemento", 0, 60, False),
        "bairro": texto(dados, "bairro", 2, 80), "cidade": texto(dados, "cidade", 2, 80),
        "estado_uf": uf, "aceite_termos": True,
    }


def preco_brl(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def veiculo_de_interesse(dados, incluir_preco=False):
    """Carro escolhido no estoque; precisa estar DISPONIVEL no banco agora."""
    escolhido = str(dados.get("id_veiculo") or "").strip()
    if not escolhido.isdigit():
        raise DadoInvalido("Escolha um dos veículos disponíveis")
    achado = [v for v in consultar(SQL_DISPONIVEIS) if v["id_veiculo"] == int(escolhido)]
    if not achado:
        raise DadoInvalido("Esse veículo não está mais disponível. Escolha outro da lista.")
    v = achado[0]
    preco = preco_brl(v["preco_anunciado"]) if v["preco_anunciado"] is not None else "preço a consultar"
    descricao = f"{v['marca']} {v['modelo']} {v['ano_modelo']} {v['cor']} (veículo {v['id_veiculo']} do estoque, {preco})"
    return (descricao, v["preco_anunciado"]) if incluir_preco else descricao

def veiculo_do_cliente(dados, modalidade):
    """Carro que o cliente oferece (venda, consignação ou troca): vira cadastro preliminar (RN04/RN05)."""
    ano_atual = datetime.date.today().year
    ano = texto(dados, "carro_ano", 4, 4)
    if not ano.isdigit() or not 1950 <= int(ano) <= ano_atual + 1:
        raise DadoInvalido("Confira o campo Ano do seu veículo")
    km_txt = texto(dados, "carro_km", 1, 7)
    if not km_txt.isdigit():
        raise DadoInvalido("Confira o campo Quilometragem do seu veículo")
    placa = re.sub(r"[^A-Za-z0-9]", "", str(dados.get("carro_placa") or "")).upper()
    if placa and not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
        raise DadoInvalido("Confira o campo Placa (ex.: ABC1D23 ou ABC1234)")
    donos = str(dados.get("carro_donos") or "").strip()
    if donos and not (donos.isdigit() and int(donos) <= 20):
        raise DadoInvalido("Confira o campo Número de donos")
    valor = texto(dados, "carro_valor", 0, 12, False)
    if valor and not re.fullmatch(r"\d+(\.\d{1,2})?", valor):
        raise DadoInvalido("Confira o campo Valor pretendido")
    return {
        "marca": texto(dados, "carro_marca", 2, 40), "modelo": texto(dados, "carro_modelo", 1, 60),
        "ano_modelo": int(ano), "cor": texto(dados, "carro_cor", 3, 30),
        "combustivel": opcao(dados, "carro_combustivel", COMBUSTIVEIS),
        "cambio": opcao(dados, "carro_cambio", CAMBIOS), "quilometragem": int(km_txt),
        "placa": placa, "proprietarios": int(donos) if donos else None,
        "valor_pretendido": valor or None, "modalidade": modalidade,
        "observacoes": texto(dados, "carro_observacoes", 0, 500, False),
    }


def cadastro_orcamento(dados):
    p = pessoa_do_formulario(dados, "nome_cliente")
    tipo = opcao(dados, "tipo_atendimento", TIPO_ORCAMENTO)
    obs = texto(dados, "observacoes", 0, 800, False)
    detalhes = []
    if tipo in ("COMPRA", "TROCA"):
        interesse, preco_anunciado = veiculo_de_interesse(dados, incluir_preco=True)
        preferencia = opcao(dados, "preferencia_veiculo", PREFERENCIA_VEICULO)
        pagamento = opcao(dados, "forma_pagamento", PAGAMENTO)
        valor = texto(dados, "valor_disponivel", 0, 12, False)
        if valor and not re.fullmatch(r"\d+(\.\d{1,2})?", valor):
            raise DadoInvalido("Confira o campo Valor disponível")
        if valor and preco_anunciado is not None and decimal.Decimal(valor) > decimal.Decimal(str(preco_anunciado)):
            raise DadoInvalido(f"O valor dispon\u00edvel n\u00e3o pode ser maior que o pre\u00e7o do ve\u00edculo escolhido ({preco_brl(preco_anunciado)})")
        detalhes.append(f"Forma de pagamento: {pagamento}")
        if valor:
            detalhes.append(f"Valor disponível: R$ {valor}")
        p["intencao"] = {"id_veiculo": int(dados["id_veiculo"]), "valor_disponivel": valor or None,
                         "codigo_forma": CODIGO_FORMA.get(str(dados.get("forma_pagamento") or "").strip().lower())}
    if tipo in ("VENDA", "TROCA"):
        modalidade = "TROCA" if tipo == "TROCA" else opcao(dados, "carro_modalidade", MODALIDADE_VENDA)
        carro = veiculo_do_cliente(dados, modalidade)
        p["veiculo_cliente"] = carro
        km_formatado = f"{carro['quilometragem']:,}".replace(",", ".")
        descricao_carro = (f"{carro['marca']} {carro['modelo']} {carro['ano_modelo']} {carro['cor']}, "
                           f"{km_formatado} km informados")
        if carro["valor_pretendido"]:
            descricao_carro += f", valor pretendido R$ {carro['valor_pretendido']}"
    if tipo == "COMPRA":
        descricao = f"{interesse} (preferência: {preferencia})"
    elif tipo == "TROCA":
        descricao = f"{interesse}, com o carro do cliente na troca: {descricao_carro}"
    else:
        rotulo = {"COMPRA_PROPRIA": "vender para a loja", "CONSIGNACAO": "deixar em consignação"}[modalidade]
        descricao = f"Cliente quer {rotulo}: {descricao_carro}"
    if obs:
        detalhes.append(f"Observações do cliente: {obs}")
    p.update({
        "formulario": "ORCAMENTO", "tipo_interesse": tipo,
        "descricao_interesse": descricao[:400],
        "observacoes": "; ".join(detalhes),
        "resumo": (f"Pedido de orçamento pelo site. Contato informado: telefone {p['telefone']}, "
                   f"e-mail {p['email']}. {descricao}" + ("; " + "; ".join(detalhes) if detalhes else "")),
        "preferencia_contato": "telefone ou e-mail",
    })
    return chamar(DSN_CADASTRO, "app.cadastrar_lead", json.dumps(p, ensure_ascii=False))


def cadastro_contato(dados):
    p = pessoa_do_formulario(dados, "nome_completo")
    assunto = str(dados.get("assunto") or "").strip().lower()
    mensagem = texto(dados, "mensagem", 10, 1000)
    preferencia = opcao(dados, "preferencia_contato", PREFERENCIA)
    if assunto in MENSAGEM_CONTATO:
        p.update({"assunto": MENSAGEM_CONTATO[assunto], "mensagem": mensagem,
                  "preferencia_contato": preferencia})
        return chamar(DSN_CADASTRO, "app.registrar_mensagem", json.dumps(p, ensure_ascii=False))
    if assunto not in ASSUNTO_CONTATO:
        raise DadoInvalido("Assunto inválido")
    tipo, rotulo = ASSUNTO_CONTATO[assunto]
    p.update({
        "formulario": "CONTATO", "tipo_interesse": tipo,
        "descricao_interesse": f"{rotulo}: {mensagem[:200]}",
        "observacoes": "",
        "resumo": (f"Mensagem pelo formulário de contato do site ({rotulo}). Contato informado: telefone "
                   f"{p['telefone']}, e-mail {p['email']}. Mensagem: {mensagem}"),
        "preferencia_contato": preferencia,
    })
    return chamar(DSN_CADASTRO, "app.cadastrar_lead", json.dumps(p, ensure_ascii=False))


# Limite de envios por IP (formulários públicos): 5 a cada 10 minutos, 300 por dia no total.
_envios_ip = defaultdict(deque)
_envios_dia = deque()
_trava = threading.Lock()


def dentro_do_limite(ip):
    agora = time.time()
    with _trava:
        fila = _envios_ip[ip]
        while fila and agora - fila[0] > 600:
            fila.popleft()
        while _envios_dia and agora - _envios_dia[0] > 86400:
            _envios_dia.popleft()
        if len(fila) >= 5 or len(_envios_dia) >= 300:
            return False
        fila.append(agora)
        _envios_dia.append(agora)
        return True


# Trava de login da área do vendedor: 5 senhas erradas por IP a cada 15 minutos e
# 50 no total por hora. A verificação da senha é feita na Vercel, que consulta e
# registra as falhas aqui, porque as funções da Vercel não guardam estado.
_falhas_ip = defaultdict(deque)
_falhas_hora = deque()


def limpar_falhas(agora, fila):
    while fila and agora - fila[0] > 900:
        fila.popleft()
    while _falhas_hora and agora - _falhas_hora[0] > 3600:
        _falhas_hora.popleft()


def login_permitido(ip):
    agora = time.time()
    with _trava:
        fila = _falhas_ip[ip]
        limpar_falhas(agora, fila)
        return len(fila) < 5 and len(_falhas_hora) < 50


def registrar_falha_login(ip):
    with _trava:
        _falhas_ip[ip].append(time.time())
        _falhas_hora.append(time.time())


# ---------- ações do painel do vendedor ----------

def inteiro(dados, campo):
    try:
        return int(dados.get(campo))
    except (TypeError, ValueError):
        raise DadoInvalido(f"Campo {campo} inválido")


def membro(dados, campo, permitidos):
    valor = str(dados.get(campo) or "").strip().upper()
    if valor not in permitidos:
        raise DadoInvalido(f"Campo {campo} inválido")
    return valor


def data_hora_opcional(dados, campo):
    valor = str(dados.get(campo) or "").strip()
    if not valor:
        return None
    try:
        return datetime.datetime.fromisoformat(valor)
    except ValueError:
        raise DadoInvalido(f"Campo {campo} inválido")


def acao_vendedor(rota, d):
    if rota == "painel/revisar":
        return chamar(DSN_CRM, "app.revisar_lead", inteiro(d, "id_atendimento"),
                      membro(d, "temperatura", TEMPERATURAS), inteiro(d, "id_funcionario"),
                      texto(d, "justificativa", 0, 500, False))
    if rota == "painel/interacao":
        proximo = texto(d, "proximo_passo", 0, 200, False)
        data_proximo = data_hora_opcional(d, "data_proximo_passo")
        if data_proximo and not proximo:
            raise DadoInvalido("Informe o próximo passo junto com a data")
        return chamar(DSN_CRM, "app.registrar_interacao", inteiro(d, "id_atendimento"),
                      inteiro(d, "id_funcionario"), membro(d, "canal", CANAIS),
                      membro(d, "direcao", DIRECOES), texto(d, "resumo", 3, 1000), proximo, data_proximo)
    if rota == "painel/reclassificar":
        return chamar(DSN_CRM, "app.reclassificar_lead", inteiro(d, "id_atendimento"))
    if rota == "painel/desfecho":
        return chamar(DSN_CRM, "app.registrar_desfecho", inteiro(d, "id_atendimento"),
                      inteiro(d, "id_funcionario"), membro(d, "tipo", DESFECHOS),
                      texto(d, "motivo", 3, 300), texto(d, "detalhe", 0, 800, False))
    if rota == "painel/mensagem-lida":
        return chamar(DSN_CRM, "app.marcar_mensagem_lida", inteiro(d, "id_mensagem"),
                      inteiro(d, "id_funcionario"))
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "multiplikar-api"

    def responder(self, status, corpo):
        dados = json.dumps(corpo, default=para_json, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def nivel_acesso(self):
        chave = self.headers.get("X-API-Key", "")
        if hmac.compare_digest(chave, CHAVE_VENDEDOR):
            return "vendedor"
        if hmac.compare_digest(chave, CHAVE_PUBLICA):
            return "publico"
        return None

    def do_GET(self):
        nivel = self.nivel_acesso()
        if nivel is None:
            return self.responder(401, {"erro": "chave inválida"})
        rota = urlparse(self.path).path.strip("/")
        try:
            if rota == "saude":
                return self.responder(200, consultar("SELECT data_referencia() AS data_referencia, CURRENT_TIMESTAMP(6) AS agora")[0])
            if rota == "fila":
                return self.responder(200, consultar_fila_compatibilidade())
            if rota in CONSULTAS_PUBLICAS:
                return self.responder(200, consultar(CONSULTAS_PUBLICAS[rota]))
            if rota.startswith("cenario/") and rota.split("/", 1)[1] in CENARIOS:
                return self.responder(200, consultar_cenario(rota.split("/", 1)[1], 25000.00))
            if rota == "testar-regras":
                return self.responder(200, testar_regras())
            if nivel == "vendedor":
                if rota in CONSULTAS_VENDEDOR:
                    return self.responder(200, consultar(CONSULTAS_VENDEDOR[rota]))
                encontrado = re.fullmatch(r"painel/lead/(\d{1,10})", rota)
                if encontrado:
                    id_atendimento = int(encontrado.group(1))
                    return self.responder(200, {nome: consultar(sql, (id_atendimento,))
                                                for nome, sql in DETALHE_LEAD.items()})
            return self.responder(404, {"erro": "rota inexistente"})
        except pymysql.MySQLError:
            return self.responder(500, {"erro": "falha no banco"})

    def do_POST(self):
        nivel = self.nivel_acesso()
        if nivel is None:
            return self.responder(401, {"erro": "chave inválida"})
        rota = urlparse(self.path).path.strip("/")
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            tamanho = -1
        if not 0 < tamanho <= TAMANHO_MAXIMO_CORPO:
            return self.responder(413, {"erro": "corpo ausente ou grande demais"})
        try:
            dados = json.loads(self.rfile.read(tamanho))
            if not isinstance(dados, dict):
                raise ValueError
        except ValueError:
            return self.responder(400, {"erro": "JSON inválido"})
        try:
            if rota in ("cadastro/orcamento", "cadastro/contato"):
                if not dentro_do_limite(self.headers.get("X-Cliente-IP", "desconhecido")):
                    return self.responder(429, {"erro": "Muitos envios seguidos. Tente de novo em alguns minutos."})
                funcao = cadastro_orcamento if rota == "cadastro/orcamento" else cadastro_contato
                return self.responder(201, {"protocolo": funcao(dados)})
            if nivel == "vendedor" and rota in ("login/permitido", "login/falhou"):
                ip = texto(dados, "ip", 1, 64)
                if rota == "login/falhou":
                    registrar_falha_login(ip)
                    return self.responder(200, {"ok": True})
                permitido = login_permitido(ip)
                return self.responder(200 if permitido else 429, {"ok": permitido})
            if nivel == "vendedor":
                resultado = acao_vendedor(rota, dados)
                if resultado is not None:
                    return self.responder(200, {"ok": True, "id": resultado})
            return self.responder(404, {"erro": "rota inexistente"})
        except DadoInvalido as erro:
            return self.responder(422, {"erro": str(erro)})
        except pymysql.MySQLError as erro:
            estado = getattr(erro, "sqlstate", None)
            mensagem = str(erro.args[-1]) if erro.args else str(erro)
            if estado == "45000":
                if nivel == "publico":
                    return self.responder(422, {"erro": "Não foi possível registrar. Confira os dados e tente de novo."})
                return self.responder(422, {"erro": mensagem, "restricao": None})
            return self.responder(500, {"erro": "falha no banco"})

    def log_message(self, formato, *args):
        print("%s - %s" % (self.address_string(), formato % args), flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
