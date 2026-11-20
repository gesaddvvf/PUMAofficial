-- Sedi di appartenenza allineate a FireOps (db/comandi.json, direzioni.json, CON.json, SOCAV.json):
--  * i Comandi sono quelli VVF (107): in Sardegna Cagliari, Sassari, Nuoro, Oristano (niente «Sud Sardegna»);
--  * le Direzioni regionali sono 19 come in FireOps («Veneto e TAA» comprende Belluno…Verona, Trento e Bolzano);
--  * Direzioni regionali, CON e SOCAV diventano anche sedi di appartenenza (tabella comandi, colonna tipo),
--    così il personale delle Direzioni e del CON può registrarsi e organizzare addestramenti.
-- I contatti (telefoni SO, email, PEC, indirizzi, coordinate, canali radio) sono caricati all'avvio da dati/fireops/ (anagrafiche.py)
-- solo nei campi vuoti: quello che un amministratore modifica a mano non viene sovrascritto.

ALTER TABLE comandi ADD COLUMN tipo TEXT NOT NULL DEFAULT 'comando';   -- comando | direzione | nazionale
ALTER TABLE comandi ADD COLUMN regione TEXT;
ALTER TABLE comandi ADD COLUMN telefono_so TEXT;
ALTER TABLE comandi ADD COLUMN email_so TEXT;
ALTER TABLE comandi ADD COLUMN pec_so TEXT;
ALTER TABLE comandi ADD COLUMN canale_radio TEXT;
ALTER TABLE comandi ADD COLUMN fonte_contatti TEXT;                    -- 'fireops' se i contatti arrivano da FireOps

-- «Sud Sardegna» non è un Comando VVF: chi l'aveva scelto torna da completare
UPDATE utenti SET comando_id = NULL WHERE comando_id IN (SELECT id FROM comandi WHERE sigla = 'SU');
UPDATE sedi_wauc SET comando_id = NULL WHERE comando_id IN (SELECT id FROM comandi WHERE sigla = 'SU');
DELETE FROM comandi WHERE sigla = 'SU';

-- Direzioni come in FireOps: Veneto e Trentino-Alto Adige formano «Veneto e TAA»
UPDATE puma_direzioni SET nome = 'Veneto e TAA' WHERE nome = 'Veneto';
UPDATE puma_comando_dir SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
UPDATE puma_eventi SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
UPDATE puma_individuali SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
UPDATE puma_interventi SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
UPDATE puma_attivita SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
UPDATE puma_addestramenti SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
UPDATE puma_documenti SET direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Veneto e TAA')
  WHERE direzione_id = (SELECT id FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige');
DELETE FROM puma_direzioni WHERE nome = 'Trentino-Alto Adige';

-- Una sede «Direzione Regionale …» per ogni Direzione, legata alla sua Direzione
INSERT OR IGNORE INTO comandi(nome, tipo, regione) SELECT 'Direzione Regionale ' || nome, 'direzione', nome FROM puma_direzioni;
INSERT OR IGNORE INTO puma_comando_dir(comando_id, direzione_id)
  SELECT k.id, d.id FROM comandi k JOIN puma_direzioni d ON k.nome = 'Direzione Regionale ' || d.nome WHERE k.tipo = 'direzione';

-- Livello nazionale: Centro Operativo Nazionale e Sala Operativa del Centro Assistenza al Volo (nessuna Direzione)
INSERT OR IGNORE INTO comandi(nome, sigla, tipo, regione) VALUES ('CON - Centro Operativo Nazionale VVF', 'CON', 'nazionale', 'Lazio'),
  ('SOCAV - Centro Assistenza al Volo', 'SOCAV', 'nazionale', 'Lazio');
