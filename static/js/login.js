// Se l'utente scrive anche @vigilfuoco.it (o incolla l'indirizzo completo) il dominio viene tolto: è già mostrato accanto al campo.
(function () {
  var campo = document.getElementById('email');
  if (!campo) return;
  function pulisci() { campo.value = campo.value.replace(/\s+/g, '').replace(/@.*$/, ''); }
  campo.addEventListener('input', pulisci);
  campo.addEventListener('blur', pulisci);
})();

// Stato del collegamento alla rete VVF (posta dipartimentale e WAUC): dice subito se FortiClient VPN è collegata.
(function () {
  var box = document.getElementById('stato-rete');
  if (!box || !window.fetch) return;
  var voci = document.getElementById('stato-rete-voci'), nota = document.getElementById('stato-rete-nota');
  function voce(ok, titolo, testo) {
    var li = document.createElement('li'), b = document.createElement('b'), s = document.createElement('span');
    li.className = ok ? 'ok' : 'ko';
    b.textContent = (ok ? '✔ ' : '✖ ') + titolo;
    s.textContent = ' — ' + testo;
    li.appendChild(b); li.appendChild(s); return li;
  }
  fetch(box.getAttribute('data-url'), { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.modalita === 'prova') return;   // in prova non serve la rete VVF
      box.hidden = false; voci.textContent = '';
      d.controlli.forEach(function (c) { voci.appendChild(voce(c.ok, c.nome, c.ok ? 'raggiungibile' : c.dettaglio)); });
      if (d.tutto_ok) { nota.textContent = 'Sei collegato alla rete VVF: puoi accedere.'; box.className += ' tutto-ok'; }
      else if (d.login_ok) nota.textContent = 'Il login funziona; WAUC non risponde: i dati del profilo andranno completati a mano.';
      else { nota.textContent = 'Non sei collegato alla rete VVF: apri FortiClient VPN, collegati e ricarica questa pagina.'; box.className += ' problema'; }
    })
    .catch(function () {});
})();
