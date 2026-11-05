#!/usr/bin/env python3
"""Verifica consultas e procedimentos da API usando a conexao MySQL do ambiente."""
import api


def executar(rotulo, fn):
    try:
        resultado = fn()
        print(f"PASS {rotulo}: {len(resultado) if isinstance(resultado, list) else 'ok'}")
        return resultado
    except Exception as erro:
        raise SystemExit(f"FAIL {rotulo}: {type(erro).__name__}: {erro}") from erro


for nome, dsn in [("leitura", api.DSN_LEITURA), ("demo", api.DSN_DEMO),
                  ("cadastro", api.DSN_CADASTRO), ("crm", api.DSN_CRM)]:
    executar(f"conexao MySQL {nome}", lambda dsn=dsn: api.conectar(dsn).close() or [])

for rota, sql in api.CONSULTAS_PUBLICAS.items():
    executar(f"GET {rota}", lambda sql=sql: api.consultar(sql))
for rota, sql in api.CONSULTAS_VENDEDOR.items():
    executar(f"GET {rota}", lambda sql=sql: api.consultar(sql))

lead = executar("GET painel/leads", lambda: api.consultar(api.CONSULTAS_VENDEDOR["painel/leads"]))
if lead:
    id_atendimento = lead[0]["id_atendimento"]
    for parte, sql in api.DETALHE_LEAD.items():
        executar(f"GET painel/lead/{id_atendimento}/{parte}",
                 lambda sql=sql: api.consultar(sql, (id_atendimento,)))

for cenario in api.CENARIOS:
    executar(f"GET cenario/{cenario}", lambda cenario=cenario: api.consultar_cenario(cenario, 25000.00))

regras = executar("GET testar-regras", api.testar_regras)
if not regras or not all(r["recusado"] for r in regras):
    raise SystemExit("FAIL testar-regras: alguma operacao negativa foi aceita ou falhou fora da regra esperada")
print(f"Resultado: PASS; {len(regras)} testes negativos recusados pelas regras do banco.")
