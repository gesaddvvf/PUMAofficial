-- P.U.M.A.: punto di rendez-vous ambulanza (il punto RV esistente diventa "RV elicottero") e codice fiscale dei partecipanti.
ALTER TABLE puma_eventi ADD COLUMN amb_lat REAL;
ALTER TABLE puma_eventi ADD COLUMN amb_lon REAL;
ALTER TABLE puma_eventi ADD COLUMN amb_descr TEXT;
-- Il codice fiscale è inserito dall'utente al primo addestramento e riutilizzato; compare solo nei PDF (organizzazione e fogli firme).
CREATE TABLE IF NOT EXISTS puma_persone(utente_id INTEGER PRIMARY KEY REFERENCES utenti(id) ON DELETE CASCADE, codice_fiscale TEXT NOT NULL);
