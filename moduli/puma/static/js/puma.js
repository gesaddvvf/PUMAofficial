(function () {
  if (!window.L) return;

  // Simboli: pallino rosso = area addestramento · cerchio verde con H = RV elicottero · cerchio verde con croce = RV ambulanza
  function pin(kind) {
    var cls = { area: 'puma-pin puma-pin-area', h: 'puma-pin puma-pin-h', amb: 'puma-pin puma-pin-a' }[kind];
    return L.divIcon({ className: 'puma-pin-wrap', html: '<i class="' + cls + '">' + (kind === 'h' ? 'H' : '') + '</i>', iconSize: [26, 26], iconAnchor: [13, 13] });
  }
  var NOMI = { area: 'Area addestramento', h: 'RV elicottero', amb: 'RV ambulanza' };
  window.PUMAPin = pin;


  document.querySelectorAll('.puma-map').forEach(function (el) {
    if (el._leaflet_id) return;                 // già inizializzata: salta

    var map = L.map(el, {
      zoomControl: true,
      attributionControl: true
    });
    // centro: la sede di appartenenza (data-centro="lat,lon"), altrimenti l'Italia
    var centro = (el.dataset.centro || '').split(',').map(Number);
    if (centro.length === 2 && isFinite(centro[0]) && isFinite(centro[1]) && centro[0]) map.setView(centro, +(el.dataset.zoom || 11));
    else map.setView([42.5, 12.5], 6);
    el._pumaMap = map;

    L.tileLayer(el.dataset.tiles, {
      maxZoom: 18,
      attribution: '© OpenStreetMap'
    }).addTo(map);

    // --- DIMENSIONE CORRETTA ---
    // Leaflet misura il contenitore una sola volta, quando lo crea.
    // Se in quel momento il layout non è ancora definitivo (form in grid,
    // CSS non applicato, font non caricato) la mappa resta piccola.
    // La facciamo rimisurare dopo il primo layout e ad ogni resize.
    function fixSize() { map.invalidateSize(); }
    requestAnimationFrame(function () {
      requestAnimationFrame(fixSize);           // due rAF: layout sicuramente pronto
    });
    setTimeout(fixSize, 200);                   // ulteriore sicurezza (font/immagini)
    window.addEventListener('resize', fixSize);

    var d = el.dataset;

    // --- SELEZIONE DEI PUNTI: la gestisce mappa-punto.js (croce, coordinate, localizzami, centra su Comando) ---

    // --- MARKER AREA + RV (scheda esistente) ---
    if (d.lat) {
      var area = L.marker([+d.lat, +d.lon], { icon: pin('area') }).addTo(map).bindTooltip(NOMI.area);
      var bounds = [area.getLatLng()];
      if (d.rvlat) {
        L.marker([+d.rvlat, +d.rvlon], { icon: pin('h') }).addTo(map).bindTooltip(NOMI.h);
        bounds.push([+d.rvlat, +d.rvlon]);
      }
      if (d.amblat) {
        L.marker([+d.amblat, +d.amblon], { icon: pin('amb') }).addTo(map).bindTooltip(NOMI.amb);
        bounds.push([+d.amblat, +d.amblon]);
      }
      map.fitBounds(L.latLngBounds(bounds).pad(0.5), { maxZoom: 15 });
    }

    // --- MAPPA LIVE ---
    if (d.live) {
      var layer = L.layerGroup().addTo(map);
      var tb = document.getElementById('tab');

      function load() {
        fetch(d.live)
          .then(function (r) { return r.json(); })
          .then(function (ev) {
            layer.clearLayers();
            if (tb) tb.innerHTML = '';
            var pts = [];

            ev.forEach(function (e) {
              if (e.lat != null && e.lon != null) {
                if (e.rv && e.rv[0] != null) L.marker(e.rv, { icon: pin('h') }).addTo(layer).bindTooltip(NOMI.h);
                if (e.amb && e.amb[0] != null) L.marker(e.amb, { icon: pin('amb') }).addTo(layer).bindTooltip(NOMI.amb);
                L.marker([e.lat, e.lon], { icon: pin('area') })
                  .addTo(layer)
                  .bindPopup(
                    '<a href="' + e.url + '">' + e.tipologia + ' – ' + e.team + '</a>' +
                    '<br>Presenti: ' + e.presenti
                  );
                pts.push([e.lat, e.lon]);
              }

              if (tb) {
                var tr = document.createElement('tr');
                [e.tipologia + ' ' + e.team, e.stato, e.presenti, e.convalidati]
                  .forEach(function (t) {
                    var td = document.createElement('td');
                    td.textContent = t;
                    tr.appendChild(td);
                  });
                tr.onclick = function () { location.href = e.url; };
                tb.appendChild(tr);
              }
            });

            if (tb && !ev.length) {
              tb.innerHTML = '<tr><td colspan="4">Nessun addestramento attivo.</td></tr>';
            }

            // fitBounds solo al primo caricamento, per non "saltare" ogni 30 s
            if (pts.length && !load._fitted) {
              map.fitBounds(pts, { maxZoom: 13, padding: [30, 30] });
              load._fitted = true;
            }
          })
          .catch(function (err) {
            // rete assente o endpoint momentaneamente non raggiungibile:
            // non svuotiamo la mappa, lasciamo l'ultimo stato valido.
            if (window.console) console.warn('PUMA live:', err);
          });
      }

      load();
      setInterval(load, 30000);
    }
  });
})();