// Função da Vercel: repassa a consulta para a API do banco Multiplikar no Umbrel.
// A chave fica só nas variáveis de ambiente da Vercel; o navegador nunca a vê.
const ROTAS = new Set([
  'saude', 'estoque', 'propostas', 'simulacoes', 'previsao', 'fila', 'testar-regras', 'disponiveis',
  'cenario/BASE', 'cenario/BANCO_ATRA_15_DIAS', 'cenario/LEADS_QUENTES_NAO_FECHAM',
]);

module.exports = async (req, res) => {
  const rota = String(req.query.r || '');
  if (!ROTAS.has(rota)) {
    return res.status(400).json({ erro: 'rota inválida' });
  }
  try {
    const resposta = await fetch(`${process.env.MULTIPLIKAR_API_URL}/${rota}`, {
      headers: { 'X-API-Key': process.env.MULTIPLIKAR_API_KEY },
      signal: AbortSignal.timeout(8000),
    });
    const corpo = await resposta.json();
    res.setHeader('Cache-Control', rota === 'testar-regras'
      ? 'no-store'
      : 's-maxage=60, stale-while-revalidate=86400');
    return res.status(resposta.status).json(corpo);
  } catch (erro) {
    return res.status(503).json({ erro: 'banco indisponível no momento' });
  }
};
