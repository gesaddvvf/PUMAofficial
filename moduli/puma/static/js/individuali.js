// Tipologia → categoria (campo nascosto) e manovre previste della tipologia da spuntare (individuali e programmazione dei collettivi).
(function () {
  var liv = document.getElementById('liv'); if (!liv) return;
  var tipo = document.getElementById('tipo'), box = document.getElementById('man');
  function testo(t) { var s = document.createElement('small'); s.textContent = t; return s; }
  function aggiorna() {
    var o = liv.selectedOptions[0];
    if (tipo) tipo.value = (o && o.dataset.s) || '';
    if (!box) return;
    var legenda = box.querySelector('legend'); box.textContent = ''; if (legenda) box.appendChild(legenda);
    if (!liv.value) { box.appendChild(testo('Scegli prima la tipologia.')); return; }
    fetch(liv.dataset.url.replace(/0$/, liv.value), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (r) {
      if (!r.length) { box.appendChild(testo('Nessuna manovra prevista per questa tipologia (si aggiungono importando il foglio Manovre_PREVISTE o da Impostazioni).')); return; }
      var ciclo = null;
      r.forEach(function (x) {
        if (x.ciclo && x.ciclo !== ciclo) { ciclo = x.ciclo; var h = document.createElement('div'); h.className = 'man-ciclo'; h.textContent = x.ciclo; box.appendChild(h); }
        var l = document.createElement('label'); l.className = 'puma-chk';
        var i = document.createElement('input'); i.type = 'checkbox'; i.name = 'manovre'; i.value = x.nome;
        l.appendChild(i); l.appendChild(document.createTextNode(' ' + x.nome + (x.lettera ? ' (' + x.lettera + ')' : '')));
        box.appendChild(l);
      });
    });
  }
  liv.addEventListener('change', aggiorna); if (liv.value) aggiorna();
})();
