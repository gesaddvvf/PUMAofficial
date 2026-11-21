-- v1.5: documento d'impianto, presenza in turno/fuori turno, mail TEP e Formazione dei Comandi,
-- campi personalizzabili per sede (Trento, Bolzano, Aosta…), utenti non VVF (accesso con codice fiscale).

-- Presenza: in turno / fuori turno / anticipo / posticipo (12 ore del turno diurno o notturno in cui cade l'addestramento)
ALTER TABLE puma_checkin ADD COLUMN servizio TEXT;            -- in_turno | fuori_turno | anticipo | posticipo
ALTER TABLE puma_checkin ADD COLUMN variazione TEXT;          -- turno coperto con anticipo/posticipo, es. «diurno 21/11 (B7)»
ALTER TABLE puma_checkin ADD COLUMN variazione_min INTEGER;   -- ore coperte in minuti (720 = 12 ore)

-- Mail del Comando: TEP e Formazione (oltre a Sala Operativa)
ALTER TABLE comandi ADD COLUMN email_tep TEXT;
ALTER TABLE comandi ADD COLUMN email_formazione TEXT;

-- Campi personalizzabili del profilo per sede (Trento, Bolzano e Aosta non sono in WAUC)
CREATE TABLE IF NOT EXISTS puma_campi_sede(
  id INTEGER PRIMARY KEY,
  comando_id INTEGER NOT NULL REFERENCES comandi(id) ON DELETE CASCADE,
  etichetta TEXT NOT NULL,
  tipo TEXT NOT NULL DEFAULT 'testo' CHECK(tipo IN ('testo','elenco','data','numero')),
  opzioni TEXT,                 -- per «elenco»: una voce per riga
  obbligatorio INTEGER NOT NULL DEFAULT 0,
  ordine INTEGER NOT NULL DEFAULT 0,
  attivo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS puma_valori_campi(
  utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
  campo_id INTEGER NOT NULL REFERENCES puma_campi_sede(id) ON DELETE CASCADE,
  valore TEXT,
  PRIMARY KEY(utente_id, campo_id));
ALTER TABLE comandi ADD COLUMN profilo_libero INTEGER NOT NULL DEFAULT 0;   -- 1 = qualifica/distaccamento liberi (non da WAUC)
UPDATE comandi SET profilo_libero = 1 WHERE sigla IN ('TN','BZ','AO');
INSERT INTO puma_campi_sede(comando_id, etichetta, tipo, opzioni, obbligatorio, ordine)
  SELECT k.id, x.etichetta, x.tipo, x.opzioni, x.obbl, x.ordine FROM comandi k
  JOIN (SELECT 'Corpo di appartenenza' AS etichetta, 'elenco' AS tipo, 'Corpo permanente' || char(10) || 'Corpo volontario' || char(10) || 'Unione / Federazione distrettuale' AS opzioni, 1 AS obbl, 1 AS ordine
        UNION ALL SELECT 'Corpo / distaccamento', 'testo', NULL, 0, 2
        UNION ALL SELECT 'Matricola', 'testo', NULL, 0, 3) x
  WHERE k.sigla IN ('TN','BZ','AO')
    AND NOT EXISTS (SELECT 1 FROM puma_campi_sede c WHERE c.comando_id = k.id);

-- Utenti non VVF (Amministrazioni dello Stato, Forze armate, volontariato…): accesso con codice fiscale e password
ALTER TABLE utenti ADD COLUMN tipo_utente TEXT NOT NULL DEFAULT 'vvf';     -- vvf | esterno
ALTER TABLE utenti ADD COLUMN codice_fiscale TEXT;
ALTER TABLE utenti ADD COLUMN password_hash TEXT;
ALTER TABLE utenti ADD COLUMN ente_tipo TEXT;
ALTER TABLE utenti ADD COLUMN ente_nome TEXT;
ALTER TABLE utenti ADD COLUMN email_contatto TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_utenti_cf ON utenti(codice_fiscale) WHERE codice_fiscale IS NOT NULL;
INSERT OR IGNORE INTO puma_ruoli VALUES ('ESTERNO', 'Utente esterno (non VVF)', 'base', 13);

-- Documento d'impianto dell'addestramento: date e orari, sezioni con titolo libero, mappe e immagini
CREATE TABLE IF NOT EXISTS puma_impianti(
  id INTEGER PRIMARY KEY,
  titolo TEXT NOT NULL,
  area TEXT,
  evento_id INTEGER REFERENCES puma_eventi(id) ON DELETE SET NULL,
  comando_id INTEGER NOT NULL,
  stato TEXT NOT NULL DEFAULT 'bozza' CHECK(stato IN ('bozza','definitivo')),
  creato_da TEXT, creato_il TEXT, aggiornato_il TEXT);
CREATE TABLE IF NOT EXISTS puma_impianti_date(
  id INTEGER PRIMARY KEY,
  impianto_id INTEGER NOT NULL REFERENCES puma_impianti(id) ON DELETE CASCADE,
  data TEXT NOT NULL, ora_inizio TEXT, ora_fine TEXT, nota TEXT);
CREATE TABLE IF NOT EXISTS puma_impianti_sezioni(
  id INTEGER PRIMARY KEY,
  impianto_id INTEGER NOT NULL REFERENCES puma_impianti(id) ON DELETE CASCADE,
  ordine INTEGER NOT NULL DEFAULT 0,
  titolo TEXT NOT NULL,
  testo TEXT,
  lat REAL, lon REAL, rv_lat REAL, rv_lon REAL, amb_lat REAL, amb_lon REAL,
  mappa INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS puma_impianti_immagini(
  id INTEGER PRIMARY KEY,
  sezione_id INTEGER NOT NULL REFERENCES puma_impianti_sezioni(id) ON DELETE CASCADE,
  file TEXT NOT NULL, nome TEXT, didascalia TEXT, caricato_il TEXT);
