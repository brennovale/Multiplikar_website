(() => {
  const botao = document.querySelector('[data-controle-tema]');
  if (!botao) return;

  const rotulo = botao.querySelector('[data-rotulo-tema]');
  const aplicarTema = (escuro) => {
    document.body.classList.toggle('tema-escuro', escuro);
    botao.setAttribute('aria-pressed', String(escuro));
    botao.setAttribute('aria-label', escuro ? 'Ativar tema claro' : 'Ativar tema escuro');
    rotulo.textContent = escuro ? 'Modo claro' : 'Modo escuro';
    botao.querySelector('[aria-hidden="true"]').textContent = escuro ? '\u2600' : '\u263e';
  };

  try { aplicarTema(localStorage.getItem('multiplikar-tema') === 'escuro'); }
  catch { aplicarTema(false); }

  botao.addEventListener('click', () => {
    const escuro = !document.body.classList.contains('tema-escuro');
    aplicarTema(escuro);
    try { localStorage.setItem('multiplikar-tema', escuro ? 'escuro' : 'claro'); }
    catch { /* A escolha permanece apenas nesta navegação se o armazenamento falhar. */ }
  });
})();
