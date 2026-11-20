"""Navigazione di PUMA, uguale al sito gesaddvvf.github.io/PUMA: pulsanti per area nell'intestazione
(Home Page, Attività, Real Time, Documentazione, Report Individuale, Report Collettivo, Area Comando),
schede sotto l'intestazione per le aree con più pagine e menu laterale (☰).

Il nucleo (app.py) chiama contesto() a ogni pagina, anche per le pagine del nucleo (profilo, amministrazione),
così l'intestazione è la stessa ovunque. Colori delle aree: neu grigio, att rosso, rt verde, doc blu, rep giallo, com bianco."""
from flask import url_for, request, g
import db as portale_db

# Schede delle aree con più pagine: (endpoint, argomenti, etichetta, permesso)
# permesso: None = tutti · 'comando' = ROP/ROR/Nazionale/admin · 'gestore' = gestore P.U.M.A. · 'admin' = amministratori
GRUPPI = {
    'attivita': dict(nome='Attività', area='att', ic='📝', schede=[
        ('profilo_view', {}, 'Profilazione individuale', None),
        ('puma.individuali', {}, 'Registrazione attività', None),
        ('puma.interventi', {}, 'Interventi reali', None),
        ('puma.collettivi', {}, 'Pianificazione addestramenti collettivi', None),
        ('puma.attivita', {}, 'Attività formative', None)]),
    'realtime': dict(nome='Real Time', area='rt', ic='⏱️', schede=[
        ('puma.presenze', {}, 'Presenze Odierne', None),
        ('puma.mappa', {}, 'Mappa Real Time', None),
        ('puma.collettivi', {'vista': 'riepilogo', 'quando': 'tutti'}, 'Riepilogo Globale', None),
        ('puma.oggi', {}, 'Registro odierno', None)]),
    'documentazione': dict(nome='Documentazione', area='doc', ic='📚', schede=[
        ('puma.documentazione', {'cat': 'manuali-puma'}, 'Manuali P.U.M.A.', None),
        ('puma.documentazione', {'cat': 'manuali-settore'}, 'Manuali di settore', None),
        ('puma.documentazione', {'cat': 'circolari-settore'}, 'Circolari di settore', None),
        ('puma.archivio', {}, 'Archivio', None)]),
    'comando': dict(nome='Area Comando', area='com', ic='🔓', schede=[
        ('puma.area_comando', {}, 'Panoramica', 'comando'),
        ('puma.report_collettivo', {}, 'Report collettivo', 'comando'),
        ('puma.impostazioni', {}, 'Impostazioni del Comando', 'gestore'),
        ('puma.livelli_utente', {}, 'Livelli utenti', 'admin'),
        ('admin_utenti', {}, 'Utenti e permessi', 'admin'),
        ('admin_organico', {}, 'Organico', 'admin'),
        ('admin_config', {}, 'Configurazione e WAUC', 'admin'),
        ('admin_comandi', {}, 'Schede dei comandi', 'admin'),
        ('admin_audit', {}, 'Registro attività', 'admin')]),
}

# endpoint -> (gruppo o area, titolo della pagina). Il gruppo decide pulsante acceso, schede e colore.
PAGINE = {
    'puma.index': ('home', 'Home Page'),
    'profilo_view': ('attivita', 'Profilazione individuale'), 'profilo_spec_aggiungi': ('attivita', 'Profilazione individuale'),
    'puma.individuali': ('attivita', 'Registrazione attività'), 'puma.interventi': ('attivita', 'Interventi reali'),
    'puma.collettivi': ('attivita', 'Pianificazione addestramenti collettivi'),
    'puma.collettivo_nuovo': ('attivita', 'Nuovo addestramento collettivo'), 'puma.collettivo': ('attivita', 'Scheda addestramento'),
    'puma.partecipa': ('attivita', 'Registrazione all\'addestramento'), 'puma.piano': ('attivita', 'Piano di sicurezza'),
    'puma.attivita': ('attivita', 'Attività formative'),
    'puma.presenze': ('realtime', 'Presenze Odierne'), 'puma.mappa': ('realtime', 'Mappa Real Time'), 'puma.oggi': ('realtime', 'Registro odierno'),
    'puma.documentazione': ('documentazione', 'Documentazione'), 'puma.archivio': ('documentazione', 'Archivio'),
    'puma.profilo': ('individuale', 'Report Individuale'),
    'puma.report_collettivo': ('collettivo', 'Report Collettivo'), 'puma.settore': ('collettivo', 'Report Collettivo'),
    'puma.area_comando': ('comando', 'Area Comando'), 'puma.impostazioni': ('comando', 'Impostazioni del Comando'),
    'puma.livelli_utente': ('comando', 'Livelli utenti'),
    'admin_utenti': ('comando', 'Utenti e permessi'), 'admin_utente': ('comando', 'Gestisci utente'), 'admin_organico': ('comando', 'Organico'),
    'admin_config': ('comando', 'Configurazione e WAUC'), 'admin_comandi': ('comando', 'Schede dei comandi'), 'admin_audit': ('comando', 'Registro attività'),
}
TITOLI_DOC = {'manuali-puma': 'Manuali P.U.M.A.', 'manuali-settore': 'Manuali di settore', 'circolari-settore': 'Circolari di settore'}


def permessi(u, puo):
    """Cosa può vedere l'utente: Area Comando (ROP, ROR, Nazionale, admin), Impostazioni (gestore), amministrazione (admin)."""
    if not u or u['stato'] != 'attivo': return dict(comando=False, gestore=False, admin=False)
    admin = bool(u['is_admin'])
    with portale_db.connect() as c:
        liv = c.execute('SELECT livello FROM puma_livello_utente WHERE utente_id=?', (u['id'],)).fetchone()
        settori = [r[0] for r in c.execute('SELECT codice FROM puma_settori')]
    gestore = admin or puo('puma', 'gestore')
    comando = gestore or (liv and liv[0] in ('regione', 'nazionale')) or any(puo(s.lower(), 'gestore') for s in settori)
    return dict(comando=bool(comando), gestore=bool(gestore), admin=admin)


def _ok(perm, p):
    return p is None or perm.get(p, False)


def contesto(utente, puo):
    """Dati per l'intestazione e il menu (templates/base.html)."""
    ep = request.endpoint or ''
    args = {**request.view_args, **request.args.to_dict()} if request.view_args is not None else request.args.to_dict()
    perm = permessi(utente, puo) if utente else dict(comando=False, gestore=False, admin=False)
    chiave, titolo = PAGINE.get(ep, (None, None))
    if ep == 'puma.collettivi' and args.get('vista') == 'riepilogo': chiave, titolo = 'realtime', 'Riepilogo Globale'
    if ep == 'puma.documentazione': titolo = TITOLI_DOC.get(args.get('cat'), titolo)
    gruppo = GRUPPI.get(chiave)
    area = gruppo['area'] if gruppo else {'home': 'neu', 'individuale': 'rep', 'collettivo': 'rep'}.get(chiave, 'neu')
    schede = []
    if gruppo:
        for e, a, etichetta, p in gruppo['schede']:
            if not _ok(perm, p): continue
            attiva = e == ep and all(str(args.get(k)) == str(v) for k, v in a.items())
            if ep == 'puma.collettivi' and e == 'puma.collettivi': attiva = (args.get('vista') == 'riepilogo') == ('vista' in a)
            if e == 'puma.collettivi' and ep in ('puma.collettivo_nuovo', 'puma.collettivo', 'puma.partecipa', 'puma.piano') and 'vista' not in a: attiva = True
            if e == 'admin_utenti' and ep == 'admin_utente': attiva = True
            schede.append(dict(url=url_for(e, **a), etichetta=etichetta, attiva=attiva))
    return dict(nav_chiave=chiave, nav_area=area, nav_titolo=titolo, nav_gruppo=gruppo, nav_schede=schede, nav_perm=perm,
                nav_gruppi=GRUPPI, nav_voci_menu=_menu(perm, ep, args))


def _menu(perm, ep, args):
    """Voci del menu laterale: [(sezione, area, icona, [(url, etichetta, attiva)])]."""
    out = []
    for chiave in ('attivita', 'realtime', 'documentazione', 'comando'):
        gr = GRUPPI[chiave]
        if chiave == 'comando' and not perm['comando']: continue
        voci = []
        for e, a, etichetta, p in gr['schede']:
            if not _ok(perm, p): continue
            voci.append((url_for(e, **a), etichetta, e == ep and all(str(args.get(k)) == str(v) for k, v in a.items())))
        out.append((gr['nome'], gr['area'], gr['ic'], voci))
    return out
