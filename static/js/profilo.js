// Profilo: filtro delle specializzazioni e distaccamenti limitati al comando scelto (sigla provinciale).
(function () {
  var filtro = document.getElementById('filtro-spec'), elenco = document.getElementById('elenco-spec');
  if (filtro && elenco) filtro.addEventListener('input', function () {
    var t = filtro.value.toLowerCase();
    Array.prototype.forEach.call(elenco.children, function (l) { l.hidden = t && l.textContent.toLowerCase().indexOf(t) === -1; });
  });
  var com = document.getElementById('co'), dist = document.getElementById('distaccamento');
  if (com && dist && dist.tagName === 'SELECT') {
    function aggiorna() {
      var o = com.options[com.selectedIndex], sigla = o ? o.getAttribute('data-sigla') : '';
      Array.prototype.forEach.call(dist.options, function (x) {
        var s = x.getAttribute('data-sigla'), nascondi = !!(s && sigla && s !== sigla);
        x.hidden = nascondi; x.disabled = nascondi;
      });
      if (dist.options[dist.selectedIndex] && dist.options[dist.selectedIndex].disabled) dist.value = '';
    }
    com.addEventListener('change', aggiorna); aggiorna();
  }
  // sedi con profilo libero (Trento, Bolzano, Aosta…) e campi personalizzati della sede scelta
  if (com) {
    function sede() {
      var o = com.options[com.selectedIndex], libero = o && o.getAttribute('data-libero') === '1';
      Array.prototype.forEach.call(document.querySelectorAll('.solo-libero'), function (x) { x.hidden = !libero; });
      Array.prototype.forEach.call(document.querySelectorAll('.solo-wauc'), function (x) { x.hidden = libero; });
      Array.prototype.forEach.call(document.querySelectorAll('.campi-sede'), function (x) {
        var vis = x.getAttribute('data-comando') === com.value; x.hidden = !vis;
        Array.prototype.forEach.call(x.querySelectorAll('input,select'), function (i) { i.disabled = !vis; });
      });
    }
    com.addEventListener('change', sede); sede();
  }
})();
