"""Gera a vitrine de index.html e de pages/estoque.html a partir do banco de dados.

Lê os veículos com situação DISPONIVEL (view vw_veiculo_situacao do projeto), com o
preço anunciado da entrada vigente e a quilometragem da avaliação, e escreve os cartões
e as tabelas em HTML puro entre os marcadores <!-- BANCO:... --> das páginas.
Só entram carros que têm foto em assets/img/estoque/<marca-modelo-ano>.jpg.

Uso (com o banco multiplikar carregado, inclusive sql/extensao/06-estoque-loja.sql):
  python servidor/gerar-vitrine.py --dsn "host=127.0.0.1 port=3306 user=api_leitura password=... database=multiplikar"
Requer PyMySQL; a conexão recebe os parâmetros MySQL pelo argumento --dsn.
"""
import argparse
import html
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SQL = """
SELECT s.id_veiculo, s.marca, s.modelo, s.ano_modelo, s.cor, s.combustivel, s.cambio,
       s.categoria_comercial, e.preco_anunciado, a.quilometragem
FROM vw_veiculo_situacao s
JOIN LATERAL (SELECT x.* FROM entrada x WHERE x.id_veiculo = s.id_veiculo
              ORDER BY x.data_entrada DESC, x.id_entrada DESC LIMIT 1) e ON true
JOIN avaliacao a ON a.id_avaliacao = e.id_avaliacao
WHERE s.situacao_atual = 'DISPONIVEL'
ORDER BY s.ano_modelo DESC, e.preco_anunciado DESC
"""
CAMBIO = {"Automatico": "Automático", "Semiautomatico": "Semiautomático", "Manual": "Manual"}
QTD_DESTAQUE = 6


def slug(*partes):
    texto = unicodedata.normalize("NFKD", " ".join(map(str, partes))).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def brl(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def km(valor):
    return f"{valor:,}".replace(",", ".") + " km"


def cartao(v, prefixo, recuo, rotulo_botao):
    e = lambda t: html.escape(str(t))
    nome = f"{v['marca']} {v['modelo']}"
    linhas = [
        '<article class="card-veiculo">',
        '  <div class="card-midia">',
        f'    <img src="{prefixo}assets/img/estoque/{v["foto"]}" alt="{e(nome)} {v["ano_modelo"]} cor {e(v["cor"].lower())}" class="card-foto" width="800" height="600" loading="lazy">',
        '    <span class="selo-card">Laudo Aprovado</span>',
        '  </div>',
        '  <div class="card-corpo">',
        f'    <h3 class="card-titulo">{e(nome)} — {v["ano_modelo"]}</h3>',
        f'    <p class="card-detalhes">{km(v["quilometragem"])} &bull; {e(v["cor"])} &bull; {e(CAMBIO.get(v["cambio"], v["cambio"]))} &bull; {e(v["combustivel"])}</p>',
        f'    <p class="card-preco">{brl(v["preco_anunciado"])}</p>',
        f'    <a href="{prefixo}pages/orcamento.html" class="btn btn-primario card-acao">{rotulo_botao}</a>' if prefixo == ""
        else f'    <a href="orcamento.html" class="btn btn-primario card-acao">{rotulo_botao}</a>',
        '  </div>',
        '</article>',
    ]
    return "\n".join(recuo + l for l in linhas)


def linha_tabela(v, recuo, marca_th, com_combustivel=True):
    e = lambda t: html.escape(str(t))
    celula_marca = f'<th scope="row">{e(v["marca"])}</th>' if marca_th else f'<td>{e(v["marca"])}</td>'
    return (f"{recuo}<tr>{celula_marca}<td>{e(v['modelo'])}</td><td>{v['ano_modelo']}</td><td>{e(v['cor'])}</td>"
            f"<td>{km(v['quilometragem'])}</td>" + (f"<td>{e(v['combustivel'])}</td>" if com_combustivel else "") +
            f"<td>{e(CAMBIO.get(v['cambio'], v['cambio']))}</td><td>{brl(v['preco_anunciado'])}</td><td>Disponível</td></tr>")


def substituir(texto, marcador, conteudo, recuo):
    padrao = re.compile(rf"(<!-- BANCO:{marcador} -->\r?\n).*?(\r?\n{re.escape(recuo)}<!-- /BANCO:{marcador} -->)", re.S)
    novo, n = padrao.subn(lambda m: m.group(1) + conteudo + m.group(2), texto)
    if n != 1:
        raise SystemExit(f"marcador {marcador} não encontrado (ou repetido)")
    return novo


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--dsn", required=True)
    a = arg.parse_args()
    import pymysql
    params = dict(item.split("=", 1) for item in a.dsn.split())
    params["port"] = int(params.get("port", 3306))
    params["charset"] = "utf8mb4"
    with pymysql.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL)
            nomes = [c[0] for c in cur.description]
            carros = [dict(zip(nomes, linha)) for linha in cur.fetchall()]
    pasta = os.path.join(RAIZ, "assets", "img", "estoque")
    for v in carros:
        v["foto"] = slug(v["marca"], v["modelo"], v["ano_modelo"]) + ".jpg"
    com_foto = [v for v in carros if os.path.exists(os.path.join(pasta, v["foto"]))]
    destaque = com_foto[:QTD_DESTAQUE]

    p = os.path.join(RAIZ, "pages", "estoque.html")
    s = open(p, encoding="utf-8", newline="").read()
    s = substituir(s, "tabela", "\n".join(linha_tabela(v, "          ", True) for v in com_foto), "          ")
    s = substituir(s, "total", f'            <td colspan="9">Total: {len(com_foto)} veículos disponíveis no banco de dados da loja.</td>', "            ")
    s = substituir(s, "fichas", "\n\n".join(cartao(v, "../", "      ", "Solicitar Orçamento") for v in com_foto), "      ")
    open(p, "w", encoding="utf-8", newline="").write(s)

    p = os.path.join(RAIZ, "index.html")
    s = open(p, encoding="utf-8", newline="").read()
    s = substituir(s, "destaques", "\n\n".join(cartao(v, "", "        ", "Solicitar Proposta") for v in destaque), "        ")
    s = substituir(s, "tabela", "\n".join(linha_tabela(v, "            ", False, False) for v in destaque), "            ")
    open(p, "w", encoding="utf-8", newline="").write(s)
    print(f"{len(carros)} disponíveis no banco, {len(com_foto)} com foto; {len(destaque)} em destaque na página inicial.")


if __name__ == "__main__":
    main()
