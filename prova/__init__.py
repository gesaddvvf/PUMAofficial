"""Modalità prova di PUMA (AVVIA_PROVA.bat / avvia_prova.sh, cioè PUMA_MODALITA=prova).

- db separato in data_prova/: il db reale (data/) non viene mai toccato;
- password «dev» per qualsiasi utente; nessun collegamento a posta dipartimentale o WAUC (niente VPN);
- WAUC simulato (prova/wauc_finto.json) con utenti fittizi: il login percorre lo stesso codice del login reale;
- all'avvio vengono (ri)creati gli utenti di prova con i rispettivi permessi e alcuni addestramenti di oggi.

Per ricominciare da zero basta cancellare la cartella data_prova/ (oppure AZZERA_PROVA.bat)."""
import datetime
from . import wauc_finto

DOMINIO = '@vigilfuoco.it'
UTENTI = [dict(u, email=u['account'] + DOMINIO) for u in wauc_finto.dati()['utenti_prova']]
NON_PRECREATI = {'demo.nuovo'}   # resta da creare: serve a provare il primo accesso (profilo da WAUC, attesa, abilitazione)


def prepara():
    import db, profilo
    from moduli.puma import demo
    adesso = datetime.datetime.now().isoformat(timespec='seconds')
    with db.connect() as c:
        profilo.assicura_catalogo(c)
        c.execute("INSERT OR IGNORE INTO utenti(email,nome,cognome,creato_il) VALUES(?,?,?,?)", ('demo.admin' + DOMINIO, 'Elena', 'Ferri', adesso))
        c.execute("UPDATE utenti SET is_admin=1, stato='attivo' WHERE email=?", ('demo.admin' + DOMINIO,))
    demo.crea(silenzioso=True)   # utenti P.U.M.A. di prova, permessi, livelli di visibilità, addestramenti di oggi
    with db.connect() as c:
        for u in UTENTI:
            if u['account'] in NON_PRECREATI: continue
            r = c.execute('SELECT * FROM utenti WHERE email=?', (u['email'],)).fetchone()
            if r and r['origine_profilo'] != 'wauc':   # prima volta: profilo compilato dal WAUC simulato, come al login reale
                c.execute('UPDATE utenti SET profilo_confermato=0 WHERE id=?', (r['id'],))
                profilo.profila(c, c.execute('SELECT * FROM utenti WHERE id=?', (r['id'],)).fetchone())
                c.execute('UPDATE utenti SET profilo_confermato=1 WHERE id=?', (r['id'],))
                profilo.salva_in_organico(c, u['email'], dict(c.execute('SELECT * FROM utenti WHERE id=?', (r['id'],)).fetchone()),
                                          c.execute('SELECT k.nome FROM utenti u JOIN comandi k ON k.id=u.comando_id WHERE u.id=?', (r['id'],)).fetchone()[0])
    print(f"[PROVA] utenti fittizi pronti: {', '.join(u['email'] for u in UTENTI)}  (password: dev)")
