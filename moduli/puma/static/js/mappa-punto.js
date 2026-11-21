// Barra delle mappe P.U.M.A. (dopo puma.js e coord.js):
//  · «Centra su…»: Comandi, Direzioni, CON e SOCAV (poi si sposta la mappa e si sceglie il luogo)
//  · 🎯 Localizzami: posizione del dispositivo (serve https oppure localhost)
//  · ✛ croce al centro della mappa: «Usa la croce» mette il punto lì
//  · casella coordinate: gradi decimali, GMS, gradi e primi, UTM, MGRS, link Google Maps / OpenStreetMap
//  · clic sulla mappa o trascinamento dei segnaposto
// Mappe con data-pick: i punti vanno nei campi #lat/#lon, #rv_lat/#rv_lon, #amb_lat/#amb_lon del modulo (scelta con name=modo).
(function () {
  if (!window.L || !window.PUMACoord) return;
  var NOMI = { area: 'Area addestramento', rv: 'RV elicottero', amb: 'RV ambulanza' };
  var PREF = { area: '', rv: 'rv_', amb: 'amb_' }, KIND = { area: 'area', rv: 'h', amb: 'amb' };
  var sedi = null, attese = [];
  function caricaSedi(url, cb) {
    if (sedi) return cb(sedi);
    attese.push(cb); if (attese.length > 1) return;
    fetch(url, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (r) { sedi = r; attese.forEach(function (f) { f(r); }); })
      .catch(function () { sedi = []; });
  }
  function crea(tag, cls, testo) { var x = document.createElement(tag); if (cls) x.className = cls; if (testo) x.textContent = testo; return x; }

  document.querySelectorAll('.puma-map[data-barra]').forEach(function (el) {
    var map = el._pumaMap; if (!map) return;
    var pick = el.dataset.pick, form = el.closest('form') || document, mk = {};
    var barra = crea('div', 'mp-barra');
    var sel = crea('select', 'mp-sede'); sel.appendChild(new Option('📍 Centra la mappa su un Comando…', ''));
    sel.title = 'Centra la mappa su una sede: poi spostala e scegli il luogo';
    var bLoc = crea('button', 'btn mp-loc', '🎯 Localizzami'); bLoc.type = 'button'; bLoc.title = 'Centra sulla posizione di questo dispositivo';
    barra.appendChild(sel); barra.appendChild(bLoc);
    var testo, bVai, bCroce;
    if (pick) {
      bCroce = crea('button', 'btn mp-usa', '✛ Usa la croce'); bCroce.type = 'button'; bCroce.title = 'Mette il punto al centro della mappa (sotto la croce)';
      barra.appendChild(bCroce);
      var riga = crea('div', 'mp-coord');
      testo = crea('input'); testo.type = 'text'; testo.placeholder = 'Incolla o scrivi le coordinate (44.2225, 12.0408 · 44°13\'21"N 12°02\'27"E · 33T 263634 4900845 · link Google Maps…)';
      testo.setAttribute('aria-label', 'Coordinate');
      bVai = crea('button', 'btn', 'Vai'); bVai.type = 'button';
      riga.appendChild(testo); riga.appendChild(bVai); barra.appendChild(riga);
    }
    el.parentNode.insertBefore(barra, el);
    var mir = crea('div', 'mp-mirino'); mir.setAttribute('aria-hidden', 'true'); el.appendChild(mir);
    var letto = crea('div', 'mp-letto'); el.parentNode.insertBefore(letto, el.nextSibling);
    var msg = crea('div', 'mp-msg'); barra.appendChild(msg);
    function avviso(t) { msg.textContent = t || ''; }

    caricaSedi(el.dataset.sedi, function (r) {
      var gruppi = { comando: 'Comandi', direzione: 'Direzioni regionali', nazionale: 'Livello nazionale' }, og = {};
      r.forEach(function (s) {
        var k = s.tipo || 'comando';
        if (!og[k]) { og[k] = document.createElement('optgroup'); og[k].label = gruppi[k] || k; sel.appendChild(og[k]); }
        var o = new Option(s.nome, s.lat + ',' + s.lon); og[k].appendChild(o);
      });
    });
    sel.addEventListener('change', function () {
      if (!sel.value) return; var p = sel.value.split(',').map(Number);
      map.setView(p, 13); avviso('Sposta la mappa sul luogo e clicca, oppure metti la croce sul punto e premi «Usa la croce».');
    });

    function modo() { var r = form.querySelector('input[name=modo]:checked'); return r ? r.value : (pick === '1' ? 'area' : pick); }
    function campi(m) {   // per nome dentro il modulo (più mappe nella stessa pagina), altrimenti per id
      function c(n) { return form.querySelector('[name="' + n + '"]') || form.querySelector('#' + n); }
      return [c(PREF[m] + 'lat'), c(PREF[m] + 'lon')];
    }
    function mostra() {
      letto.textContent = '';
      if (!pick) return;
      var m = modo(), c = campi(m);
      if (!c[0] || !c[0].value) { letto.appendChild(crea('span', 'muted', (NOMI[m] || 'Punto') + ': non ancora scelto — clicca sulla mappa, usa la croce o scrivi le coordinate.')); return; }
      var lat = +c[0].value, lon = +c[1].value, f = PUMACoord.formati(lat, lon);
      letto.appendChild(crea('b', '', (NOMI[m] || 'Punto') + ': '));
      [['', f.dd], ['GMS', f.gms], ['UTM', f.utm], ['MGRS', f.mgrs]].forEach(function (x) {
        var s = crea('span', 'mp-f'); if (x[0]) s.appendChild(crea('small', '', x[0] + ' ')); s.appendChild(document.createTextNode(x[1])); letto.appendChild(s);
      });
      var a = crea('a', '', 'Google Maps ↗'); a.href = 'https://www.google.com/maps/search/?api=1&query=' + lat.toFixed(6) + ',' + lon.toFixed(6);
      a.target = '_blank'; a.rel = 'noopener'; letto.appendChild(a);
    }
    function metti(m, ll, centra) {
      var c = campi(m); if (!c[0]) return;
      c[0].value = ll.lat.toFixed(6); c[1].value = ll.lng.toFixed(6);
      c[0].dispatchEvent(new Event('change', { bubbles: true }));
      if (mk[m]) mk[m].setLatLng(ll);
      else {
        mk[m] = L.marker(ll, { icon: window.PUMAPin(KIND[m]), draggable: true }).addTo(map).bindTooltip(NOMI[m]);
        mk[m].on('dragend', function () { metti(m, mk[m].getLatLng()); });
      }
      if (centra) map.setView(ll, Math.max(map.getZoom(), 15));
      mostra();
    }
    function togli(m) { var c = campi(m); if (c[0]) { c[0].value = ''; c[1].value = ''; } if (mk[m]) { map.removeLayer(mk[m]); delete mk[m]; } mostra(); }
    el._pumaPunto = { metti: function (m, lat, lon, centra) { if (lat == null || lon == null || lat === '') return togli(m); metti(m, L.latLng(+lat, +lon), centra); }, togli: togli, map: map };

    if (pick) {
      var punti = [];
      Object.keys(PREF).forEach(function (m) {
        var c = campi(m);
        if (c[0] && c[0].value && c[1].value) { metti(m, L.latLng(+c[0].value, +c[1].value)); punti.push([+c[0].value, +c[1].value]); }
      });
      if (punti.length) map.fitBounds(L.latLngBounds(punti).pad(0.4), { maxZoom: 16 });
      map.on('click', function (e) { metti(modo(), e.latlng); avviso(''); });
      bCroce.addEventListener('click', function () { metti(modo(), map.getCenter()); avviso(''); });
      function vai() {
        var z = PUMACoord.zona(map.getCenter().lng), p = PUMACoord.leggi(testo.value, z);
        if (!p) { avviso('Coordinate non riconosciute: prova 44.2225, 12.0408 oppure 33T 263634 4900845.'); return; }
        metti(modo(), L.latLng(p.lat, p.lon), true); avviso(''); testo.value = '';
      }
      bVai.addEventListener('click', vai);
      testo.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); vai(); } });
      form.querySelectorAll('input[name=modo]').forEach(function (r) { r.addEventListener('change', mostra); });
      mostra();
    }

    var cerchio = null;
    bLoc.addEventListener('click', function () {
      if (!navigator.geolocation) { avviso('Questo browser non fornisce la posizione.'); return; }
      if (!window.isSecureContext) { avviso('La posizione funziona solo aprendo PUMA da questo PC (localhost) o in https: usa la croce o le coordinate.'); return; }
      avviso('Ricerca della posizione…');
      navigator.geolocation.getCurrentPosition(function (p) {
        var ll = L.latLng(p.coords.latitude, p.coords.longitude);
        if (cerchio) map.removeLayer(cerchio);
        cerchio = L.circle(ll, { radius: Math.max(p.coords.accuracy, 10), color: '#1e88e5', weight: 1, fillOpacity: 0.15 }).addTo(map);
        map.setView(ll, 16);
        if (pick) { metti(modo(), ll); avviso('Punto messo sulla tua posizione (precisione ±' + Math.round(p.coords.accuracy) + ' m): trascinalo per correggerlo.'); }
        else avviso('Sei qui (precisione ±' + Math.round(p.coords.accuracy) + ' m).');
      }, function (e) { avviso(e.code === 1 ? 'Posizione non autorizzata nel browser.' : 'Posizione non disponibile.'); }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    });
  });
})();
