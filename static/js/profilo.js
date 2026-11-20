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
})();
