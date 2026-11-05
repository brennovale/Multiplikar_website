# Revisão responsiva

**Projeto:** Multiplikar Automóveis  
**Data:** 5 de novembro de 2026  
**Escopo:** revisão do HTML e CSS local com conferência no portal do Maestri.

## Resultado

**Resultado:** as ocorrências de empilhamento do cabeçalho e rolagem horizontal identificadas na revisão foram corrigidas. A página inicial foi conferida em 320, 340, 341, 360, 390, 768, 992, 1024, 1280 e 1440 px. As 11 páginas foram conferidas em 320 px.

| Área | Evidência no código | Resultado |
| --- | --- | --- |
| Viewport | As 11 páginas têm `meta name="viewport"` configurada para a largura do dispositivo. | Adequado |
| Navegação | Menu recolhido até 991 px, com botão de 44 × 44 px; navegação horizontal a partir de 992 px. Em 992–1280 px a navegação ocupa uma linha abaixo do logo e dos controles. | Adequado; sem sobreposição nem rolagem horizontal |
| Cabeçalho estreito | Em 320 px a logo tinha 64 px de altura e ficava numa linha separada do controle de tema. | Corrigido: logo reduzida para 52 px até 340 px; logo e tema agora alinham na mesma linha |
| Vitrine | Grade de veículos com uma coluna na base, duas a partir de 768 px e três a partir de 1280 px. | Adequado |
| Mídia | Imagens limitadas à largura disponível; vídeo configurado com largura fluida e altura automática. | Adequado |
| Tabelas | Tabelas longas usam contêineres com rolagem horizontal. | Adequado; os contêineres foram adicionados também às tabelas de Compra de Veículos, Consignação, Avaliação, Financiamento e Vendas |
| Toque | Links da navegação e controle de tema têm altura/largura mínima de 44 px. | Adequado no CSS |

## Conferência no navegador

O portal `Multiplikar QA` foi usado para conferir a versão local e a publicação. Em 320 px, o `scrollWidth` correspondeu à largura visível nas 11 páginas locais e nas páginas públicas de tabelas largas. Na página inicial, também não houve rolagem horizontal nas demais larguras listadas acima. Os controles de tema e menu mantiveram pelo menos 44 px de área de toque, e as tabelas largas continuam roláveis dentro do próprio contêiner.

O ajuste final do cabeçalho foi confirmado visualmente em 320 px: logo e controle de tema ficam lado a lado; o botão do menu fica na linha seguinte. O desktop mantém o cabeçalho sem sobreposição. Capturas da produção: [celular 320 px](evidencias/responsivo-mobile-320.png) e [desktop 1440 px](evidencias/responsivo-desktop-1440.png). A revisão não percorreu cada página interna em todos os tamanhos de tablet e desktop.

## Arquivos alterados

- `assets/css/design-system.css`: redução localizada da logo em telas de até 340 px.
- `pages/compra-veiculos.html`, `pages/consignacao.html`, `pages/avaliacao.html`, `pages/financiamento.html` e `pages/vendas.html`: tabelas largas envolvidas em contêiner rolável.

## Arquivos inspecionados

- `assets/css/design-system.css`: breakpoints, menu, grades, imagens, mídia, tabelas e tamanho mínimo de toque.
- `index.html` e as dez páginas de `pages/`: meta viewport, presença dos controles e classes compartilhadas.

## Acessibilidade do cabeçalho

O controle móvel é um botão nativo com nome acessível, `aria-controls` e `aria-expanded`. A abertura e o fechamento foram testados com Enter no navegador, mantendo a largura da página em 360 px. Escape retorna o foco ao controle quando usado dentro do menu. No tema escuro, as superfícies da barra superior e do rodapé mantêm fundo escuro; textos das ações usam cor escura sobre fundos claros. O verde de destaque no tema claro foi ajustado para #008746 para melhorar o contraste com texto branco.

Essas verificações cobrem os componentes descritos e não representam certificação completa de conformidade WCAG.
