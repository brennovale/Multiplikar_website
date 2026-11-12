# Pesquisa de sites e Design System — Entrega 2

**Projeto:** Multiplikar Automóveis  
**Integrantes:** Andrey Azevedo Veloso e Brenno Lima do Vale  
**Área pesquisada:** revenda de automóveis e veículos seminovos (car dealership / used car dealership)  
**Data da consulta:** 5 de novembro de 2026

## 1. Sites de referência encontrados

A busca foi feita por sites reais de revendas e estoques de seminovos no Brasil. A lista registra dez resultados relevantes encontrados nas consultas web; a ordem abaixo é a ordem de registro nesta pesquisa, não uma alegação de posição fixa no Google. “Busca web” identifica a ferramenta de descoberta, e os links apontam para os sites das organizações.

| # | Site | URL completa | Onde foi encontrado | Elementos relevantes observados |
|---|---|---|---|---|
| 1 | Mais Seminovos (Grupo Mais) | https://www.maiseminovos.com.br/ | Busca web: “websites de seminovos concessionária Brasil” | Busca de veículos, categorias por carroceria, marcas, lojas e compra do carro do cliente. |
| 2 | Localiza Seminovos | https://seminovos.localiza.com/ | Busca web: “site oficial seminovos Brasil” | Vitrine de estoque, filtros por localização, agendamento e avaliação de usado na troca. |
| 3 | Kavak Brasil | https://www.kavak.com/br/seminovos/br | Busca web: “carros usados seminovos Brasil estoque” | Filtros detalhados, ordenação, localização, condições e fichas de veículos. |
| 4 | Seminovos Kia | https://seminovos.kia.com.br/estoque/ | Busca web: “estoque seminovos concessionária” | Vitrine por modelo, preço, quilometragem e concessionária. |
| 5 | Gambatto Seminovos | https://seminovos.gambatto.com.br/estoque/ | Busca web: “estoque de seminovos concessionária” | Filtros por unidade, carroceria, marca, ano, cor, transmissão e combustível. |
| 6 | Carrera Seminovos | https://lp.carrera.com.br/seminovos | Busca web: “concessionária seminovos São Paulo” | Destaque para lojas físicas, contatos e estoque de seminovos. |
| 7 | Grupo Sinal — veículos | https://www.gruposinal.com.br/veiculos | Busca web: “carros usados concessionária São Paulo estoque” | Filtros, lojas, inspeção, garantia, test-drive e financiamento. |
| 8 | AUTOMOB Seminovos | https://seminovos.automob.com.br/ | Busca web: “estoque seminovos multimarcas Brasil” | Estoque multimarcas, filtros extensos por loja, cidade, marca, faixa de preço e ano. |
| 9 | Rodobens Seminovos | https://seminovos.rodobens.com.br/ | Busca web: “carros e caminhões seminovos com garantia” | Busca por marca, categoria, faixa de preço e unidade. |
| 10 | Auto Parvi Seminovos | https://www.autoparvi.com.br/ | Busca web: “revenda seminovos compra e venda Brasil” | Estoque de várias lojas, avaliação online do usado e atendimento de compra. |

## 2. Síntese visual e decisões para o projeto

Nos sites consultados se repetem a busca e os filtros de estoque, fotos dos veículos, chamadas para contato, informações de loja e propostas de troca/financiamento. Os portais de grupos maiores oferecem filtros mais detalhados e concentram várias lojas; isso não é necessário para representar uma revenda de bairro com clareza.

Para a Multiplikar, mantivemos a navegação global, a busca e os cards do estoque, contato visível e chamadas para orçamento. O sistema visual usa azul como cor principal, verde como destaque, fundos neutros, cartões com bordas arredondadas e tipografia do sistema para manter leitura rápida e identidade automotiva. A organização usa Grid nas grades de conteúdo e Flexbox no cabeçalho e componentes; as regras estão centralizadas em `assets/css/design-system.css`.

O cabeçalho foi atualizado com a logo maior e um botão de tema. O tema escuro troca as variáveis de superfícies, textos, bordas e cores de interação; a preferência fica salva no navegador. A implementação está em `assets/js/tema.js` e funciona nas onze páginas HTML.

## 3. Responsividade e acessibilidade

O projeto usa CSS mobile-first, menu em coluna até 991 px e navegação horizontal a partir de 992 px. A grade de veículos apresenta uma coluna no smartphone, duas a partir de 768 px e três a partir de 1280 px. As tabelas largas possuem contêineres com rolagem interna. Formulários utilizam rótulos e validação nativa; links, campos e botões têm estados de foco definidos.

A revisão no navegador cobriu a página inicial entre 320 e 1440 px e as onze páginas em 320 px, sem rolagem horizontal da página. O relatório e as capturas estão em [revisao-responsiva.md](revisao-responsiva.md). A conferência dos valores computados de dez referências está em [sites.md](../design-system/sites.md); valores não medidos não são apresentados como extrações de CSS.

## 4. Uso de IA

O modelo informado pelo grupo foi Codex Luna 6, com nível High, utilizado no Maestri para apoiar pesquisa, documentação e implementação. O briefing orientou o conteúdo da organização; o navegador e os validadores foram usados para conferir as respostas. O processo e a reflexão estão descritos no [README](../README.md).

## 5. Documentação complementar

- [Referências e medições](../design-system/sites.md).
- [Tokens comentados](../design-system/tokens.css) e [exemplo de componentes](../design-system/exemplo.html).
- [Validação HTML e CSS](validacao-w3c.md), com zero erros no CSS publicado e treze avisos informativos.
- [Domínio e publicação](dominio-e-publicacao.md), com três capturas de disponibilidade.
- [Registro fotográfico da entrevista](../assets/img/evidencias/entrevista-multiplikar-2026-10.svg).
- Site publicado: https://multiplikar-web.vercel.app/.
