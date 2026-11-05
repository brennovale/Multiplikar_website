# Relatório dos validadores — Entrega 2

**Data:** 5 de novembro de 2026  
**Site publicado:** https://multiplikar-web.vercel.app/

## HTML

As onze páginas HTML do projeto foram enviadas ao [W3C Nu HTML Checker](https://validator.w3.org/nu/) individualmente.

| Arquivo | Erros | Avisos |
|---|---:|---:|
| `index.html` | 0 | 0 |
| `pages/avaliacao.html` | 0 | 0 |
| `pages/compra-veiculos.html` | 0 | 0 |
| `pages/consignacao.html` | 0 | 0 |
| `pages/contato.html` | 0 | 0 |
| `pages/estoque.html` | 0 | 0 |
| `pages/financiamento.html` | 0 | 0 |
| `pages/garantia.html` | 0 | 0 |
| `pages/orcamento.html` | 0 | 0 |
| `pages/sistema.html` | 0 | 0 |
| `pages/vendas.html` | 0 | 0 |

## CSS

O arquivo `assets/css/design-system.css` foi verificado pelo [W3C CSS Validation Service](https://jigsaw.w3.org/css-validator/) com o perfil CSS3 + SVG (`css3svg`).


## Revalidação responsiva — 5 de novembro de 2026

Após os ajustes responsivos, `pages/compra-veiculos.html`, `pages/consignacao.html`, `pages/avaliacao.html`, `pages/financiamento.html` e `pages/vendas.html` foram revalidados no Nu Html Checker e todos validaram.

A folha de estilos publicada foi verificada novamente com o perfil CSS3 + SVG: **0 erros e 13 avisos**. Os avisos são extensões de fornecedor e declarações com variáveis CSS que o validador não consegue verificar estaticamente. O perfil SVG é necessário porque a folha aplica a propriedade `fill` aos ícones SVG. O [manual do validador](https://jigsaw.w3.org/css-validator/manual.html) descreve os perfis disponíveis.

O resultado desta revalidação está em `docs/evidencias/revalidacao-w3c-responsiva-2026-11-05.json`.

O retorno completo da conferência original está em `docs/evidencias/validacao-w3c.json`.

## Reprodução

Os validadores são serviços online e podem mudar. Para reproduzir a conferência, abra cada arquivo HTML no Nu HTML Checker usando “Validate by File Upload”; depois envie `assets/css/design-system.css` ao CSS Validation Service usando “Validate by file upload”. Salve capturas da tela dos resultados junto da entrega caso o professor exija comprovantes visuais.

## Conferência final da entrega

As onze páginas foram novamente enviadas ao Nu Html Checker após a inclusão do botão acessível de navegação, e todas validaram. O exemplo `design-system/exemplo.html` também validou. O resumo está em [validacao-html-entrega-final.json](evidencias/validacao-html-entrega-final.json); os retornos individuais estão na pasta `evidencias/w3c-final/`.

O CSS da publicação final foi novamente validado: zero erros e treze avisos. O retorno está em [validacao-css-entrega-final.json](evidencias/validacao-css-entrega-final.json).
