(function () {
  var f = document.getElementById('matrice'); if (!f) return;
  var medio = +f.dataset.medio, alto = +f.dataset.alto;
  function calc() {
    var tot = 0, crit = false;
    f.querySelectorAll('input[type=radio]:checked').forEach(function (r) { var p = +r.dataset.p; tot += p; if (p >= 100) crit = true; });
    var max = +document.getElementById('a-max').textContent, pct = max ? Math.round(tot / max * 100) : 0;
    var liv = crit ? 'CRITICO' : pct >= alto ? 'ALTO' : pct >= medio ? 'MEDIO' : 'BASSO';
    document.getElementById('a-tot').textContent = tot; document.getElementById('a-pct').textContent = pct;
    var l = document.getElementById('a-liv'); l.textContent = liv; l.className = 'puma-tag puma-liv-' + liv.toLowerCase();
  }
  f.addEventListener('change', calc); calc();
})();
