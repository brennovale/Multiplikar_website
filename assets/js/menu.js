(() => {
  const botao = document.querySelector('[data-menu-toggle]');
  const menu = document.getElementById('menu-principal');
  if (!botao || !menu) return;
  const alterar = aberto => {
    menu.classList.toggle('menu-aberto', aberto);
    botao.setAttribute('aria-expanded', String(aberto));
    botao.setAttribute('aria-label', aberto ? 'Fechar menu principal' : 'Abrir menu principal');
  };
  botao.addEventListener('click', () => alterar(botao.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('keydown', evento => {
    if (evento.key === 'Escape') { alterar(false); botao.focus(); }
  });
})();
