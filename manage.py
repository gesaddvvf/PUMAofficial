"""Gestione di PUMA da riga di comando:  python manage.py <comando>
  (in modalità prova i comandi agiscono sul db di prova: impostare prima PUMA_MODALITA=prova)
  verifica-vpn            controlla che posta dipartimentale e WAUC siano raggiungibili (FortiClient VPN collegata)
  primo-admin             chiede l'email del primo amministratore (solo se non ce n'è ancora uno)
  nomina-admin EMAIL | revoca-admin EMAIL | utenti
  wauc-test [EMAIL]       prova il collegamento a WAUC: mostra i campi restituiti e cosa trova per quell'email
  wauc-sync               legge da WAUC l'elenco completo di specializzazioni e qualifiche
  sync-sedi [CMD,UFC]     scarica le sedi da /api/Sedi e le collega ai Comandi di PUMA
  sync-qualifiche         scarica soltanto le qualifiche
  sync-specializzazioni   scarica soltanto le specializzazioni (con validità)
  comandi                 riepilogo delle schede dei comandi (contatti, PEC, NUE, siti)
  wauc-sedi               scopre le sedi WAUC con personale (interroga tutte le sigle provinciali)
  specializzazioni        stampa l'elenco di tutte le specializzazioni note (codice, descrizione, persone)
  organico                (elenco dell'anagrafica usata per la ricerca all'accesso; si gestisce da Amministrazione > Organico)
  reset-utente EMAIL      cancella l'utente: al prossimo login è un primo accesso
  reset-profilo EMAIL     svuota il profilo: al prossimo login riparte la ricerca in organico
  reset-db [--tutto]      svuota utenti/permessi/registro (--tutto: elimina l'intero db, organico incluso)
  puma-demo --rimuovi     toglie dal db utenti e dati marcati demo (i dati di prova si usano con AVVIA_PROVA)
  puma-scadenze           invia gli alert di scadenza P.U.M.A. (da pianificare ogni giorno)
  migra | backup | esporta-csv [cartella] | primo-admin"""
import sys, os, csv, datetime
import config, db, profilo
from auth_imap import EMAIL_RE, estrai_nome_cognome, norm_email
if not ('reset-db' in sys.argv and '--tutto' in sys.argv): db.migra()   # reset-db --tutto deve poter ripartire anche da un db vecchio
ADESSO = lambda: datetime.datetime.now().isoformat(timespec='seconds')

def main(a):
    if not a: return print(__doc__)
    cmd = a[0]
    if cmd == 'migra': print('Db aggiornato.')
    elif cmd == 'verifica-vpn':
        import rete, wauc
        if config.PROVA: return print('Modalita prova: non serve nessun collegamento alla rete VVF.')
        print('Verifica dei collegamenti alla rete VVF (FortiClient VPN collegata oppure rete interna)...')
        ris = rete.controlli(timeout=4)
        for r in ris: print(f"  [{'OK' if r['ok'] else '!!'}] {r['nome']:22} {r['dettaglio']}")
        if any(r['ok'] for r in ris[1:]):
            try: print(f"  [OK] Lettura dati WAUC      {len(wauc.catalogo_qualifiche())} qualifiche ricevute")
            except Exception as e: print(f"  [!!] Lettura dati WAUC      il server risponde ma i dati non arrivano ({str(e)[:120] or e.__class__.__name__})")
        if ris[0]['ok']:
            print('Collegamento OK: puoi accedere con le credenziali dipartimentali.' if all(r['ok'] for r in ris)
                  else 'Il login funziona; WAUC non risponde: i dati del profilo andranno completati a mano.')
            return
        print('\nNON sei collegato alla rete VVF: il login con le credenziali dipartimentali non funzionera.\n'
              '  1. apri FortiClient VPN e collegati (se serve, anche con il codice OTP)\n'
              '  2. ripeti la verifica:  python manage.py verifica-vpn\n'
              '  Per provare PUMA senza VPN usa la modalita prova (AVVIA_PROVA.bat / ./avvia_prova.sh).')
        raise SystemExit(1)
    elif cmd == 'primo-admin':
        c = db.connect()
        if c.execute('SELECT 1 FROM utenti WHERE is_admin=1').fetchone(): return print('Amministratore gia presente.')
        print('Primo avvio: nessun amministratore. Indica il tuo utente dipartimentale (basta nome.cognome).')
        try: email = input('Utente del primo amministratore: ').strip().lower()
        except EOFError: return print('Nessun amministratore indicato: potrai nominarlo con  python manage.py nomina-admin nome.cognome')
        if not email: return print('Nessun amministratore indicato: potrai nominarlo con  python manage.py nomina-admin nome.cognome')
        return main(['nomina-admin', email])
    elif cmd == 'puma-demo':
        if not config.PROVA and '--rimuovi' not in a and '--forza' not in a:
            return print('I dati di prova si usano in modalita prova (AVVIA_PROVA.bat / ./avvia_prova.sh), con un db separato:\n'
                         'li crea da sola all\'avvio. Per crearli comunque nel db reale: python manage.py puma-demo --forza')
        import app as portale
        from moduli.puma import demo
        demo.rimuovi() if '--rimuovi' in a else demo.crea()
    elif cmd == 'puma-scadenze':
        import app as portale
        from moduli.puma import addestramenti
        with portale.app.test_request_context(): print(addestramenti.invia_alert_scadenze(), 'alert inviati')
    elif cmd == 'backup': print('Backup creato:', db.backup())
    elif cmd == 'esporta-csv':
        out = a[1] if len(a) > 1 else os.path.join(config.BACKUP_DIR, f'csv_{datetime.datetime.now():%Y%m%d_%H%M%S}')
        os.makedirs(out, exist_ok=True); c = db.connect()
        for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            cur = c.execute(f'SELECT * FROM "{t}"')
            with open(os.path.join(out, t + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';'); w.writerow([d[0] for d in cur.description]); w.writerows(cur)
        print('Esportato in', out)
    elif cmd == 'utenti':
        for r in db.connect().execute('SELECT email,stato,is_admin FROM utenti ORDER BY email'):
            print(f"{r['email']:45} {r['stato']:12} {'ADMIN' if r['is_admin'] else ''}")
    elif cmd == 'wauc-sync':
        try: c = db.connect(); ns, nq = profilo.sincronizza_catalogo(c); c.commit(); print(f'{ns} specializzazioni e {nq} qualifiche lette da WAUC.  (elenco: python3 manage.py specializzazioni)')
        except Exception as e: print('ERRORE:', e)
    elif cmd in ('sync-sedi', 'sync-qualifiche', 'sync-specializzazioni'):
        c = db.connect()
        try:
            if cmd == 'sync-sedi': r = profilo.sincronizza_sedi(c, tuple(t.strip().upper() for t in (a[1] if len(a) > 1 else 'CMD,UFC').split(',') if t.strip())); print(f"{r['sedi']} sedi ({r['comandi']} comandi, {r['collegati']} collegati ai Comandi di PUMA, {r['con_coordinate']} con coordinate).")
            elif cmd == 'sync-qualifiche': print(profilo.sincronizza_qualifiche(c), 'qualifiche lette da WAUC.')
            else: print(profilo.sincronizza_specializzazioni(c), 'specializzazioni lette da WAUC.')
            c.commit()
        except Exception as e: print('ERRORE:', e)
    elif cmd == 'comandi':
        c = db.connect(); r = c.execute("SELECT COUNT(*) n, SUM(telefono IS NOT NULL) t, SUM(pec IS NOT NULL) p, SUM(nue=1) ns, SUM(nue=0) nn, SUM(sito_intranet IS NOT NULL) i, SUM(wauc_sede_id IS NOT NULL) w FROM comandi").fetchone()
        print(f"Comandi: {r['n']} · con telefono: {r['t'] or 0} · con PEC: {r['p'] or 0} · NUE sì/no: {r['ns'] or 0}/{r['nn'] or 0} · con intranet: {r['i'] or 0} · collegati a una sede WAUC: {r['w'] or 0}")
        for k in c.execute('SELECT nome, sigla, telefono, pec, nue, sito_intranet FROM comandi WHERE telefono IS NOT NULL OR pec IS NOT NULL OR nue IS NOT NULL ORDER BY nome LIMIT 30'):
            print(f"  {k['nome']:28} {k['telefono'] or '-':18} {k['pec'] or '-':35} NUE: {'sì' if k['nue'] == 1 else 'no' if k['nue'] == 0 else '?'}")
    elif cmd == 'wauc-sedi':
        c = db.connect(); print('Interrogo tutte le sedi (può richiedere un po\' di tempo)...'); ris = profilo.scopri_sedi(c); c.commit()
        for s, n in sorted(ris.items()): print(f"  {s}  {'errore/non raggiungibile' if n is None else str(n) + ' persone'}") if n != 0 else None
        print(f"Sedi con personale: {sum(1 for n in ris.values() if n)}  ·  persone totali: {sum(n or 0 for n in ris.values())}  ·  senza risposta: {sum(1 for n in ris.values() if n is None)}")
    elif cmd == 'specializzazioni':
        c = db.connect(); righe = c.execute("""SELECT s.codice, s.descrizione, s.fonte, (SELECT COUNT(*) FROM specializzazioni_utente u WHERE u.codice=s.codice) AS persone
                                           FROM specializzazioni s WHERE s.aggiornata_il IS NOT NULL ORDER BY s.codice""").fetchall()
        print(f'{len(righe)} specializzazioni' if righe else 'Elenco vuoto: esegui prima  python3 manage.py wauc-sync')
        for r in righe: print(f"{r['codice']:8} {(r['descrizione'] or '-'):60} persone: {r['persone']}" + ('  (aggiunta da un utente)' if r['fonte'] == 'utente' else ''))
    elif cmd == 'wauc-test':
        import wauc
        c = db.connect(); sedi = profilo.sedi_wauc(c)
        print(f'Sedi interrogate: {len(sedi)}' + (f" ({', '.join(sedi)})" if len(sedi) <= 8 else ' (tutte le sigle provinciali: per limitare la ricerca usa wauc-sedi o PUMA_WAUC_SEDI)'))
        if len(a) > 1:
            try: w = wauc.cerca_persona(norm_email(a[1])[0] or a[1], sedi)
            except Exception as e: return print('ERRORE:', e)
            if not w: return print('Email non trovata in WAUC (ne per email ne per nome.cognome).')
            print('Trovata via', w['via'], '· sede', w['sede']); [print(f'  {k}: {v or "-"}') for k, v in w['dati'].items() if k != 'extra']
            print('  --- dati WAUC memorizzati:'); [print(f'  {k}: {v or "-"}') for k, v in w['dati']['extra'].items()]
            print('  specializzazioni:' + ('' if w['specs'] else ' nessuna rilevata'))
            for cod, d, ini, fin in w['specs']: print(f"    {cod:8} {d or '-':45} dal {ini or '-'} al {fin or 'senza scadenza'}")
        try: print(f'Catalogo WAUC: {len(wauc.catalogo_specializzazioni())} specializzazioni, {len(wauc.catalogo_qualifiche())} qualifiche.')
        except Exception as e: print('Cataloghi: ERRORE', e.__class__.__name__)
    elif cmd == 'organico':
        c = db.connect(); print('Persone in organico:', c.execute('SELECT COUNT(*) FROM organico').fetchone()[0])
        for r in c.execute('SELECT email,cognome,nome,comando FROM organico ORDER BY cognome LIMIT 20'): print(f"  {r['email']:40} {r['cognome']} {r['nome']} · {r['comando'] or ''}")
    elif cmd in ('reset-utente', 'reset-profilo') and len(a) > 1:
        email = norm_email(a[1])[0] or a[1].strip().lower(); c = db.connect()
        u = c.execute('SELECT id FROM utenti WHERE email=?', (email,)).fetchone()
        if not u: return print('Utente non presente nel db.')
        if cmd == 'reset-utente':
            c.execute('UPDATE utenti SET approvato_da=NULL WHERE approvato_da=?', (u['id'],))
            c.execute('DELETE FROM utenti WHERE id=?', (u['id'],))
        else: c.execute("UPDATE utenti SET profilo_confermato=0, comando_id=NULL, matricola=NULL, qualifica=NULL, distaccamento=NULL, telefono=NULL, origine_profilo=NULL WHERE id=?", (u['id'],))
        db.audit(c, 'cli', cmd, email); c.commit(); print('Fatto:', cmd, email)
    elif cmd == 'reset-db':
        if '--tutto' in a:
            if os.path.exists(config.DB_PATH): print('Backup:', db.backup('pre_reset'))
            for suff in ('', '-wal', '-shm', '-journal'):
                if os.path.exists(config.DB_PATH + suff): os.remove(config.DB_PATH + suff)
            db.migra(); return print('Db eliminato e ricreato (vuoto). Ora: python3 manage.py nomina-admin nome.cognome')
        c = db.connect(); print('Backup:', db.backup('pre_reset'))
        for t in ('permessi', 'utenti', 'audit'): c.execute(f'DELETE FROM {t}')
        c.commit(); print('Utenti, permessi e registro azzerati (organico, comandi e settori conservati).')
    elif cmd in ('nomina-admin', 'revoca-admin') and len(a) > 1:
        email = norm_email(a[1])[0] or a[1].strip().lower(); c = db.connect()
        if not EMAIL_RE.match(email): return print('Email non valida (atteso nome.cognome@vigilfuoco.it)')
        if cmd == 'nomina-admin':
            n, cg = estrai_nome_cognome(email)
            c.execute("INSERT OR IGNORE INTO utenti(email,nome,cognome,creato_il) VALUES(?,?,?,?)", (email, n, cg, datetime.datetime.now().isoformat(timespec='seconds')))
            c.execute("UPDATE utenti SET is_admin=1, stato='attivo' WHERE email=?", (email,))
            u = c.execute('SELECT * FROM utenti WHERE email=?', (email,)).fetchone()
            o, err = profilo.profila(c, u); print({'wauc': 'Trovato in WAUC: dati caricati.', 'organico': 'Trovato in organico: dati caricati.'}.get(o, 'Non trovato: userà nome/cognome ricavati dall\'email.'), ('(' + err + ')') if err else '')
        else: c.execute('UPDATE utenti SET is_admin=0 WHERE email=?', (email,))
        db.audit(c, 'cli', cmd, email); c.commit(); print('Fatto:', cmd, email)
    else: print(__doc__)

if __name__ == '__main__': main(sys.argv[1:])
