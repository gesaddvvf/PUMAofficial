"""Accesso al db SQLite e migrazioni versionate (migrazioni/NNN_nome.sql).
All'avvio le migrazioni mancanti vengono applicate in ordine, dopo un backup automatico:
così il db esistente si adatta da solo quando i file del portale vengono sovrascritti."""
import sqlite3, os, glob, datetime
import config

class _Conn(sqlite3.Connection):
    """Dentro 'with' fa commit/rollback e poi CHIUDE la connessione (sqlite3 di default non la chiude)."""
    def __exit__(self, *a):
        try: return super().__exit__(*a)
        finally: self.close()

def connect():
    c = sqlite3.connect(config.DB_PATH, timeout=15, factory=_Conn)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def backup(etichetta='manuale'):
    dst = os.path.join(config.BACKUP_DIR, f"puma_{datetime.datetime.now():%Y%m%d_%H%M%S}_{etichetta}.db")
    src, out = connect(), sqlite3.connect(dst)
    src.backup(out); out.close(); src.close()
    return dst

def migra():
    """Applica le migrazioni mancanti. Il riconoscimento è per NOME FILE (non per numero): due file con lo stesso numero non si coprono a vicenda."""
    c = connect()
    c.execute('CREATE TABLE IF NOT EXISTS migrazioni(nome TEXT PRIMARY KEY, applicata_il TEXT)')
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='schema_version'").fetchone():   # db di versioni vecchie: ne legge i nomi per riconoscerlo
        c.execute('INSERT OR IGNORE INTO migrazioni(nome,applicata_il) SELECT nome,applicata_il FROM schema_version WHERE nome IS NOT NULL')
    c.commit()
    fatte = {r[0] for r in c.execute('SELECT nome FROM migrazioni')}
    file_sql = sorted(glob.glob(os.path.join(config.BASE_DIR, 'migrazioni', '*.sql')))
    sconosciute = fatte - {os.path.basename(f) for f in file_sql}
    if sconosciute:
        c.close()
        raise RuntimeError(f'Il db {config.DB_PATH} contiene migrazioni sconosciute a questa versione di PUMA ({", ".join(sorted(sconosciute))}).\n'
                           '  -> eseguire:  python manage.py reset-db --tutto   (crea prima un backup e ricrea il db vuoto)\n'
                           '     oppure cancellare il file del db. Poi:  python manage.py nomina-admin nome.cognome')
    da_fare = [f for f in file_sql if os.path.basename(f) not in fatte]
    if da_fare and fatte:
        c.close(); print('[DB] backup pre-migrazione:', backup('pre_migrazione')); c = connect()
    for f in da_fare:
        nome = os.path.basename(f)
        try:
            c.executescript('BEGIN;\n' + open(f, encoding='utf-8').read() + '\nCOMMIT;')
            c.execute('INSERT INTO migrazioni VALUES(?,?)', (nome, datetime.datetime.now().isoformat()))
            c.commit(); print(f'[DB] migrazione applicata: {nome}')
        except Exception:
            c.rollback(); raise
    c.close()

def audit(c, email, azione, dettaglio=''):
    c.execute('INSERT INTO audit(ts,utente_email,azione,dettaglio) VALUES(?,?,?,?)',
              (datetime.datetime.now().isoformat(timespec='seconds'), email, azione, dettaglio))
