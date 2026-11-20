-- Corsi e manovre come nel sito gesaddvvf.github.io/PUMA (fogli Formazione e Manovre_PREVISTE del «PUMA VVF Database Personale").
-- puma_livelli diventa il catalogo delle TIPOLOGIE (es. «SAF (Speleo Alpino Fluviale) BASICO»), con i requisiti del libretto;
-- puma_settori le CATEGORIE (SAF, SSA, USAR, TPSS, TAS, NBCR...). Il catalogo è caricato da moduli/puma/dati/tipologie.json
-- e i requisiti da  python manage.py importa-foglio <file.xlsx>.
ALTER TABLE puma_livelli ADD COLUMN sigla TEXT;
ALTER TABLE puma_livelli ADD COLUMN chiave TEXT;                 -- nome del logo (static/img/tipologie/<chiave>.svg)
ALTER TABLE puma_livelli ADD COLUMN corso INTEGER NOT NULL DEFAULT 1;   -- 0 = tipologia di attività (Esercitazione, Altro...), non un corso
ALTER TABLE puma_livelli ADD COLUMN ore_minime REAL;             -- ore richieste nel periodo («Ore Minime»)
ALTER TABLE puma_livelli ADD COLUMN quota_collettive REAL;       -- frazione delle ore minime da fare in collettivi («Collettive (in %)»: 0.5 = 50%)
ALTER TABLE puma_livelli ADD COLUMN delta_anni INTEGER NOT NULL DEFAULT 0;   -- anni precedenti che contano (1 = anche l'anno prima)
ALTER TABLE puma_livelli ADD COLUMN sovraordinazione REAL;       -- ordine nel libretto
ALTER TABLE puma_livelli ADD COLUMN profilazione TEXT;           -- nome del corso nella profilazione («Corsi (Profilazione)»)
ALTER TABLE puma_livelli ADD COLUMN codici_wauc TEXT;            -- specializzazioni WAUC che danno il corso in possesso (es. S1A,SBA)
ALTER TABLE puma_livelli ADD COLUMN di_tutti INTEGER NOT NULL DEFAULT 0;     -- in possesso di tutti (Competenze primarie SAF, TPSS)
ALTER TABLE puma_livelli ADD COLUMN equivale_a INTEGER;          -- si conta come un altro corso (SAF1A -> Competenze primarie)
ALTER TABLE puma_livelli ADD COLUMN ordine INTEGER NOT NULL DEFAULT 0;
ALTER TABLE puma_livelli ADD COLUMN da_foglio TEXT;              -- data dell'ultimo import dal foglio Formazione

-- Manovre previste (Manovre_PREVISTE: A corso, B UID, C codice, D ciclo, E manovra, F testo; lettera finale A/B/C/N)
ALTER TABLE puma_manovre ADD COLUMN uid TEXT;
ALTER TABLE puma_manovre ADD COLUMN lettera TEXT;
ALTER TABLE puma_manovre ADD COLUMN testo TEXT;
ALTER TABLE puma_manovre ADD COLUMN da_foglio INTEGER NOT NULL DEFAULT 0;

-- Addestramenti: manovre previste scelte nella programmazione e descrizione; individuali: descrizione
ALTER TABLE puma_eventi ADD COLUMN manovre TEXT;
ALTER TABLE puma_eventi ADD COLUMN descrizione TEXT;
ALTER TABLE puma_individuali ADD COLUMN descrizione TEXT;

-- Nomi dei livelli esistenti allineati alle tipologie del sito (i riferimenti restano)
UPDATE puma_livelli SET nome = 'SAF (Speleo Alpino Fluviale) BASICO' WHERE nome = 'SAF Basico';
UPDATE puma_livelli SET nome = 'SAF (Speleo Alpino Fluviale) AVANZATO' WHERE nome = 'SAF Avanzato';
UPDATE puma_livelli SET nome = 'TPSS (Tecniche di Primo Soccorso Sanitario)' WHERE nome = 'Retraining TPSS';

-- Corsi in possesso letti dal foglio Elenco_Filtrato (quando WAUC non trova la persona): Cognome Nome - Codice Fiscale
CREATE TABLE IF NOT EXISTS puma_possesso_foglio(
  chiave TEXT PRIMARY KEY,          -- cf:<CODICE FISCALE> oppure n:<cognomenome normalizzato>
  nominativo TEXT, codice_fiscale TEXT, comando TEXT, qualifica TEXT, corsi TEXT, importato_il TEXT);
