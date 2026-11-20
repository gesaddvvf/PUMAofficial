-- P.U.M.A.: piano di sicurezza (orari, COD_ADD, ruoli ICS, matrici di rischio, catalogo manovre, sigle direzioni).
ALTER TABLE puma_eventi ADD COLUMN ora_inizio TEXT;
ALTER TABLE puma_eventi ADD COLUMN ora_fine TEXT;
ALTER TABLE puma_eventi ADD COLUMN cod_add TEXT;
ALTER TABLE puma_eventi ADD COLUMN org_dr INTEGER NOT NULL DEFAULT 0;
ALTER TABLE puma_eventi ADD COLUMN organizzazione TEXT;
ALTER TABLE puma_eventi ADD COLUMN matrice TEXT;
ALTER TABLE puma_checkin ADD COLUMN ruolo_ics TEXT;
ALTER TABLE puma_direzioni ADD COLUMN sigla TEXT;
ALTER TABLE puma_manovre ADD COLUMN corso TEXT;
ALTER TABLE puma_manovre ADD COLUMN codice TEXT;
ALTER TABLE puma_manovre ADD COLUMN ciclo TEXT;
ALTER TABLE puma_manovre ADD COLUMN numero INTEGER;
CREATE UNIQUE INDEX IF NOT EXISTS ux_puma_manovre_codice ON puma_manovre(codice) WHERE codice IS NOT NULL;
CREATE TABLE IF NOT EXISTS puma_ics_ruoli(codice TEXT PRIMARY KEY, nome TEXT NOT NULL, riga INTEGER NOT NULL, ordine INTEGER NOT NULL);
INSERT OR IGNORE INTO puma_ics_ruoli VALUES
 ('RESP','Responsabile addestramento (Incident Commander)',1,1),('SAFE','Responsabile sicurezza (Safety Officer)',2,2),
 ('COMM','Comunicazioni / radio',2,3),('SANI','Sanitario',2,4),('VET','Veterinario',2,5),('LOGI','Logistica (mezzi e attrezzature)',2,6),
 ('CAPO','Capo operazioni',3,7),('LEAD','Capo squadra / Leader',4,8),('OPER','Operatore',5,9);
CREATE TABLE IF NOT EXISTS puma_matrici(codice TEXT PRIMARY KEY, nome TEXT NOT NULL, soglia_medio INTEGER NOT NULL DEFAULT 34, soglia_alto INTEGER NOT NULL DEFAULT 67);
CREATE TABLE IF NOT EXISTS puma_fattori(id INTEGER PRIMARY KEY, matrice TEXT NOT NULL REFERENCES puma_matrici(codice) ON DELETE CASCADE,
  codice TEXT NOT NULL, descrizione TEXT NOT NULL, peso_max INTEGER NOT NULL, ordine INTEGER NOT NULL, UNIQUE(matrice,codice));
CREATE TABLE IF NOT EXISTS puma_opzioni(id INTEGER PRIMARY KEY, fattore_id INTEGER NOT NULL REFERENCES puma_fattori(id) ON DELETE CASCADE,
  testo TEXT NOT NULL, punteggio INTEGER NOT NULL, ordine INTEGER NOT NULL);
UPDATE puma_direzioni SET sigla = CASE nome WHEN 'Piemonte' THEN 'PIE' WHEN 'Valle d''Aosta' THEN 'VDA' WHEN 'Lombardia' THEN 'LOM'
 WHEN 'Trentino-Alto Adige' THEN 'TAA' WHEN 'Veneto' THEN 'VEN' WHEN 'Friuli Venezia Giulia' THEN 'FVG' WHEN 'Liguria' THEN 'LIG'
 WHEN 'Emilia-Romagna' THEN 'EMR' WHEN 'Toscana' THEN 'TOS' WHEN 'Umbria' THEN 'UMB' WHEN 'Marche' THEN 'MAR' WHEN 'Lazio' THEN 'LAZ'
 WHEN 'Abruzzo' THEN 'ABR' WHEN 'Molise' THEN 'MOL' WHEN 'Campania' THEN 'CAM' WHEN 'Puglia' THEN 'PUG' WHEN 'Basilicata' THEN 'BAS'
 WHEN 'Calabria' THEN 'CAL' WHEN 'Sicilia' THEN 'SIC' WHEN 'Sardegna' THEN 'SAR' END WHERE sigla IS NULL;
-- Correzione: TPSS = Tecniche di Primo Soccorso Sanitario (BLS-D, SVT), non "Topografia".
UPDATE puma_settori SET nome='TPSS – Tecniche di Primo Soccorso Sanitario' WHERE codice='TPSS' AND nome LIKE '%Topografia%';
UPDATE settori SET descrizione='P.U.M.A. - Tecniche di Primo Soccorso Sanitario' WHERE codice='tpss' AND descrizione LIKE '%Topografia%';
