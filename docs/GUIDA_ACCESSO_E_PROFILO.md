# P.U.M.A. — Accesso, profilo da WAUC e amministrazione

*Parte «nucleo» di PUMA (login con credenziali dipartimentali, profilo compilato da WAUC, utenti e permessi). Deriva dal Portale Unico VVF 0.2.0. Per installare e avviare PUMA vedi [ISTRUZIONI.md](../ISTRUZIONI.md).*


## 1. Che cos'è
PUMA si apre con **accesso con le credenziali dipartimentali**, **profilo personale compilato automaticamente dall'anagrafica WAUC**, **specializzazioni** e **gestione degli utenti** da parte degli amministratori. Dopo il login si entra direttamente in PUMA.

## 2. Per l'utente

### 2.1 Accedere
1. Apri PUMA dal browser (`http://localhost:8080` sul PC dove gira; da un altro PC `http://indirizzo-del-pc:8080`).
2. Nel campo **Utente** scrivi solo `nome.cognome`: `@vigilfuoco.it` è già mostrato accanto al campo. Se lo scrivi anche tu, viene tolto automaticamente.
3. Inserisci la **password dipartimentale** e premi *Accedi*. La password non viene mai salvata da PUMA.
4. In alto a destra puoi cambiare il tema **chiaro / scuro** (utile in sala operativa di notte).

### 2.2 Primo accesso: «Verifica i tuoi dati»
Al primo accesso PUMA ti cerca in WAUC con l'email inserita (in tutte le sedi) e precompila il profilo. Controlla e conferma:
- **Nome e cognome**: arrivano da WAUC e non si modificano.
- **Comando di appartenenza**: è la **provincia**, scritta per esteso.
- **Distaccamento, qualifica, tipo di personale, turno, salto turno**: sono menu con i soli valori presenti in WAUC. Il distaccamento mostra solo quelli del comando scelto.
- **Matricola e telefono**: campi liberi (non esistono in WAUC).
- Se non risulti in WAUC PUMA ricava solo nome e cognome dall'email: completa tu gli altri dati.

Dopo *Conferma e continua* resti **in attesa di abilitazione**: un amministratore ti assegna i settori di competenza.

### 2.3 Specializzazioni
Nella stessa pagina (sempre raggiungibile cliccando il tuo nome in alto):
- Sono elencate **tutte** le specializzazioni presenti in WAUC; usa il campo di ricerca per trovarle.
- Quelle che WAUC ti riconosce sono **già spuntate e non modificabili**, con la data di inizio; se sono **scadute** compare la data di scadenza.
- Per quelle che ti mancano: metti il **tic** e, se vuoi, una **data** (facoltativa).
- Se la specializzazione **non è in elenco**: pulsante **«+ Aggiungi specializzazione non presente»**, poi inserisci *codice*, *descrizione* e, se vuoi, la *data*. Entra nell'elenco, viene spuntata e diventa disponibile anche agli altri (con l'etichetta «non in WAUC»).
- Attenzione: premendo *Aggiungi* la pagina si ricarica e le altre modifiche non salvate si perdono. Aggiungi prima le mancanti, poi conferma il profilo.

### 2.4 Se qualcosa non torna
- *«Credenziali non valide»*: controlla utente (senza dominio) e password dipartimentale.
- *Dati di WAUC sbagliati*: PUMA li legge così come sono; la correzione va fatta dal tuo comando di appartenenza.
- *Elenco specializzazioni vuoto*: WAUC non era raggiungibile; ricarica tra qualche minuto o usa il pulsante di aggiunta.

## 3. Per l'amministratore

### 3.1 Primo amministratore
Da terminale, nella cartella di PUMA: `python manage.py nomina-admin nome.cognome`. Poi accedi normalmente.

### 3.2 Menu amministrazione
- **Utenti**: elenco con stato (in attesa / attivo / disabilitato) e **filtro per comando**. Nella scheda di ogni utente: abilitazione, comando, **settori e livelli** (lettura / scrittura / gestore), dati WAUC ricevuti (qualifica, gruppo, sede, tipo personale, turno) e specializzazioni con validità. Non puoi modificare il tuo stesso account.
- **Organico**: anagrafica locale (ricerca per nome/email, aggiunta, modifica, eliminazione). Si popola da sola con i profili confermati ed è usata se WAUC non trova la persona.
- **Configurazione**: comandi e settori; sezione **Anagrafiche WAUC** con le voci *Sedi*, *Qualifiche*, *Specializzazioni*, ciascuna con numero di record, data dell'ultimo aggiornamento e pulsante **«Crea o aggiorna dati»** (vedi sezione 5); link alle **Schede dei comandi**; sezione **Personale per sede** («Scopri sedi»: censisce le sedi con personale); **Elenco specializzazioni** (con validità, numero di persone e segnalazione di quelle aggiunte dagli utenti).
- **Registro**: tracciamento delle azioni (accessi anomali, abilitazioni, errori WAUC, modifiche).

### 3.3 Comandi da terminale (`python manage.py …`)
| Comando | A cosa serve |
|---|---|
| `nomina-admin EMAIL` / `revoca-admin EMAIL` | assegna o toglie il ruolo di amministratore |
| `utenti` | elenco utenti e stato |
| `wauc-test [EMAIL]` | prova il collegamento a WAUC e mostra cosa trova per quell'email |
| `wauc-sync` | scarica l'elenco completo di specializzazioni e qualifiche |
| `sync-sedi [CMD,UFC]` | scarica le sedi da `/api/Sedi` e le collega ai Comandi di PUMA |
| `sync-qualifiche` / `sync-specializzazioni` | scaricano solo l'elenco indicato |
| `comandi` | riepilogo delle schede dei comandi (contatti, PEC, NUE, intranet compilati) |
| `wauc-sedi` | censisce le sedi WAUC con personale (accelera la ricerca al login) |
| `specializzazioni` | stampa tutte le specializzazioni note |
| `organico` | elenco dell'anagrafica locale |
| `backup` / `esporta-csv` | copia del db / esportazione in CSV |

### 3.4 Prove e ripartenze
| Comando | Effetto |
|---|---|
| `reset-utente EMAIL` | cancella l'utente: al login successivo è un primo accesso |
| `reset-profilo EMAIL` | riparte la ricerca in WAUC mantenendo utente e permessi |
| `reset-db` | azzera utenti, permessi e registro (conserva organico, comandi, elenchi WAUC) |
| `reset-db --tutto` | ricrea l'intero db vuoto |

Ogni reset del db crea prima un backup in `data/backup/` (in prova: `data_prova/backup/`). Dopo un reset rifai `nomina-admin`.

### 3.5 Aggiornare PUMA
Sovrascrivi **tutti i file tranne la cartella `data/` (e `data_prova/`, `puma.env`)** (contiene db, chiave di sessione e backup) e riavvia. Lo schema del db si adegua da solo con backup automatico (da questa versione viene applicata anche la migrazione `006_anagrafiche_wauc.sql`, che aggiunge tabelle e colonne senza toccare i dati esistenti). Il db di PUMA si chiama `data/puma.db` (il vecchio `portale.db` del Portale Unico non viene letto).

## 4. Come funziona la ricerca in WAUC (in breve)
- L'email inserita viene cercata nei campi `accountDipvvf` / `emailVigilfuoco` dei record WAUC; se l'email non c'è, si prova `nome.cognome` (accettato solo se la corrispondenza è unica).
- Si interrogano tutte le sedi (sigle provinciali) in parallelo; la sede trovata viene ricordata per i login successivi.
- Se WAUC non risponde, l'accesso funziona comunque e il profilo si compila dall'organico locale.
- Tutti i dati ricevuti sono salvati e aggiornati a ogni accesso; ciò che l'utente conferma nel profilo resta come da lui scelto.

## 5. Anagrafiche WAUC e Schede dei comandi (novità 0.2.0)

### 5.1 Configurazione → Anagrafiche WAUC
Tre voci, ognuna con il proprio pulsante **«Crea o aggiorna dati»** (solo amministratori):

| Voce | Da dove | Dove finisce | A cosa serve |
|---|---|---|---|
| **Sedi** | `GET /api/Sedi` (tipi `CMD` = comandi e `UFC` = uffici) | tabella `sedi_wauc`; i comandi sono collegati ai Comandi di PUMA (per sigla provinciale) | schede dei comandi, in futuro distaccamenti e uffici |
| **Qualifiche** | `GET /api/ElencoQualifiche` (CNVVF e Amministrazione Civile) | `qualifiche_wauc` | menu del profilo; usi futuri |
| **Specializzazioni** | `GET /api/Specializzazioni` | `specializzazioni`, ora anche con data di inizio e fine validità | profilo utente e **P.U.M.A.** (portali di specializzazione; in futuro visualizzazione filtrata sulle specializzazioni dell'utente) |

- Il pulsante scarica di nuovo l'elenco e **aggiunge o aggiorna** le voci: non cancella nulla. Restano quindi le specializzazioni aggiunte dagli utenti e le schede dei comandi.
- Se WAUC non risponde o restituisce un elenco vuoto, il db **non viene modificato** e compare il messaggio d'errore (e una riga nel Registro).
- Le sedi possono richiedere qualche decina di secondi: la descrizione dell'API indica la chiave di ricerca come obbligatoria, per cui, se la richiesta senza chiave viene rifiutata, PUMA interroga lettere e cifre in parallelo e toglie i doppioni. Lascia aperta la pagina fino al messaggio di esito.
- Le specializzazioni e le qualifiche si aggiornano comunque da sole al login (ogni 24 ore); il pulsante serve per forzare l'aggiornamento.
- Da terminale: `python manage.py sync-sedi`, `sync-qualifiche`, `sync-specializzazioni`.

### 5.2 Configurazione → Schede dei comandi
Per ogni Comando (provincia) l'amministratore compila: **telefono e telefono 2, email, PEC, indirizzo, CAP, comune, latitudine e longitudine, NUE (sì / no / non noto) con note, sito web, sito intranet, note**.
- Questi dati non esistono in WAUC: sono inseriti a mano e **nessun aggiornamento da WAUC li sovrascrive**.
- Le coordinate inserite a mano prevalgono su quelle di WAUC (che compaiono comunque nell'elenco e nella scheda).
- Controlli: email e PEC con formato valido; siti solo `http://` o `https://` (se manca lo schema viene aggiunto `http://`); latitudine e longitudine insieme.
- Ogni salvataggio finisce nel Registro. `python manage.py comandi` mostra quanti comandi sono già compilati; `esporta-csv` include le nuove tabelle.

### 5.3 Limiti noti
- Il formato del campo `coordinate` di `/api/Sedi` non è documentato (nello Swagger è «string»): PUMA riconosce `46.14, 12.21`, `46,14;12,21` e `POINT(lon lat)`; il testo ricevuto è sempre conservato in `sedi_wauc.coordinate_raw`. Se una sede risulta senza coordinate, guarda quel campo.
- Il collegamento sede ↔ Comando usa la sigla provinciale (`codice`) e, in mancanza, il nome della provincia. Le sedi che non corrispondono a nessuna provincia restano in `sedi_wauc` senza collegamento.
- Il riconoscimento dei nomi dei comuni da coordinate (geocoding inverso con tabella ISTAT) **non è ancora incluso**: è previsto in seguito.
