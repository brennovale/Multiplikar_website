# Site e banco de dados do projeto

## Origem acadêmica

O banco de dados foi desenvolvido no trabalho da disciplina de Modelagem de Dados sobre a Multiplikar Automóveis. Sua integração ao site permite aplicar os processos modelados à interface da mesma organização. Na entrega de Desenvolvimento Frontend para Web, essa integração é complementar ao trabalho de HTML, CSS e JavaScript.

O modelo, os scripts SQL, as instruções de execução e as evidências do trabalho de banco estão no [repositório de Modelagem de Dados](https://github.com/andreyveloso/modelagem-banco-multiplikar-automoveis). A pasta `servidor/` deste site reúne os componentes de integração e a documentação correspondente.

## Arquitetura

O sistema usa MySQL 8.4. O navegador acessa o site e a API Python; somente a API se conecta ao banco. A API usa PyMySQL, consultas fixas e procedures para gravações.

Navegador → site na Vercel → funções de `api/` → API Python → MySQL 8.4

A API recebe conexões por variáveis de ambiente, fixa o fuso da sessão e não recebe SQL arbitrário do cliente. O banco deve escutar somente em 127.0.0.1. O ambiente local de demonstração usa 127.0.0.1:33306; ajuste host e porta conforme a instalação.

| Variável | Uso |
|---|---|
| MULTIPLIKAR_MYSQL_LEITURA | Consultas públicas, painel e testes de regras |
| MULTIPLIKAR_MYSQL_DEMO | Operações negativas revertidas |
| MULTIPLIKAR_MYSQL_CADASTRO | Procedures de cadastro de lead e mensagem |
| MULTIPLIKAR_MYSQL_CRM | Procedures do painel do vendedor |
| MULTIPLIKAR_API_KEY | Chave pública HTTP |
| MULTIPLIKAR_API_KEY_VENDEDOR | Chave do vendedor HTTP |

app.sql cria estruturas auxiliares no schema app. As contas devem usar caching_sha2_password e privilégios separados: leitura, testes revertidos, cadastro e CRM. app_definer não deve permitir login e recebe apenas os privilégios exigidos pelas rotinas SQL SECURITY DEFINER.

## Conferência

verificar-banco.py usa as variáveis de ambiente para executar consultas fixas públicas e do painel, verificar cenários e confirmar recusas de regras.

~~~sh
python servidor/verificar-banco.py
~~~

A execução reproduzível do schema e da massa está descrita no README do repositório de modelagem. O registro de validação da API está em BANCO-DE-DADOS-verificacao.md.

## Origem dos dados

| Rota ou formulário | Origem MySQL |
|---|---|
| estoque | app.vw_veiculo_situacao_publica |
| propostas, simulacoes, previsao, fila | vw_proposta_comparativo, vw_simulacao_parcela, vw_previsao_caixa, vw_fila_acoes |
| cenario | Procedure fn_previsao_caixa_cenario |
| orçamento e contato | app.cadastrar_lead e app.registrar_mensagem |
| CRM | Procedures de revisão, interação, classificação, desfecho e leitura |

O navegador não se conecta ao banco. A API executa consultas fixas e valida os parâmetros recebidos.
