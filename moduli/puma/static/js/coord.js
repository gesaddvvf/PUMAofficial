// Coordinate in ogni formato: lettura (testo incollato) e scrittura (gradi decimali, GMS, gradi e primi, UTM, MGRS).
// Formati riconosciuti in lettura:
//   44.2225, 12.0408 · 44,2225 12,0408 · N44.2225 E12.0408 · 44.2225N 12.0408E
//   44°13'21"N 12°02'27"E · 44 13 21 N 12 2 27 E · 44°13.35'N 12°2.45'E (gradi e primi)
//   UTM: 32T 712345 4901234 · 33 T 297000 4900000 · E 712345 N 4901234 fuso 32 (senza fuso: quello della mappa)
//   MGRS: 32TQP1234501234 · 32T QP 12345 01234
//   link: Google Maps (@lat,lon · q=lat,lon · !3d…!4d…), OpenStreetMap (mlat/mlon · #map=z/lat/lon), geo:lat,lon
var PUMACoord = (function () {
  var a = 6378137, f = 1 / 298.257223563, k0 = 0.9996, e2 = f * (2 - f), ep2 = e2 / (1 - e2), R = Math.PI / 180;
  var BANDE = 'CDEFGHJKLMNPQRSTUVWX', RIGHE = 'ABCDEFGHJKLMNPQRSTUV', COLONNE = ['ABCDEFGH', 'JKLMNPQR', 'STUVWXYZ'];

  function zona(lon) { return Math.min(60, Math.floor((lon + 180) / 6) + 1); }
  function banda(lat) { return lat < -80 || lat > 84 ? '' : BANDE.charAt(Math.min(19, Math.floor((lat + 80) / 8))); }

  function versoUTM(lat, lon, z) {
    z = z || zona(lon);
    var l0 = ((z - 1) * 6 - 177) * R, p = lat * R, l = lon * R, s = Math.sin(p), c = Math.cos(p), t = Math.tan(p);
    var N = a / Math.sqrt(1 - e2 * s * s), T = t * t, C = ep2 * c * c, A = c * (l - l0);
    var M = a * ((1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 * e2 * e2 / 256) * p - (3 * e2 / 8 + 3 * e2 * e2 / 32 + 45 * e2 * e2 * e2 / 1024) * Math.sin(2 * p)
      + (15 * e2 * e2 / 256 + 45 * e2 * e2 * e2 / 1024) * Math.sin(4 * p) - (35 * e2 * e2 * e2 / 3072) * Math.sin(6 * p));
    var E = k0 * N * (A + (1 - T + C) * Math.pow(A, 3) / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * Math.pow(A, 5) / 120) + 500000;
    var Y = k0 * (M + N * t * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * Math.pow(A, 4) / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * Math.pow(A, 6) / 720));
    if (lat < 0) Y += 10000000;
    return { zona: z, banda: banda(lat), e: E, n: Y };
  }

  function daUTM(z, nord, E, Y) {
    var x = E - 500000, y = nord ? Y : Y - 10000000, l0 = ((z - 1) * 6 - 177) * R;
    var mu = (y / k0) / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 * e2 * e2 / 256)), e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
    var p1 = mu + (3 * e1 / 2 - 27 * Math.pow(e1, 3) / 32) * Math.sin(2 * mu) + (21 * e1 * e1 / 16 - 55 * Math.pow(e1, 4) / 32) * Math.sin(4 * mu)
      + (151 * Math.pow(e1, 3) / 96) * Math.sin(6 * mu) + (1097 * Math.pow(e1, 4) / 512) * Math.sin(8 * mu);
    var s = Math.sin(p1), c = Math.cos(p1), t = Math.tan(p1);
    var N1 = a / Math.sqrt(1 - e2 * s * s), T1 = t * t, C1 = ep2 * c * c, R1 = a * (1 - e2) / Math.pow(1 - e2 * s * s, 1.5), D = x / (N1 * k0);
    var lat = p1 - (N1 * t / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * Math.pow(D, 4) / 24
      + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * Math.pow(D, 6) / 720);
    var lon = l0 + (D - (1 + 2 * T1 + C1) * Math.pow(D, 3) / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * Math.pow(D, 5) / 120) / c;
    return { lat: lat / R, lon: lon / R };
  }

  function versoMGRS(lat, lon) {
    var u = versoUTM(lat, lon), set = (u.zona - 1) % 3;
    var col = COLONNE[set].charAt(Math.floor(u.e / 100000) - 1);
    var riga = RIGHE.charAt((Math.floor(u.n / 100000) + (u.zona % 2 === 0 ? 5 : 0)) % 20);
    function p5(v) { v = Math.floor(v % 100000); return ('00000' + v).slice(-5); }
    return u.zona + u.banda + ' ' + col + riga + ' ' + p5(u.e) + ' ' + p5(u.n);
  }

  function daMGRS(z, b, col, riga, cifre) {
    if (cifre.length % 2) return null;
    var n = cifre.length / 2, mol = Math.pow(10, 5 - n);
    var set = (z - 1) % 3, ci = COLONNE[set].indexOf(col), ri = RIGHE.indexOf(riga);
    if (ci < 0 || ri < 0) return null;
    var E = (ci + 1) * 100000 + (n ? +cifre.slice(0, n) * mol : 0) + (n < 5 ? mol / 2 : 0);
    var r = (ri - (z % 2 === 0 ? 5 : 0) + 20) % 20;
    var Y = r * 100000 + (n ? +cifre.slice(n) * mol : 0) + (n < 5 ? mol / 2 : 0);
    var bi = BANDE.indexOf(b), nord = b >= 'N', latMin = -80 + 8 * bi;
    var minN = versoUTM(latMin, (z - 1) * 6 - 177, z).n;
    if (!nord && latMin === -80) minN = 1100000;
    while (Y < minN - 1) Y += 2000000;
    return daUTM(z, nord, E, Y);
  }

  function ok(p) { return p && isFinite(p.lat) && isFinite(p.lon) && Math.abs(p.lat) <= 90 && Math.abs(p.lon) <= 180 ? { lat: +p.lat, lon: +p.lon } : null; }
  function num(s) { return parseFloat(String(s).replace(',', '.')); }

  function leggi(testo, zonaMappa) {
    var t = String(testo || '').trim(), m;
    if (!t) return null;
    // link e URI
    if ((m = t.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/))) return ok({ lat: +m[1], lon: +m[2] });
    if ((m = t.match(/[?&](?:q|query|ll|daddr|destination|center|sll)=(-?\d+(?:\.\d+)?)(?:,|%2C)\s*(-?\d+(?:\.\d+)?)/i))) return ok({ lat: +m[1], lon: +m[2] });
    if ((m = t.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/))) return ok({ lat: +m[1], lon: +m[2] });
    if ((m = t.match(/mlat=(-?\d+(?:\.\d+)?).*mlon=(-?\d+(?:\.\d+)?)/i))) return ok({ lat: +m[1], lon: +m[2] });
    if ((m = t.match(/#map=\d+\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/))) return ok({ lat: +m[1], lon: +m[2] });
    if ((m = t.match(/^geo:(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i))) return ok({ lat: +m[1], lon: +m[2] });
    var u = t.toUpperCase().replace(/\s+/g, ' ');
    // MGRS
    if ((m = u.replace(/ /g, '').match(/^(\d{1,2})([C-HJ-NP-X])([A-HJ-NP-Z])([A-HJ-NP-V])(\d{0,10})$/))) return ok(daMGRS(+m[1], m[2], m[3], m[4], m[5]));
    // UTM con fuso
    if ((m = u.match(/^(?:UTM\s*)?(\d{1,2})(?:\s*([C-HJ-NP-X])|\s)\s*[,;]?\s*(?:E\s*[:=]?\s*)?(\d{5,7}(?:[.,]\d+)?)\s*(?:M\s*)?(?:E\b)?\s*[,;]?\s*(?:N\s*[:=]?\s*)?(\d{6,8}(?:[.,]\d+)?)\s*(?:M\s*)?(?:N\b)?$/))) {
      var b = m[2] || 'T'; return ok(daUTM(+m[1], b >= 'N', num(m[3]), num(m[4])));
    }
    // UTM «E … N … fuso 32» o solo est/nord (fuso della mappa)
    var fz = u.match(/(?:FUSO|ZONA|ZONE)\s*(\d{1,2})\s*([C-HJ-NP-X])?/);
    var ee = u.match(/\bE(?:ST)?\s*[:=]?\s*(\d{6}(?:[.,]\d+)?)\b/), nn = u.match(/\bN(?:ORD)?\s*[:=]?\s*(\d{7}(?:[.,]\d+)?)\b/);
    if (!ee || !nn) { var d2 = u.replace(/(?:FUSO|ZONA|ZONE)\s*\d{1,2}\s*[C-HJ-NP-X]?/, '').match(/^\s*(\d{6}(?:[.,]\d+)?)\s*[,; ]\s*(\d{7}(?:[.,]\d+)?)\s*$/); if (d2) { ee = [0, d2[1]]; nn = [0, d2[2]]; } }
    if (ee && nn && (fz || zonaMappa)) return ok(daUTM(fz ? +fz[1] : zonaMappa, fz && fz[2] ? fz[2] >= 'N' : true, num(ee[1]), num(nn[1])));
    // gradi decimali, GMS, gradi e primi
    var s = u.replace(/LAT(?:ITUDINE)?|LON(?:GITUDINE)?|LNG/g, ' ').replace(/[°º˚]/g, ' ').replace(/[′’']/g, ' ').replace(/[″"”]/g, ' ');
    s = s.replace(/OVEST/g, 'W').replace(/NORD/g, 'N').replace(/SUD/g, 'S').replace(/EST/g, 'E');
    if (/^\s*-?\d+,\d+\s*[,; ]\s*-?\d+,\d+\s*$/.test(s)) s = s.replace(/(\d),(\d)/g, '$1.$2');
    s = s.replace(/(\d),(\d)/g, function (x, p, q) { return p + '.' + q; }).replace(/[,;]/g, ' ; ');
    var tok = s.match(/-?\d+(?:\.\d+)?|[NSEWO]|;/g) || [], comp = [], cur = null, prefisso = /^[NSEWO]$/.test(tok[0] || '');
    function chiudi() { if (cur && cur.n.length) comp.push(cur); cur = null; }
    tok.forEach(function (x) {
      if (x === ';') { chiudi(); return; }
      if (/^[NSEWO]$/.test(x)) {
        if (prefisso) { chiudi(); cur = { n: [], h: x }; } else { if (!cur) cur = { n: [] }; cur.h = x; chiudi(); }
        return;
      }
      if (!cur) cur = { n: [] };
      if (cur.n.length === 3) { chiudi(); cur = { n: [] }; }
      cur.n.push(x);
    });
    chiudi();
    if (comp.length === 1 && comp[0].n.length >= 2 && !comp[0].h) {   // numeri senza separatori: 2, 4 o 6 numeri
      var v = comp[0].n, h = v.length / 2;
      if (v.length % 2 === 0) comp = [{ n: v.slice(0, h) }, { n: v.slice(h) }];
    }
    if (comp.length !== 2) return null;
    function val(c) {
      var neg = String(c.n[0]).charAt(0) === '-', d = Math.abs(num(c.n[0])), mi = c.n[1] ? num(c.n[1]) : 0, se = c.n[2] ? num(c.n[2]) : 0;
      if (mi >= 60 || se >= 60) return NaN;
      var x = d + mi / 60 + se / 3600;
      return (neg || c.h === 'S' || c.h === 'W' || c.h === 'O') ? -x : x;
    }
    var A = comp[0], B = comp[1], lat, lon;
    if (A.h === 'E' || A.h === 'W' || A.h === 'O' || B.h === 'N' || B.h === 'S') { lat = val(B); lon = val(A); } else { lat = val(A); lon = val(B); }
    if (!A.h && !B.h && Math.abs(lat) > 90 && Math.abs(lon) <= 90) { var tmp = lat; lat = lon; lon = tmp; }
    return ok({ lat: lat, lon: lon });
  }

  function gms(v, pos, negat, primi) {
    var h = v < 0 ? negat : pos; v = Math.abs(v);
    var d = Math.floor(v), m = (v - d) * 60;
    if (primi) return d + '°' + m.toFixed(3) + "'" + h;
    var mi = Math.floor(m), s = (m - mi) * 60;
    if (s >= 59.95) { s = 0; mi += 1; } if (mi >= 60) { mi = 0; d += 1; }
    return d + '°' + ('0' + mi).slice(-2) + "'" + (s < 10 ? '0' : '') + s.toFixed(1) + '"' + h;
  }

  function formati(lat, lon) {
    var u = versoUTM(lat, lon);
    return {
      dd: lat.toFixed(6) + ', ' + lon.toFixed(6),
      gms: gms(lat, 'N', 'S') + ' ' + gms(lon, 'E', 'W'),
      gp: gms(lat, 'N', 'S', true) + ' ' + gms(lon, 'E', 'W', true),
      utm: u.zona + u.banda + ' ' + Math.round(u.e) + ' ' + Math.round(u.n),
      mgrs: versoMGRS(lat, lon)
    };
  }

  return { leggi: leggi, formati: formati, versoUTM: versoUTM, daUTM: daUTM, zona: zona };
})();
if (typeof module !== 'undefined') module.exports = PUMACoord;
