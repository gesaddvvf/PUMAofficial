-- v1.3: livelli di accesso per area corsi, gestione aree corsi, database località, inviti con link.
--
-- Livelli di accesso: ogni assegnazione è (persona, ruolo, sede, area corsi). La sede è un Comando (ruoli «Comando»),
-- una Direzione Regionale (ruoli «Direzione») o nessuna (Amministratore Generale, Operatore). L'area corsi è un codice
-- di puma_settori (SAF, TPSS…) oppure '*' = tutte le aree. Cosa può fare ogni ruolo sta in moduli/puma/ruoli.py.

CREATE TABLE IF NOT EXISTS puma_ruoli(
  codice TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  livello TEXT NOT NULL CHECK(livello IN ('nazionale','direzione','comando','base')),
  ordine INTEGER NOT NULL DEFAULT 0);
INSERT OR IGNORE INTO puma_ruoli VALUES
  ('AMM_GEN',  'Amministratore Generale',          'nazionale', 1),
  ('AMM_DIR',  'Amministratore Direzione',         'direzione', 2),
  ('FUNZ_DIR', 'Funzionario di settore Direzione', 'direzione', 3),
  ('ROR_DIR',  'ROR Direzione',                    'direzione', 4),
  ('STAFF_DIR','Staff Direzione',                  'direzione', 5),
  ('MAG_DIR',  'Magazzino Direzione',              'direzione', 6),
  ('AMM_CMD',  'Amministratore Comando',           'comando',   7),
  ('FUNZ_CMD', 'Funzionario di settore Comando',   'comando',   8),
  ('ROP_CMD',  'ROP Comando',                      'comando',   9),
  ('STAFF_CMD','Staff Comando',                    'comando',  10),
  ('MAG_CMD',  'Magazzino Comando',                'comando',  11),
  ('OPERATORE','Operatore',                        'base',     12);

CREATE TABLE IF NOT EXISTS puma_ruoli_utente(
  id INTEGER PRIMARY KEY,
  utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
  ruolo TEXT NOT NULL REFERENCES puma_ruoli(codice),
  sede_id INTEGER REFERENCES comandi(id) ON DELETE CASCADE,
  settore TEXT NOT NULL DEFAULT '*',
  assegnato_da TEXT,
  assegnato_il TEXT,
  UNIQUE(utente_id, ruolo, sede_id, settore));

-- Ruoli dai permessi di prima: amministratori -> Amministratore Generale; gestore P.U.M.A. -> Amministratore Comando;
-- scrittura P.U.M.A. -> Staff Comando; gestore di un settore (saf, tpss…) -> Funzionario di settore Comando di quell'area;
-- visibilità «regione» -> ROR Direzione della propria Direzione.
INSERT OR IGNORE INTO puma_ruoli_utente(utente_id, ruolo, sede_id, settore, assegnato_da, assegnato_il)
  SELECT id, 'AMM_GEN', NULL, '*', 'migrazione', datetime('now','localtime') FROM utenti WHERE is_admin = 1;
INSERT OR IGNORE INTO puma_ruoli_utente(utente_id, ruolo, sede_id, settore, assegnato_da, assegnato_il)
  SELECT p.utente_id, CASE p.livello WHEN 'gestore' THEN 'AMM_CMD' ELSE 'STAFF_CMD' END, u.comando_id, '*', 'migrazione', datetime('now','localtime')
  FROM permessi p JOIN settori s ON s.id = p.settore_id JOIN utenti u ON u.id = p.utente_id
  WHERE s.codice = 'puma' AND p.livello IN ('gestore','scrittura') AND u.comando_id IS NOT NULL AND u.is_admin = 0;
INSERT OR IGNORE INTO puma_ruoli_utente(utente_id, ruolo, sede_id, settore, assegnato_da, assegnato_il)
  SELECT p.utente_id, 'FUNZ_CMD', u.comando_id, UPPER(s.codice), 'migrazione', datetime('now','localtime')
  FROM permessi p JOIN settori s ON s.id = p.settore_id JOIN utenti u ON u.id = p.utente_id
  JOIN puma_settori ps ON ps.codice = UPPER(s.codice)
  WHERE p.livello = 'gestore' AND u.comando_id IS NOT NULL AND u.is_admin = 0;
INSERT OR IGNORE INTO puma_ruoli_utente(utente_id, ruolo, sede_id, settore, assegnato_da, assegnato_il)
  SELECT l.utente_id, 'ROR_DIR', dr.id, '*', 'migrazione', datetime('now','localtime')
  FROM puma_livello_utente l JOIN utenti u ON u.id = l.utente_id
  JOIN puma_comando_dir cd ON cd.comando_id = u.comando_id
  JOIN puma_comando_dir cdr ON cdr.direzione_id = cd.direzione_id
  JOIN comandi dr ON dr.id = cdr.comando_id AND dr.tipo = 'direzione'
  WHERE l.livello = 'regione';

-- Aree corsi: si possono aggiungere, rinominare, disattivare e riordinare (Area Comando -> Aree corsi).
-- modificata = 1: l'avvio non riporta più il nome di dati/tipologie.json; area_manuale = 1: il corso è stato spostato a mano.
ALTER TABLE puma_settori ADD COLUMN descrizione TEXT;
ALTER TABLE puma_settori ADD COLUMN attiva INTEGER NOT NULL DEFAULT 1;
ALTER TABLE puma_settori ADD COLUMN ordine INTEGER NOT NULL DEFAULT 0;
ALTER TABLE puma_settori ADD COLUMN modificata INTEGER NOT NULL DEFAULT 0;
ALTER TABLE puma_livelli ADD COLUMN area_manuale INTEGER NOT NULL DEFAULT 0;
ALTER TABLE puma_livelli ADD COLUMN attiva INTEGER NOT NULL DEFAULT 1;

-- Database località: luoghi di addestramento con punto, RV elicottero e RV ambulanza.
CREATE TABLE IF NOT EXISTS puma_localita(
  id INTEGER PRIMARY KEY,
  nome TEXT NOT NULL,
  tipo TEXT NOT NULL DEFAULT 'altro',
  comune TEXT,
  comando_id INTEGER NOT NULL REFERENCES comandi(id) ON DELETE CASCADE,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  rv_lat REAL, rv_lon REAL, rv_descr TEXT,
  amb_lat REAL, amb_lon REAL, amb_descr TEXT,
  aree TEXT,                -- aree corsi adatte, separate da virgola (vuoto = tutte)
  note TEXT,
  condivisa INTEGER NOT NULL DEFAULT 1,   -- 1 = la vedono anche gli altri Comandi
  attiva INTEGER NOT NULL DEFAULT 1,
  origine TEXT,             -- 'sede' per le sedi dei Comandi caricate in automatico
  creato_da TEXT,
  creato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(comando_id, nome));
ALTER TABLE puma_eventi ADD COLUMN localita_id INTEGER;
ALTER TABLE puma_eventi ADD COLUMN finalita TEXT;
ALTER TABLE puma_individuali ADD COLUMN localita_id INTEGER;

-- Inviti: link da mandare ai colleghi; al primo accesso con quell'utente l'account è subito attivo con il ruolo indicato.
CREATE TABLE IF NOT EXISTS puma_inviti(
  token TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  comando_id INTEGER REFERENCES comandi(id),
  ruolo TEXT REFERENCES puma_ruoli(codice),
  sede_id INTEGER REFERENCES comandi(id),
  settore TEXT NOT NULL DEFAULT '*',
  creato_da TEXT,
  creato_il TEXT,
  scade_il TEXT,
  usato_il TEXT);
