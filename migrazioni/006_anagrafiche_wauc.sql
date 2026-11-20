-- Anagrafiche WAUC: sedi (/api/Sedi), validità delle specializzazioni (/api/Specializzazioni) e scheda di contatto dei comandi.
-- Gli aggiornamenti da WAUC riscrivono solo sedi_wauc e i cataloghi: la scheda dei comandi (contatti, PEC, NUE, siti) è inserita a mano e non viene mai toccata.
ALTER TABLE specializzazioni ADD COLUMN data_inizio_validita TEXT;
ALTER TABLE specializzazioni ADD COLUMN data_fine_validita TEXT;

CREATE TABLE sedi_wauc(
  id TEXT PRIMARY KEY,                      -- id WAUC della sede
  codice TEXT,                              -- per i comandi = sigla provinciale
  cod_distaccamento TEXT,
  descrizione TEXT,
  tipo TEXT, desc_tipo TEXT, tipo_originale TEXT,
  tipologia_codice TEXT, tipologia_descrizione TEXT,
  provincia TEXT,
  coordinate_raw TEXT,                      -- testo ricevuto da WAUC, conservato com'è
  lat REAL, lon REAL,                       -- coordinate lette dal testo (NULL se non riconosciute)
  id_sede_padre TEXT, cod_aoo TEXT,
  cod_tipo_dipartimento TEXT,               -- parametro con cui è stata scaricata: CMD (comandi), UFC (uffici)...
  comando_id INTEGER REFERENCES comandi(id) ON DELETE SET NULL,
  aggiornata_il TEXT);
CREATE INDEX idx_sedi_wauc_tipo ON sedi_wauc(cod_tipo_dipartimento);
CREATE INDEX idx_sedi_wauc_comando ON sedi_wauc(comando_id);

-- Scheda del comando (= provincia): dati non presenti in WAUC, inseriti da un amministratore (menu Configurazione > Schede dei comandi).
ALTER TABLE comandi ADD COLUMN wauc_sede_id TEXT;       -- sede CMD di WAUC collegata (id di sedi_wauc)
ALTER TABLE comandi ADD COLUMN telefono TEXT;
ALTER TABLE comandi ADD COLUMN telefono2 TEXT;
ALTER TABLE comandi ADD COLUMN email TEXT;
ALTER TABLE comandi ADD COLUMN pec TEXT;
ALTER TABLE comandi ADD COLUMN indirizzo TEXT;
ALTER TABLE comandi ADD COLUMN cap TEXT;
ALTER TABLE comandi ADD COLUMN comune TEXT;
ALTER TABLE comandi ADD COLUMN lat REAL;                -- se valorizzate prevalgono sulle coordinate WAUC
ALTER TABLE comandi ADD COLUMN lon REAL;
ALTER TABLE comandi ADD COLUMN nue INTEGER;             -- 1 = ha il NUE, 0 = non lo ha, NULL = non noto
ALTER TABLE comandi ADD COLUMN nue_note TEXT;
ALTER TABLE comandi ADD COLUMN sito_web TEXT;
ALTER TABLE comandi ADD COLUMN sito_intranet TEXT;
ALTER TABLE comandi ADD COLUMN note TEXT;
ALTER TABLE comandi ADD COLUMN contatti_aggiornati_il TEXT;
