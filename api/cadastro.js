// Função da Vercel: recebe os formulários de orçamento e contato e grava no banco
// pela API do servidor. A chave fica só nas variáveis de ambiente da Vercel.
const FORMULARIOS = new Set(['orcamento', 'contato']);

// Resposta para quem enviou sem JavaScript: página simples com o resultado e link de volta.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function voltar(res, formulario, ok, texto) {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  return res.status(ok ? 200 : 422).send(`<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multiplikar Automóveis — ${ok ? 'Solicitação recebida' : 'Envio não concluído'}</title>
<link rel="stylesheet" href="/assets/css/design-system.css"></head>
<body><main class="conteiner-principal"><section>
<h1>${ok ? 'Solicitação recebida' : 'Não foi possível enviar'}</h1>
<p>${esc(texto)}</p>
<p><a class="btn btn-primario" href="/pages/${formulario}.html">Voltar ao formulário</a></p>
</section></main></body></html>`);
}
const SUCESSO = p => `Protocolo nº ${p}. Um consultor da Multiplikar vai entrar em contato em breve.`;

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const formulario = String(req.query.f || '');
  if (req.method !== 'POST' || !FORMULARIOS.has(formulario)) {
    return res.status(405).json({ erro: 'método ou formulário inválido' });
  }
  // Só aceita envios vindos do próprio site.
  const origem = req.headers.origin;
  if (origem && new URL(origem).host !== req.headers.host) {
    return res.status(403).json({ erro: 'origem não permitida' });
  }
  const dados = typeof req.body === 'object' && req.body !== null ? req.body : {};
  const semJavascript = !String(req.headers['content-type'] || '').includes('application/json');

  // Campo armadilha preenchido: é robô. Responde como se tivesse dado certo e não grava nada.
  if (dados.site_empresa) {
    return semJavascript ? voltar(res, formulario, true, SUCESSO(0)) : res.status(201).json({ protocolo: 0 });
  }
  delete dados.site_empresa;

  try {
    const resposta = await fetch(`${process.env.MULTIPLIKAR_API_URL}/cadastro/${formulario}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.MULTIPLIKAR_API_KEY,
        'X-Cliente-IP': String(req.headers['x-real-ip'] || req.headers['x-forwarded-for'] || '').split(',')[0].trim(),
      },
      body: JSON.stringify(dados),
      signal: AbortSignal.timeout(10000),
    });
    const corpo = await resposta.json();
    if (semJavascript) {
      return voltar(res, formulario, resposta.ok, resposta.ok ? SUCESSO(corpo.protocolo) : (corpo.erro || 'Confira os dados e tente de novo.'));
    }
    return res.status(resposta.status).json(corpo);
  } catch (erro) {
    if (semJavascript) return voltar(res, formulario, false, 'Sistema da loja fora do ar no momento. Ligue para (11) 2647-4000.');
    return res.status(503).json({ erro: 'Sistema da loja fora do ar no momento.' });
  }
};
