"""Utenti fittizi e dati di prova per P.U.M.A. (solo test).
Creati in automatico all'avvio in modalità prova (AVVIA_PROVA.bat / avvia_prova.sh), nel db separato data_prova/.
Rimossi da:  python manage.py puma-demo --rimuovi   (cancella solo ciò che è marcato demo)."""
import datetime
import db

DOM = "@vigilfuoco.it"
CF = {"demo.utente": "DMUTNT80A01A757W", "demo.rop": "DMRPOP75B15F205X", "demo.ror": "DMRRRG70C20L736Z", "demo.nazionale": "DMNZNL85D25H501F"}  # fittizi
UTENTI = [  # email, nome, cognome, sigla comando, livello P.U.M.A., permesso su puma/saf, livello visibilità
    ("demo.utente", "Mario", "Rossi", "BL", "lettura", "comando"),
    ("demo.rop", "Laura", "Bianchi", "BL", "gestore", "comando"),
    ("demo.ror", "Paolo", "Verdi", "VE", "lettura", "regione"),
    ("demo.nazionale", "Anna", "Neri", "RM", "lettura", "nazionale"),
]
# comando, team, riservato, condiviso nazionale, lat, lon
EVENTI = [("BL", "Alfa", 0, 0, 46.1400, 12.2167), ("TV", "Bravo", 0, 0, 45.6669, 12.2430),
          ("TV", "Charlie", 1, 0, 45.6700, 12.2500), ("MI", "Alfa", 0, 0, 45.4642, 9.1900), ("RM", "Delta", 0, 1, 41.9028, 12.4964)]

def crea(silenzioso=False):
    oggi = datetime.date.today(); ora = datetime.datetime.now().isoformat(timespec="seconds")
    with db.connect() as c:
        com = {r["sigla"]: r["id"] for r in c.execute("SELECT id, sigla FROM comandi")}
        sett = {r["codice"]: r["id"] for r in c.execute("SELECT id, codice FROM settori")}
        if "puma" not in sett or "saf" not in sett: raise SystemExit("Avvia prima PUMA una volta (migrazioni) e riprova.")
        for em, nome, cogn, sig, liv, vis in UTENTI:
            email = em + DOM
            c.execute("""INSERT INTO utenti(email,nome,cognome,comando_id,stato,creato_il,approvato_il,origine_profilo,profilo_confermato)
                VALUES(?,?,?,?, 'attivo', ?, ?, 'manuale', 1) ON CONFLICT(email) DO UPDATE SET comando_id=excluded.comando_id, stato='attivo', profilo_confermato=1""",
                (email, nome, cogn, com[sig], ora, ora))
            uid = c.execute("SELECT id FROM utenti WHERE email=?", (email,)).fetchone()[0]
            for cod in ("puma", "saf"):
                c.execute("INSERT OR REPLACE INTO permessi VALUES(?,?,?)", (uid, sett[cod], liv))
            c.execute("INSERT OR REPLACE INTO puma_livello_utente VALUES(?,?)", (uid, vis))
            c.execute("INSERT OR REPLACE INTO puma_persone VALUES(?,?)", (uid, CF[em]))
        lv = c.execute("SELECT id FROM puma_livelli WHERE nome='SAF Basico'").fetchone()[0]
        for sig, team, blind, naz, lat, lon in EVENTI:
            cod = f"SAF-{team.upper()}-" + c.execute("SELECT COALESCE(dz.sigla,'XXX') FROM puma_comando_dir cd JOIN puma_direzioni dz ON dz.id=cd.direzione_id WHERE cd.comando_id=?", (com[sig],)).fetchone()[0] + sig + "-" + oggi.strftime("%Y%m%d")
            c.execute("""INSERT OR IGNORE INTO puma_eventi(data,ora_inizio,ora_fine,cod_add,tipologia,livello_id,team,titolo,lat,lon,rv_lat,rv_lon,rv_descr,amb_lat,amb_lon,amb_descr,responsabile,comando_id,direzione_id,
                is_blindato,is_condiviso_nazionale) VALUES(?, '08:00', '16:00', ?, 'SAF', ?, ?, ?, ?, ?, ?, ?, 'Prato (demo)', ?, ?, 'Parcheggio (demo)', 'demo.rop'||?, ?, (SELECT direzione_id FROM puma_comando_dir WHERE comando_id=?), ?, ?)""",
                (oggi.isoformat(), cod, lv, team, f"[DEMO] Addestramento {sig}", lat, lon, lat + 0.003, lon + 0.003, lat - 0.002, lon + 0.002, DOM, com[sig], com[sig], blind, naz))
        # Mario: una scadenza imminente (SAF Basico svolto circa 11 mesi fa) -> visibile nelle scadenze del ROP/ROR/Nazionale
        mid = c.execute("SELECT id FROM utenti WHERE email='demo.utente'||?", (DOM,)).fetchone()[0]
        if not c.execute("SELECT 1 FROM puma_individuali WHERE username='demo.utente'||?", (DOM,)).fetchone():
            d0 = (oggi - datetime.timedelta(days=335)).isoformat()
            c.execute("""INSERT INTO puma_individuali(username,tipologia,livello_id,inizio,fine,manovre,comando_id,direzione_id,is_blindato,is_condiviso_nazionale)
                VALUES('demo.utente'||?, 'SAF', ?, ?, ?, '[]', ?, (SELECT direzione_id FROM puma_comando_dir WHERE comando_id=?), 0, 0)""",
                (DOM, lv, d0 + "T09:00", d0 + "T11:00", com["BL"], com["BL"]))
        c.execute("INSERT OR IGNORE INTO puma_destinatari VALUES(?, 'ROP', ?)", (com["BL"], "demo.rop" + DOM))
    if not silenzioso:
        print("Creati: " + ", ".join(e + DOM for e, *_ in UTENTI))
        print("Accesso: AVVIA_PROVA.bat oppure ./avvia_prova.sh (password 'dev').")

def rimuovi():
    with db.connect() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM utenti WHERE email LIKE 'demo.%'||?", (DOM,))]
        c.execute("DELETE FROM puma_checkin WHERE evento_id IN (SELECT id FROM puma_eventi WHERE titolo LIKE '[DEMO]%') OR username LIKE 'demo.%'")
        c.execute("DELETE FROM puma_eventi WHERE titolo LIKE '[DEMO]%'")
        for t in ("puma_individuali", "puma_interventi"): c.execute(f"DELETE FROM {t} WHERE username LIKE 'demo.%'")
        c.execute("DELETE FROM puma_destinatari WHERE email LIKE 'demo.%'")
        c.execute("DELETE FROM puma_alert_inviati WHERE username LIKE 'demo.%'")
        for i in ids: c.execute("DELETE FROM utenti WHERE id=?", (i,))
    print(f"Rimossi {len(ids)} utenti demo e i relativi dati.")
