// P.U.M.A. — comportamento dell'intestazione come nel sito gesaddvvf.github.io/PUMA:
// menu laterale (☰), turno e salto in servizio adesso, ricerca nella documentazione.
(function () {
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- menu laterale ---------- */
  function apriMenu(si) {
    document.body.classList.toggle('menu-aperto', si);
    var h = $('hamburger'), m = $('menu');
    if (h) h.setAttribute('aria-expanded', si);
    if (m) m.setAttribute('aria-hidden', !si);
  }
  document.addEventListener('DOMContentLoaded', function () {
    var h = $('hamburger');
    if (h) h.addEventListener('click', function () { apriMenu(!document.body.classList.contains('menu-aperto')); });
    if ($('menu-chiudi')) $('menu-chiudi').addEventListener('click', function () { apriMenu(false); });
    if ($('velo')) $('velo').addEventListener('click', function () { apriMenu(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') apriMenu(false); });
    // la scheda e il pulsante attivi restano visibili anche sul telefono (barre che scorrono di lato)
    Array.prototype.forEach.call(document.querySelectorAll('#nav-buttons .attivo, #schede a.on'), function (a) {
      if (a.scrollIntoView) a.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    });
    window.scrollTo(0, 0);
    aggiornaTurno(); setInterval(aggiornaTurno, 30000);
    filtroDocumenti();
  });

  /* ---------- turno e salto in servizio (stessa sequenza del sito P.U.M.A. e di FireOps) ---------- */
  var SEQUENZA_TURNI = ["A4", "C4", "B4", "B4", "D4", "C4", "C4", "A5", "D4", "D4", "B5", "A5", "A5", "C5", "B5", "B5", "D5", "C5", "C5", "A6", "D5", "D5", "B6", "A6", "A6", "C6", "B6", "B6", "D6", "C6", "C6", "A7", "D6", "D6", "B7", "A7", "A7", "C7", "B7", "B7", "D7", "C7", "C7", "A8", "D7", "D7", "B8", "A8", "A8", "C8", "B8", "B8", "D8", "C8", "C8", "A1", "D8", "D8", "B1", "A1", "A1", "C1", "B1", "B1", "D1", "C1", "C1", "A2", "D1", "D1", "B2", "A2", "A2", "C2", "B2", "B2", "D2", "C2", "C2", "A3", "D2", "D2", "B3", "A3", "A3", "C3", "B3", "B3", "D3", "C3", "C3", "A4", "D3", "D3", "B4", "A4"];
  var GIORNI_CICLO = 32, MS_GIORNO = 864e5;
  var RIFERIMENTO_CICLO = Date.UTC(2026, 0, 26);   // 26/01/2026 00:00 ora di Roma = inizio ciclo (A4)
  function oraRoma(d) {
    var p = {};
    new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
      .formatToParts(d).forEach(function (x) { p[x.type] = x.value; });
    return { y: +p.year, m: +p.month, g: +p.day, h: (+p.hour) % 24, min: +p.minute };
  }
  function turniDelGiorno(y, m, g) {
    var i = (((Math.round((Date.UTC(y, m - 1, g) - RIFERIMENTO_CICLO) / MS_GIORNO)) % GIORNI_CICLO) + GIORNI_CICLO) % GIORNI_CICLO * 3;
    return { notteUscente: SEQUENZA_TURNI[i], giorno: SEQUENZA_TURNI[i + 1], notte: SEQUENZA_TURNI[i + 2] };
  }
  function aggiornaTurno() {
    if (!$('turno-box')) return;
    var r = oraRoma(new Date()), T = turniDelGiorno(r.y, r.m, r.g), min = r.h * 60 + r.min;
    var s = min < 480 ? [T.notteUscente, 'notturno fino alle 08'] : min < 1200 ? [T.giorno, 'diurno 08–20'] : [T.notte, 'notturno 20–08'];
    $('turno-lettera').textContent = s[0].charAt(0);
    $('turno-salto').textContent = s[0].slice(1);
    $('turno-box').title = 'In servizio ora: turno ' + s[0].charAt(0) + ', salto ' + s[0].slice(1) + ' (' + s[1] + ')\nOggi: diurno ' + T.giorno + ' · notturno ' + T.notte;
  }

  /* ---------- documentazione: ricerca per titolo o settore ---------- */
  function norm(t) { return String(t).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function filtroDocumenti() {
    var cerca = $('docs-cerca'), griglia = $('docs-griglia');
    if (!cerca || !griglia) return;
    cerca.addEventListener('input', function () {
      var q = norm(cerca.value.trim()), visibili = 0;
      Array.prototype.forEach.call(griglia.querySelectorAll('.doc-sez'), function (sez) {
        var titoloSez = norm(sez.getAttribute('data-sezione') || ''), n = 0;
        Array.prototype.forEach.call(sez.querySelectorAll('.doc-v'), function (v) {
          var ok = !q || titoloSez.indexOf(q) >= 0 || norm(v.textContent).indexOf(q) >= 0;
          v.hidden = !ok; if (ok) n++;
        });
        sez.hidden = n === 0; visibili += n;
      });
      if ($('docs-vuoto')) $('docs-vuoto').hidden = visibili > 0;
    });
  }
})();
