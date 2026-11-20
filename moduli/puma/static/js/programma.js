// Programmazione guidata degli addestramenti (e registrazione individuale): elenchi collegati tra loro.
//  area corsi → corsi dell'area · località → punti sulla mappa · organizzatore → centro della mappa · squadre già usate disattivate
(function () {
  var f = document.getElementById('prog') || document.getElementById('indiv'); if (!f) return;
  var area = f.querySelector('#area'), liv = f.querySelector('#liv');
  function filtra(reset) {
    if (!area || !liv) return;
    var a = area.value, n = 0, unico = null;
    Array.prototype.forEach.call(liv.options, function (o) {
      if (!o.value) { o.textContent = a ? 'Scegli il corso…' : "Scegli prima l'area…"; return; }
      var vis = !!a && o.dataset.s === a; o.hidden = !vis; o.disabled = !vis; if (vis) { n++; unico = o; }
    });
    if (reset || (liv.selectedOptions[0] && liv.selectedOptions[0].disabled)) liv.value = '';
    if (n === 1 && !liv.value) liv.value = unico.value;
    liv.dispatchEvent(new Event('change'));
    squadre();
  }
  if (area) { area.addEventListener('change', function () { filtra(true); }); filtra(false); }

  // orari: la fine sempre dopo l'inizio
  var oi = f.querySelector('#ora_inizio'), of = f.querySelector('#ora_fine');
  if (oi && of) {
    function orari() {
      Array.prototype.forEach.call(of.options, function (o) { o.disabled = o.value <= oi.value; });
      if (of.value <= oi.value) { var i = Math.min(oi.selectedIndex + 2, of.options.length - 1); of.selectedIndex = i; }
    }
    oi.addEventListener('change', orari); orari();
  }

  // squadre già usate quel giorno per quell'area
  var team = f.querySelector('#team'), data = f.querySelector('#data');
  function squadre() {
    if (!team || !data || !area || !f.dataset.team) return;
    fetch(f.dataset.team + '?data=' + encodeURIComponent(data.value) + '&area=' + encodeURIComponent(area.value), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (usate) {
        Array.prototype.forEach.call(team.options, function (o) {
          var u = usate.indexOf(o.value) >= 0; o.disabled = u; o.textContent = o.value + (u ? ' (già usata)' : '');
        });
        if (team.selectedOptions[0] && team.selectedOptions[0].disabled) {
          var lib = Array.prototype.find.call(team.options, function (o) { return !o.disabled; }); if (lib) team.value = lib.value;
        }
      }).catch(function () {});
  }
  if (data) data.addEventListener('change', squadre);

  // mappa: centro sull'organizzatore, punti dalla località scelta
  var mapEl = f.querySelector('.puma-map');
  function punto() { return mapEl && mapEl._pumaPunto; }
  var org = f.querySelector('#organizza');
  if (org) org.addEventListener('change', function () {
    var c = (org.selectedOptions[0].dataset.centro || '').split(',').map(Number);
    if (punto() && c.length === 2 && c[0]) punto().map.setView(c, 11);
  });
  var loc = f.querySelector('#localita'), nuova = f.querySelector('#nuova-loc');
  if (loc) loc.addEventListener('change', function () {
    var o = loc.selectedOptions[0], p = punto();
    if (nuova) { nuova.hidden = loc.value !== 'nuova'; var n = nuova.querySelector('input[name=nome]'); if (n) n.required = loc.value === 'nuova'; }
    if (!p || !o || !o.dataset.lat) return;
    p.metti('area', o.dataset.lat, o.dataset.lon, true);
    p.metti('rv', o.dataset.rvlat || null, o.dataset.rvlon || null);
    p.metti('amb', o.dataset.amblat || null, o.dataset.amblon || null);
    [['#rv_descr', o.dataset.rvd], ['#amb_descr', o.dataset.ambd]].forEach(function (x) {
      var s = f.querySelector(x[0]); if (s && x[1] && Array.prototype.some.call(s.options, function (k) { return k.value === x[1]; })) s.value = x[1];
    });
    var r = f.querySelector('input[name=modo][value=area]'); if (r) { r.checked = true; r.dispatchEvent(new Event('change')); }
  });
  squadre();
})();
