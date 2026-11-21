"""Turni VVF (stessa sequenza del sito P.U.M.A., di FireOps e di static/js/puma-sito.js).
Ciclo di 32 giorni dal 26/01/2026 (A4); ogni giorno tre servizi: notte uscente 00-08, diurno 08-20, notturno 20-24.
Il codice (es. «B4») è turno + salto: chi ha quel turno e quel salto è DI SALTO, gli altri del turno sono in servizio."""
import datetime

SEQUENZA = ["A4", "C4", "B4", "B4", "D4", "C4", "C4", "A5", "D4", "D4", "B5", "A5", "A5", "C5", "B5", "B5", "D5", "C5", "C5", "A6", "D5", "D5", "B6", "A6", "A6", "C6", "B6", "B6", "D6", "C6", "C6", "A7", "D6", "D6", "B7", "A7", "A7", "C7", "B7", "B7", "D7", "C7", "C7", "A8", "D7", "D7", "B8", "A8", "A8", "C8", "B8", "B8", "D8", "C8", "C8", "A1", "D8", "D8", "B1", "A1", "A1", "C1", "B1", "B1", "D1", "C1", "C1", "A2", "D1", "D1", "B2", "A2", "A2", "C2", "B2", "B2", "D2", "C2", "C2", "A3", "D2", "D2", "B3", "A3", "A3", "C3", "B3", "B3", "D3", "C3", "C3", "A4", "D3", "D3", "B4", "A4"]
RIFERIMENTO = datetime.date(2026, 1, 26)


def del_giorno(d):
    """(notte uscente 00-08, diurno 08-20, notturno 20-24) del giorno d."""
    i = ((d - RIFERIMENTO).days % 32) * 3
    return SEQUENZA[i], SEQUENZA[i + 1], SEQUENZA[i + 2]


def in_servizio(quando):
    """Codice del turno in servizio a quella data e ora (datetime)."""
    n, g, s = del_giorno(quando.date())
    m = quando.hour * 60 + quando.minute
    return n if m < 480 else g if m < 1200 else s


def stato(turno, salto, quando):
    """'in_turno', 'salto' oppure 'fuori' per la persona (turno A-D, salto 1-8) a quella data e ora."""
    t = (turno or '').strip().upper()[:1]
    sl = ''.join(ch for ch in str(salto or '') if ch.isdigit())
    if t not in 'ABCD' or not t: return None
    c = in_servizio(quando)
    if c[0] != t: return 'fuori'
    return 'salto' if sl and c[1:] == sl else 'in_turno'
