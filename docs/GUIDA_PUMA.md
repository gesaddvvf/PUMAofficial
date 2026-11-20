# Guida a P.U.M.A. – Piattaforma Unificata Monitoraggio Addestramenti
Slogan: *Forma. Qualifica. Avanza.*

> **Novità di PUMAofficial 1.0**: PUMA è ora un'applicazione a sé: dopo il login si entra direttamente in PUMA (indirizzo `/puma/`). La modalità prova (`AVVIA_PROVA.bat` / `./avvia_prova.sh`) sostituisce `puma_demo.sh` e `avvia_locale.sh`: utenti fittizi, WAUC simulato, db separato in `data_prova/`. L'accesso reale (`AVVIA.bat` / `./avvia.sh`) richiede FortiClient VPN: vedi [ISTRUZIONI.md](../ISTRUZIONI.md). Le sezioni storiche qui sotto citano ancora il «portale»: oggi è il nucleo di PUMA (`app.py`).

## 1. Primo avvio (Admin)
1. Sovrascrivi i file del portale con il pacchetto di aggiornamento (la cartella `data/` non si tocca) e riavvia: le migrazioni `002_puma.sql` e `003_puma_livelli.sql` creano da sole le tabelle P.U.M.A. nel db del portale, con un backup automatico.
2. **Utenti → modifica utente**: assegna il livello al settore **P.U.M.A.** (`lettura` per entrare, `scrittura` per creare/registrare, `gestore` per le Impostazioni) e i livelli sui settori **SAF** / **TPSS** (`lettura` = partecipa, `scrittura` = Responsabile che crea gli addestramenti, `gestore` = ROP: vede le scadenze del personale).
3. **P.U.M.A. → Impostazioni** (gestore): e-mail di SO, ROP, ROR, SODIR, FORMAZIONE, TEP del tuo Comando e giorni di preavviso scadenze.
4. **Impostazioni → Validità**: mesi di validità per ogni livello (SAF Basico, SAF Avanzato, Retraining TPSS). I 12 mesi iniziali sono un segnaposto.
5. **Impostazioni → Checklist manovre**: aggiungi le manovre di ogni livello.

## 2. Settori
Dalla home si vedono solo i settori abilitati al proprio profilo (partiamo dai **SAF** poi il resto dovrebbe essere similare). Il ROP e gli admin vedono nella pagina del settore le **scadenze del personale** del proprio Comando.

## 3. Addestramenti collettivi (Responsabile)
1. **Nuovo addestramento**: data, tipologia, livello, **team** (Alfa…Zulu: un solo team per tipologia/giorno/Comando), titolo.
2. Clicca sulla mappa per l'**area** e poi per il **punto RV**.
3. Il giorno stesso il personale abilitato, di **qualsiasi Comando/Regione**, fa il **check-in mattutino** dalla scheda.
4. **Piano di sicurezza**: *Recupera meteo* (Open-Meteo, dalle coordinate) → compila la **matrice di rischio** (P×G, 1-4; livello = massimo dei fattori: ≤4 basso, ≤8 medio, ≤12 alto, >12 molto alto) → **Invia** via e-mail ai destinatari configurati.
5. **Convalida presenze** (spunta i presenti, opzione *Chiudi*). Solo le presenze convalidate entrano nel profilo.

## 4. Addestramenti individuali e interventi reali
- **Individuali**: scegli il livello, inserisci ora inizio/fine, spunta le manovre svolte.
- **Interventi reali**: registrazione sintetica per sola macro-categoria (es. SAF).

## 5. Mappa live
Mappa con gli addestramenti collettivi attivi oggi (aggiornamento ogni 30 s) e tabella presenze per ID/Team accanto. Clic sulla riga per aprire la scheda.

## 6. Profilo e scadenze
**Il mio profilo** mostra storico e scadenze (ultimo addestramento + mesi di validità). Con `./puma_scadenze.sh` (oppure `python3 manage.py puma-scadenze`), pianificato ogni giorno con cron, parte l'e-mail all'utente e al ROP quando mancano i giorni di preavviso. Ogni scadenza viene segnalata una sola volta.

## 7. Visibilità dei dati
Comando: propri dati. Direzione regionale: Comandi afferenti. Nazionale: tutti. In tutti i casi sono esclusi i record **riservati al Comando**; quelli condivisi a livello nazionale sono visibili a tutti. I check-in tra Comandi diversi funzionano su qualsiasi evento non riservato.

## 8. Configurazione tecnica
Variabili d'ambiente: `PUMA_SMTP_HOST`, `PUMA_SMTP_PORT`, `PUMA_SMTP_TLS`, `PUMA_SMTP_USER`, `PUMA_SMTP_PASS`, `PUMA_MAIL_FROM`; `PUMA_TILE_URL` (server di origine delle tile della mappa, default OpenStreetMap), `PUMA_TILE_UA` (User-Agent usato per scaricarle).
**Mappa**: le tile non vengono chieste dal browser a OpenStreetMap (il portale ha `Referrer-Policy: same-origin`, quindi OSM rispondeva 403). Le scarica il server del portale, con un User-Agent identificativo, e le tiene in cache in `data/puma_tiles/` per 7 giorni (se OSM non risponde si usa la copia in cache). I file in `data/puma_tiles/` sono le immagini della mappa già scaricate: è normale che compaiano in locale e si possono cancellare in qualsiasi momento. Il server deve poter raggiungere `tile.openstreetmap.org` e `api.open-meteo.com`; la politica d'uso di OSM non ammette un traffico elevato: per l'uso in produzione conviene un tile server interno o un fornitore con contratto (`PUMA_TILE_URL`). Alert scadenze: pianifica ogni giorno `puma_scadenze.sh` (es. cron `0 7 * * * /percorso/portale/puma_scadenze.sh`); le variabili `PUMA_*` possono stare in un file `puma.env` nella cartella del portale (una per riga, `NOME=valore`), letto da PUMA all'avvio (modello: `puma.env.esempio`).
PUMA si apre subito dopo il login, all'indirizzo `/puma/`.

## 9. Utenti di prova e livelli di visibilità
**Windows:** `AVVIA_PROVA.bat` · **Linux:** `./avvia_prova.sh`. All'avvio vengono creati (nel db separato `data_prova/`) gli utenti fittizi e alcuni addestramenti di oggi in più Comandi; nella pagina di accesso c'è un pulsante per ciascuno (password `dev`). I dati anagrafici arrivano dal WAUC simulato `prova/wauc_finto.json`. Oltre ai quattro qui sotto ci sono `demo.admin` (amministratore, Forlì-Cesena) e `demo.nuovo` (primo accesso: profilo da WAUC, poi attesa di abilitazione). Per ricominciare da zero: `AZZERA_PROVA.bat` (oppure cancellare `data_prova/`).

| Utente | Comando | Livello | Cosa deve vedere |
|---|---|---|---|
| demo.utente@vigilfuoco.it | Belluno | comando, SAF lettura | Solo Belluno + eventi condivisi nazionali; può fare check-in anche su eventi aperti di altri Comandi |
| demo.rop@vigilfuoco.it | Belluno | comando, SAF/P.U.M.A. gestore | Come l'utente + crea addestramenti, Impostazioni, scadenze del proprio Comando |
| demo.ror@vigilfuoco.it | Venezia | regione (Veneto) | Belluno e Treviso (non i riservati) + condivisi; scadenze della regione; sola lettura |
| demo.nazionale@vigilfuoco.it | Roma | nazionale | Tutti i Comandi, esclusi i riservati; sola lettura |

L'admin assegna il livello agli utenti reali da **P.U.M.A. → Livelli utenti**; la regione di ogni Comando è già mappata (migrazione `003`).
Check-in tra Comandi: la pagina *Addestramenti collettivi* elenca gli eventi di oggi aperti degli altri Comandi, per il personale abilitato al settore.

## 10. Non ancora incluso o da verificare
- **Alerting di prossimità** (perimetro provinciale/regionale e buffer in km): rimandato all'integrazione con FireOps, da creare.
- **Sito Google Sites originale**: ho letto solo la home; i contenuti reali delle altre pagine (Attività, Addestramenti odierni, Documentazione, Archivio) non sono stati replicati.
- **Segnaposto da correggere**: validità di 12 mesi per ogni livello; le manovre non sono precaricate (solo le tre `[demo]`), vanno inserite da Impostazioni.
- **Provati con risposta simulata**: meteo (Open-Meteo), invio e-mail e tile della mappa. Vanno verificati dal vero con internet e un server SMTP.

## 11. Struttura del modulo e dati
**File** (cartella `moduli/puma/`): `__init__.py` (adattatore al portale, regole di visibilità, home, attività, documenti, archivio), `addestramenti.py` (collettivi, individuali, interventi, mappa, scadenze, impostazioni, livelli, alert), `demo.py` (utenti e dati di prova), `templates/puma/`, `static/` (CSS, JS, logo, Leaflet in locale).
**Fuori dal modulo**: `app.py` (nucleo: login, profilo, amministrazione, CSP per le mappe), `manage.py` (comandi `verifica-vpn`, `puma-scadenze`…), `templates/` e `static/css/puma-app.css` (testata e login col marchio P.U.M.A.), `migrazioni/002…005`, `prova/` (utenti fittizi e WAUC simulato), script `AVVIA*.bat` / `avvia*.sh`, `puma_scadenze.sh`.
**Tabelle**: `puma_settori`, `puma_livelli`, `puma_manovre`, `puma_config`, `puma_destinatari`, `puma_eventi`, `puma_checkin`, `puma_individuali`, `puma_interventi`, `puma_documenti`, `puma_attivita`, `puma_addestramenti`, `puma_alert_inviati`, `puma_direzioni`, `puma_comando_dir`, `puma_livello_utente`. Ogni record dei dati ha `comando_id`, `direzione_id`, `is_blindato`, `is_condiviso_nazionale`.

## 12. Permessi in sintesi
| Azione | Permesso richiesto |
|---|---|
| Aprire P.U.M.A. | `lettura` sul settore P.U.M.A. |
| Check-in, individuali, interventi | `lettura` sul settore dell'addestramento (es. SAF) |
| Creare addestramento collettivo, piano, convalide | `scrittura` su P.U.M.A. e sul settore; solo sul proprio Comando |
| Impostazioni (e-mail, validità, manovre), scadenze del settore | `gestore` |
| Livelli utenti | admin del portale |
Il livello di visibilità (comando / regione / nazionale) si assegna da **P.U.M.A. → Livelli utenti**.

## 13. Organizzazione del lavoro (Git)
- **Cartella da toccare**: solo `moduli/puma/`. Se serve una modifica allo schema del db si aggiunge una **nuova** migrazione (`004_…sql`, ecc.) in `migrazioni/`; le migrazioni `002` e `003` non si modificano mai, perché il portale le applica una volta sola.
- **Prima di reinviare il progetto**: tutti hanno fatto `git pull` e `git push`; si evita che due persone modifichino lo stesso file insieme; si invia solo `moduli/puma` e `migrazioni/` (senza `data/` e `libs/`).

- **`.gitignore`**: aggiungere `data/`, `puma.env`, `__pycache__/`. `data/portale.db` e `data/secret.key` non devono stare su GitHub; se già caricati vanno tolti dalla cronologia e `secret.key` va rigenerata. `puma.env` contiene le credenziali SMTP.
- **Demo**: solo in modalità prova (db separato `data_prova/`), mai sul db reale. Prima di una pubblicazione reale: `python manage.py puma-demo --rimuovi`.
- **Convenzione**: ogni script consegnato ha anche la versione `.sh` per Linux.

## 14. Cronologia
- **PUMAofficial 1.0**: applicazione autonoma con accesso diretto a PUMA, marchio P.U.M.A. su testata e login, modalità prova con utenti fittizi e WAUC simulato, verifica della VPN (`VERIFICA_VPN.bat`, stato del collegamento nella pagina di accesso), librerie incluse in `libs/`.
- v1: pagine del sito P.U.M.A. ricreate (home, attività, addestramenti odierni, documentazione, archivio).
- v2: moduli collettivi, individuali, interventi, mappa live, profilo e scadenze, impostazioni.
- v3: integrazione nel portale (`/m/puma/`, permessi del portale, CSRF, CSP, migrazioni), card in home con logo.
- v8: codice fiscale dei partecipanti, RV elicottero e RV ambulanza con simboli e legenda su mappe e PDF, pittogrammi meteo, canali radio in prima pagina.
- v7: piano di sicurezza completo (COD_ADD, orari, registrazione con ruolo ICS, matrici di rischio A/B/C, meteo a 3 h, PDF, catalogo manovre, correzione del nome TPSS).
- v6: mappe mostrate per intero (mancava il collegamento al foglio di stile di Leaflet, `vendor/leaflet.css`).
- v5: correzione errore 403 delle mappe (tile tramite proxy con cache del portale).
- v4: utenti demo, livelli comando/regione/nazionale, check-in tra Comandi, script `.sh`.

## 15. Piano di sicurezza (v7)
**Nuove migrazioni fuori dal modulo**: `migrazioni/004_puma_piano.sql` e `migrazioni/005_puma_rv_cf.sql` (colonne orari/COD_ADD/ICS, tabelle delle matrici, sigle delle direzioni, correzione del nome TPSS). Va committata una volta.

**1. Pianificazione (Responsabile).** Data (anche futura: l'elenco mostra di default solo gli addestramenti di oggi, con filtri Programmati / Passati / Tutti / giorno), ora inizio e fine, tipologia e livello, squadra (Alfa…Zulu), Comando organizzatore (o Direzione Regionale), coordinate dell'area e punto **RV elicottero** e punto **RV ambulanza**.
**COD_ADD** generato in automatico: `TIPOLOGIA-SQUADRA-<DIREZIONE><COMANDO>-AAAAMMGG`, ad es. `SAF-ALFA-VENBL-20261006`; se organizza la Direzione Regionale: `SAF-ALFA-VENDR-20261006`. Le sigle delle direzioni sono nella tabella `puma_direzioni` (VEN, LOM, PIE…); la sigla del Comando è quella della provincia.

**2. Il giorno dell'addestramento (personale, anche da telefono).** Dopo il login: *Addestramenti collettivi → Aperti oggi* (o la scheda) → **Mi registro**: si vede il riepilogo con il COD_ADD, si sceglie il proprio **ruolo ICS** e si spunta *«Confermo: è l'addestramento giusto»*. Ruoli ICS di partenza (tabella `puma_ics_ruoli`): Responsabile addestramento (Incident Commander), Responsabile sicurezza, Comunicazioni, Sanitario, Veterinario, Logistica, Capo operazioni, Capo squadra/Leader, Operatore. Il Responsabile può correggere i ruoli nella scheda.
> Per lavorare «da telefono senza FortiClient» il portale (o almeno questa funzione) deve essere raggiungibile da fuori della rete interna: è una scelta di infrastruttura e sicurezza da concordare con chi gestisce la rete; il codice non la risolve.

**3. Completamento del piano (Responsabile)**, dalla scheda → *Piano di sicurezza*:
1. **Meteo**: recuperato da solo dalle coordinate, a passi di 3 ore nella fascia oraria dell'addestramento (previsioni fino a circa 16 giorni).
2. **Organizzazione**: canali radio, attrezzature e mezzi con i responsabili (una riga «voce | responsabile»), veterinario se necessario, note.
3. **Matrice di rischio**: si sceglie la matrice (A, B ambiente fluviale, C corso di formazione), si selezionano le opzioni, e in alto resta visibile l'**anteprima** di punteggio e livello. Una opzione da 100 punti rende il rischio **CRITICO** (addestramento da non svolgere così com'è). Il livello BASSO/MEDIO/ALTO è la percentuale sul massimo: **le soglie attuali (medio da 34%, alto da 67%) sono provvisorie** e stanno in `puma_matrici`; vanno confermate.
4. **PDF e invio** a SO e indirizzi configurati (ROP, ROR, SODIR, Formazione, TEP) con allegati.

**PDF completo** (generato dal portale, senza programmi esterni): 1 riepilogo con mappa per il funzionario di guardia · 2 vuota (fronte/retro) · 3 riepilogo con mappa per la SO · 4 organizzazione dell'addestramento · 5 matrice di rischio con tabella punteggi e diagramma a ragnatela · 6 schema ICS · 7… fogli firme (20 righe per pagina, nominativi già compilati).
**PDF ridotto**: solo pagine 3, 4 e fogli firme (casella «Invia solo la versione ridotta»).
**Allegato manovre**: secondo file con le sole manovre della specializzazione dell'addestramento (livello scelto), con casella da spuntare.

**Catalogo manovre.** Importato dal file fornito: BAS → *SAF Basico* (5), AVA → *SAF Avanzato* (28, con le 4 versioni della manovra 39), TPS → *Retraining TPSS* (4). Le manovre compaiono nella checklist dell'addestramento individuale. Il caricamento iniziale avviene una volta sola: le modifiche fatte poi da Impostazioni restano.
**Matrici.** Importate dalla tabella fornita (A: 12 fattori, B: 19, C: 2). Nel file originale l'ultimo record ha il codice C02 ma l'etichetta «C01 Completamento grafico»: l'ho trattato come fattore C02.
**Correzione.** TPSS è *Tecniche di Primo Soccorso Sanitario* (BLS-D, SVT, PBLS-D), non «Topografia»: corretto nei settori.
**Libreria PDF.** `moduli/puma/vendor/reportlab` (inclusa, nessuna installazione, funziona senza Pillow). I dati importati sono in `moduli/puma/dati/`.

**Da definire.** (a) soglie reali basso/medio/alto; (b) quanti fogli firme servono («pag. 7…3n+2»): per ora una pagina ogni 20 persone; (c) quale matrice vale per quale tipologia/livello (ora la sceglie il Responsabile); (d) eventuale compilazione automatica dei fattori Meteo (A07/B05) e Temperatura (A08/B06) dal meteo recuperato.

## 16. Mappe, codice fiscale e PDF (v8)
**Simboli (mappa e PDF), con legenda sotto la mappa nelle pagine e nei PDF**: pallino **rosso** = area dell'addestramento · cerchio **verde con H** = RV elicottero · cerchio **verde con croce** = RV ambulanza. In creazione si sceglie il tipo di punto (Area / RV elicottero / RV ambulanza) e si clicca sulla mappa. La mappa live mostra gli stessi tre simboli.
**Codice fiscale.** Chiesto una sola volta nella registrazione all'addestramento (controllo del formato e del carattere di controllo), riutilizzato nei successivi. Compare **solo nei PDF** (pagina 4 «Organizzazione» e fogli firme), non nelle liste a video. È un dato personale: conservarlo e stampare i PDF secondo le regole di riservatezza dell'amministrazione. Nei dati demo i codici fiscali sono fittizi.
**PDF.** Il canale radio è anche in pagina 1, insieme a una riga meteo con pittogrammi (sereno, poco nuvoloso, nuvoloso, coperto, nebbia, pioggia, neve, temporale); i pittogrammi sono anche nella tabella meteo di pagina 3 e nella pagina del piano. La **pagina 2 resta bianca** (fronte/retro).
