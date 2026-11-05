# Verificação do site com MySQL

Ambiente local de teste: MySQL Community Server 8.4.13 em 127.0.0.1:33306. A API usa PyMySQL e os schemas multiplikar e app.

## Cadeia SQL

A cadeia local do projeto executa 14 scripts, com 382 verificações PASS e saída zero. A versão do servidor e o sql_mode estão em docs/evidencias/mysql/00-server-info.txt no repositório de modelagem.

## Consultas da API

Na validação local registrada, as consultas públicas retornaram propostas (3), simulações (2), previsão (4), fila (4), veículos disponíveis (30) e dados de saúde (1). O painel retornou leads (13), funcionários (2) e mensagens (2); detalhes e consultas dos registros do lead também foram conferidos.

## Regras e gravações

As verificações negativas cobrem documento repetido, exclusão de histórico, situação fora do domínio, proposta apresentada imutável, alteração indevida de simulação, transição inválida de obrigação, interação histórica e revisão repetida. Cadastro e operações do CRM foram exercitados em transações de teste revertidas.

## Vitrine

| Página | Veículos anunciados | Conferidos |
|---|---:|---:|
| index.html | 6 | 6 |
| pages/estoque.html | 27 | 27 |

O gerador da vitrine consulta as views e tabelas MySQL do modelo. O resultado foi conferido com a massa local.

## Limite desta evidência

Este registro pertence à validação local do trabalho de modelagem de banco de dados. Os números apresentados descrevem aquele ambiente e não constituem um novo teste de produção do site. Os scripts de conferência disponíveis nesta pasta são `verificar-banco.py` e `gerar-vitrine.py`.
