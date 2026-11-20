"""Navigazione di PUMA, uguale al sito gesaddvvf.github.io/PUMA: pulsanti per area nell'intestazione
(Home Page, Attività, Real Time, Didattica e documentazione, Area personale, Reportistica, Area Comando),
schede sotto l'intestazione per le aree con più pagine e menu laterale (☰).

Il nucleo (app.py) chiama contesto() a ogni pagina, anche per le pagine del nucleo (profilo, amministrazione),
così l'intestazione è la stessa ovunque. Colori delle aree: neu grigio, att rosso, rt verde, doc blu, per viola, rep giallo, com bianco."""
from flask import url_for, request, g
import db as portale_db

# Schede delle aree con più pagine: (endpoint, argomenti, etichetta, permesso)
# permesso: None = tutti · altrimenti una capacità di moduli/puma/ruoli.py (area_comando, report, programma, piano,
# localita, ruoli, aree, impostazioni, sistema…) oppure 'comando' (= area_comando), 'scrittura' (= programma), 'admin' (= sistema).
GRUPPI = {
    'attivita': dict(nome='Attività', area='att', ic='📝', schede=[
        ('puma.attivita_oggi', {}, 'Addestramenti di oggi', None),
        ('puma.collettivo_nuovo', {}, 'Programma un addestramento', 'programma'),
        ('puma.collettivi', {}, 'Calendario', None),
        ('puma.piani', {}, 'Piani di sicurezza', 'piano'),
        ('puma.individuali', {}, 'Registrazione individuale', None),
        ('puma.interventi', {}, 'Interventi reali', None)]),
    'realtime': dict(nome='Real Time', area='rt', ic='⏱️', schede=[
        ('puma.presenze', {}, 'Presenze Odierne', None),
        ('puma.mappa', {}, 'Mappa Real Time', None),
        ('puma.collettivi', {'vista': 'riepilogo', 'quando': 'tutti'}, 'Riepilogo Globale', None),
        ('puma.oggi', {}, 'Registro odierno', None)]),
    'didattica': dict(nome='Didattica e documentazione', area='doc', ic='🎓', schede=[
        ('puma.didattica', {}, 'Didattica', None),
        ('puma.documentazione', {'cat': 'manuali-puma'}, 'Manuali P.U.M.A.', None),
        ('puma.documentazione', {'cat': 'manuali-settore'}, 'Manuali di settore', None),
        ('puma.documentazione', {'cat': 'circolari-settore'}, 'Circolari di settore', None),
        ('puma.archivio', {}, 'Archivio', None)]),
    'personale': dict(nome='Area personale', area='per', ic='👤', schede=[
        ('puma.personale', {}, 'Riepilogo', None),
        ('puma.profilo', {}, 'Report individuale', None),
        ('puma.mie_attivita', {}, 'Le mie attività', None),
        ('profilo_view', {}, 'Profilazione', None)]),
    'collettivo': dict(nome='Reportistica', area='rep', ic='📊', schede=[
        ('puma.report_collettivo', {}, 'Report collettivo', 'report'),
        ('puma.cruscotto', {}, 'Cruscotto corsi', 'report')]),
    'comando': dict(nome='Area Comando', area='com', ic='🔓', schede=[
        ('puma.area_comando', {}, 'Panoramica', 'area_comando'),
        ('puma.report_collettivo', {}, 'Report collettivo', 'report'),
        ('puma.cruscotto', {}, 'Cruscotto corsi', 'report'),
        ('puma.localita', {}, 'Località', 'localita'),
        ('puma.accessi', {}, 'Livelli di accesso', 'ruoli'),
        ('puma.inviti', {}, 'Inviti', 'ruoli'),
        ('puma.aree_corsi', {}, 'Aree corsi', 'aree'),
        ('puma.impostazioni', {}, 'Impostazioni', 'impostazioni'),
        ('puma.importa_foglio', {}, 'Corsi e foglio PUMA', 'aree'),
        ('admin_utenti', {}, 'Utenti', 'sistema'),
        ('admin_organico', {}, 'Organico', 'sistema'),
        ('admin_config', {}, 'Configurazione e WAUC', 'sistema'),
        ('admin_comandi', {}, 'Comandi e Direzioni', 'sistema'),
        ('admin_audit', {}, 'Registro attività', 'sistema')]),
}
ORDINE_MENU = ('attivita', 'realtime', 'didattica', 'personale', 'collettivo', 'comando')


def registra(gruppo, endpoint, etichetta, permesso=None, argomenti=None):
    """Per i moduli futuri: aggiunge una scheda a un'area. Esempio, in moduli/<nuovo>/__init__.py:
         from moduli.puma.navigazione import registra
         registra('didattica', 'quiz.index', 'Quiz di autoverifica')
       La pagina va poi aggiunta anche a PAGINE con registra_pagina()."""
    voce = (endpoint, argomenti or {}, etichetta, permesso)
    if voce not in GRUPPI[gruppo]['schede']: GRUPPI[gruppo]['schede'].append(voce)
    PAGINE.setdefault(endpoint, (gruppo, etichetta))


# endpoint -> (gruppo o area, titolo della pagina). Il gruppo decide pulsante acceso, schede e colore.
PAGINE = {
    'puma.index': ('home', 'Home Page'),
    'puma.attivita_oggi': ('attivita', 'Addestramenti di oggi'), 'puma.piani': ('attivita', 'Piani di sicurezza'),
    'puma.individuali': ('attivita', 'Registrazione individuale'), 'puma.interventi': ('attivita', 'Interventi reali'),
    'puma.collettivi': ('attivita', 'Calendario addestramenti'),
    'puma.collettivo_nuovo': ('attivita', 'Programma un addestramento'), 'puma.collettivo': ('attivita', 'Scheda addestramento'),
    'puma.partecipa': ('attivita', 'Registrazione all\'addestramento'), 'puma.piano': ('attivita', 'Piano di sicurezza'),
    'puma.attivita': ('attivita', 'Attività formative'),
    'puma.presenze': ('realtime', 'Presenze Odierne'), 'puma.mappa': ('realtime', 'Mappa Real Time'), 'puma.oggi': ('realtime', 'Registro odierno'),
    'puma.didattica': ('didattica', 'Didattica e documentazione'),
    'puma.documentazione': ('didattica', 'Documentazione'), 'puma.archivio': ('didattica', 'Archivio'),
    'puma.personale': ('personale', 'Area personale'), 'puma.profilo': ('personale', 'Report Individuale'),
    'puma.mie_attivita': ('personale', 'Le mie attività'),
    'profilo_view': ('personale', 'Profilazione individuale'), 'profilo_spec_aggiungi': ('personale', 'Profilazione individuale'),
    'puma.report_collettivo': ('collettivo', 'Report Collettivo'), 'puma.settore': ('collettivo', 'Report Collettivo'),
    'puma.cruscotto': ('collettivo', 'Cruscotto corsi'),
    'puma.area_comando': ('comando', 'Area Comando'), 'puma.impostazioni': ('comando', 'Impostazioni'),
    'puma.livelli_utente': ('comando', 'Livelli di accesso'), 'puma.accessi': ('comando', 'Livelli di accesso'),
    'puma.inviti': ('comando', 'Inviti'), 'puma.aree_corsi': ('comando', 'Aree corsi'),
    'puma.localita': ('comando', 'Località'), 'puma.localita_scheda': ('comando', 'Località'),
    'puma.importa_foglio': ('comando', 'Corsi e foglio PUMA'),
    'admin_utenti': ('comando', 'Utenti'), 'admin_utente': ('comando', 'Gestisci utente'), 'admin_organico': ('comando', 'Organico'),
    'admin_config': ('comando', 'Configurazione e WAUC'), 'admin_comandi': ('comando', 'Comandi e Direzioni'), 'admin_audit': ('comando', 'Registro attività'),
}
TITOLI_DOC = {'manuali-puma': 'Manuali P.U.M.A.', 'manuali-settore': 'Manuali di settore', 'circolari-settore': 'Circolari di settore'}
VUOTI = dict(comando=False, gestore=False, admin=False, scrittura=False)


def permessi(u, puo):
    """Cosa può vedere e fare l'utente: le capacità dei suoi ruoli (moduli/puma/ruoli.py) più i permessi di prima
    (P.U.M.A. scrittura/gestore, gestore di un settore, visibilità regione/nazionale), che restano validi."""
    from .ruoli import accessi, CAPACITA
    if not u or u['stato'] != 'attivo': return dict(VUOTI)
    acc = accessi()
    with portale_db.connect() as c:
        liv = c.execute('SELECT livello FROM puma_livello_utente WHERE utente_id=?', (u['id'],)).fetchone()
        settori = [r[0] for r in c.execute('SELECT codice FROM puma_settori')]
    admin = acc.admin
    vecchi = not acc.righe   # i permessi di prima valgono solo per chi non ha ancora livelli di accesso v1.3
    gestore_vecchio = admin or (vecchi and puo('puma', 'gestore'))
    comando_vecchio = gestore_vecchio or (liv and liv[0] in ('regione', 'nazionale')) or (vecchi and any(puo(s.lower(), 'gestore') for s in settori))
    out = {k: acc.puo(k) for k in CAPACITA}
    out['area_comando'] = bool(out['area_comando'] or comando_vecchio)
    out['report'] = bool(out['report'] or comando_vecchio)
    out['impostazioni'] = bool(out['impostazioni'] or gestore_vecchio)
    out['programma'] = bool(out['programma'] or (vecchi and puo('puma', 'scrittura')))
    out['piano'] = bool(out['piano'] or (vecchi and puo('puma', 'scrittura')))
    out.update(comando=out['area_comando'], gestore=out['impostazioni'], admin=admin, scrittura=out['programma'],
               ruolo=acc.etichetta() if acc.righe or acc.admin or not (liv and liv[0] != 'comando') else f'Visibilità {liv[0]}')
    return out


ALIAS = {'comando': 'area_comando', 'scrittura': 'programma', 'admin': 'sistema', 'gestore': 'impostazioni'}


def _ok(perm, p):
    return p is None or bool(perm.get(ALIAS.get(p, p), False))


def contesto(utente, puo):
    """Dati per l'intestazione e il menu (templates/base.html)."""
    ep = request.endpoint or ''
    args = {**request.view_args, **request.args.to_dict()} if request.view_args is not None else request.args.to_dict()
    perm = permessi(utente, puo) if utente else dict(VUOTI)
    chiave, titolo = PAGINE.get(ep, (None, None))
    if ep == 'puma.collettivi' and args.get('vista') == 'riepilogo': chiave, titolo = 'realtime', 'Riepilogo Globale'
    if ep == 'puma.documentazione': titolo = TITOLI_DOC.get(args.get('cat'), titolo)
    gruppo = GRUPPI.get(chiave)
    area = gruppo['area'] if gruppo else 'neu'
    schede = []
    if gruppo:
        for e, a, etichetta, p in gruppo['schede']:
            if not _ok(perm, p): continue
            attiva = e == ep and all(str(args.get(k)) == str(v) for k, v in a.items())
            if ep == 'puma.collettivi' and e == 'puma.collettivi': attiva = (args.get('vista') == 'riepilogo') == ('vista' in a)
            if e == 'puma.collettivi' and ep in ('puma.collettivo', 'puma.partecipa') and 'vista' not in a: attiva = True
            if e == 'puma.piani' and ep == 'puma.piano': attiva = True
            if e == 'admin_utenti' and ep == 'admin_utente': attiva = True
            if e == 'puma.localita' and ep == 'puma.localita_scheda': attiva = True
            if e == 'puma.accessi' and ep == 'puma.livelli_utente': attiva = True
            schede.append(dict(url=url_for(e, **a), etichetta=etichetta, attiva=attiva))
    return dict(nav_chiave=chiave, nav_area=area, nav_titolo=titolo, nav_gruppo=gruppo, nav_schede=schede, nav_perm=perm,
                nav_gruppi=GRUPPI, nav_voci_menu=_menu(perm, ep, args))


def _menu(perm, ep, args):
    """Voci del menu laterale: [(sezione, area, icona, [(url, etichetta, attiva)])]."""
    out = []
    for chiave in ORDINE_MENU:
        gr = GRUPPI[chiave]
        if chiave == 'comando' and not perm.get('area_comando'): continue
        if chiave == 'collettivo' and not perm.get('report'): continue
        voci = []
        for e, a, etichetta, p in gr['schede']:
            if not _ok(perm, p): continue
            voci.append((url_for(e, **a), etichetta, e == ep and all(str(args.get(k)) == str(v) for k, v in a.items())))
        out.append((gr['nome'], gr['area'], gr['ic'], voci))
    return out
