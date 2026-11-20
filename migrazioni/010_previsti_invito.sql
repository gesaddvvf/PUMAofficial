-- v1.4: link d'invito per ogni addestramento collettivo e persone previste (da confermare il giorno dell'addestramento).
ALTER TABLE puma_eventi ADD COLUMN invito_token TEXT;
UPDATE puma_eventi SET invito_token = lower(hex(randomblob(12))) WHERE invito_token IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_eventi_invito ON puma_eventi(invito_token);

CREATE TABLE IF NOT EXISTS puma_previsti(
  evento_id INTEGER NOT NULL REFERENCES puma_eventi(id) ON DELETE CASCADE,
  email TEXT NOT NULL,                 -- nome.cognome@vigilfuoco.it (anche di chi non è ancora entrato in PUMA)
  nome TEXT,
  comando_id INTEGER,
  stato TEXT NOT NULL DEFAULT 'previsto' CHECK(stato IN ('previsto','confermato','assente')),
  origine TEXT NOT NULL DEFAULT 'responsabile',   -- responsabile | invito (si è segnato dal link)
  aggiunto_da TEXT,
  aggiunto_il TEXT,
  PRIMARY KEY(evento_id, email));
