// Envia os formulários de orçamento e contato para o banco de dados da loja.

// Preenche a lista de veículos com os carros DISPONIVEIS no banco (ou com os dados salvos,
// se o banco estiver fora do ar). O servidor confere de novo a disponibilidade no envio.
document.querySelectorAll('select[data-veiculos-disponiveis]').forEach(function (select) {
  var brl = function (v) { return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }); };
  var categoria = { NOVO: 'novo', SEMINOVO: 'seminovo', USADO: 'usado' };
  var form = select.closest('form');
  var valor = form.querySelector('[name="valor_disponivel"]');
  var aviso = form.querySelector('#limite-valor-disponivel');
  function atualizarLimite() {
    var opcao = select.options[select.selectedIndex];
    var preco = opcao && opcao.dataset.precoAnunciado;
    if (!preco) {
      valor.removeAttribute('max');
      valor.setCustomValidity('');
      aviso.textContent = 'Selecione um veículo para consultar o limite.';
      return;
    }
    var limite = Number(preco);
    valor.max = String(limite);
    valor.step = 'any';
    var excede = valor.value !== '' && Number(valor.value) > limite;
    valor.setCustomValidity(excede ? 'O valor disponível não pode ser maior que o preço anunciado (' + brl(limite) + ').' : '');
    aviso.textContent = excede ? 'O valor informado supera o preço anunciado (' + brl(limite) + '). Ajuste antes de enviar.' : 'Limite para este veículo: ' + brl(limite) + '.';
  }
  select.addEventListener('change', atualizarLimite);
  valor.addEventListener('input', atualizarLimite);
  fetch('/api/multiplikar?r=disponiveis')
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .catch(function () {
      document.getElementById('veiculos-origem').textContent = 'Banco fora do ar: lista dos últimos dados salvos. A disponibilidade é confirmada no envio.';
      return fetch('../assets/dados/multiplikar-snapshot.json')
        .then(function (r) { return r.json(); })
        .then(function (d) { return d.rotas.disponiveis || []; });
    })
    .then(function (lista) {
      var nenhum = select.querySelector('option[value="nenhum"]');
      lista.forEach(function (v) {
        var opcao = document.createElement('option');
        opcao.value = v.id_veiculo;
        opcao.dataset.precoAnunciado = v.preco_anunciado == null ? '' : String(v.preco_anunciado);
        opcao.textContent = v.marca + ' ' + v.modelo + ' ' + v.ano_modelo + ' · ' + v.cor + ' · ' +
          (categoria[v.categoria_comercial] || v.categoria_comercial) +
          (v.preco_anunciado ? ' · ' + brl(v.preco_anunciado) : '');
        select.insertBefore(opcao, nenhum);
      });
      atualizarLimite();
    });
});
// Sem JavaScript o formulário continua funcionando: o navegador envia direto para /api/cadastro.
document.querySelectorAll('form.form-cadastro').forEach(function (form) {
  var status = form.querySelector('.status-envio');
  var botao = form.querySelector('button[type="submit"]');

  function mostrar(texto, tipo) {
    status.textContent = texto;
    status.className = 'status-envio ' + tipo;
  }

  form.addEventListener('submit', function (evento) {
    evento.preventDefault();
    var dados = Object.fromEntries(new FormData(form));
    botao.disabled = true;
    mostrar('Enviando...', '');
    fetch('/api/cadastro?f=' + form.dataset.formulario, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados)
    })
      .then(function (resposta) {
        return resposta.json().then(function (corpo) { return { ok: resposta.ok, corpo: corpo }; });
      })
      .then(function (r) {
        if (r.ok) {
          form.reset();
          mostrar('Recebemos sua solicitação! Protocolo nº ' + r.corpo.protocolo +
            '. Um consultor da Multiplikar vai entrar em contato em breve.', 'sucesso');
        } else {
          mostrar('Não foi possível enviar: ' + (r.corpo.erro || 'tente novamente.'), 'erro');
        }
      })
      .catch(function () {
        mostrar('Não foi possível enviar agora. Tente de novo ou fale com a loja pelo telefone (11) 2647-4000.', 'erro');
      })
      .finally(function () {
        botao.disabled = false;
        status.focus();
      });
  });
});

// Mostra só as seções da opção escolhida (comprar, vender ou trocar). Seção escondida
// também fica desativada: o navegador não exige nem envia os campos dela.
document.querySelectorAll('form.form-cadastro').forEach(function (form) {
  var secoes = form.querySelectorAll('[data-para]');
  if (!secoes.length) return;
  function atualizar() {
    var marcado = form.querySelector('input[name="tipo_atendimento"]:checked');
    var tipo = marcado ? marcado.value : '';
    secoes.forEach(function (secao) {
      var ativa = tipo !== '' && secao.dataset.para.split(' ').indexOf(tipo) !== -1;
      secao.hidden = !ativa;
      secao.disabled = !ativa;
    });
  }
  form.querySelectorAll('input[name="tipo_atendimento"]').forEach(function (opcao) {
    opcao.addEventListener('change', atualizar);
  });
  form.addEventListener('reset', function () { setTimeout(atualizar, 0); });
  atualizar();
});
