# P.U.M.A. — Istruzioni facili per farlo girare

PUMA è un programma in Python che gira sul tuo PC e si usa dal browser. Non serve installare librerie: sono già nella cartella `libs/`.

Ci sono **due modi** di avviarlo:

| | **Prova** (`AVVIA_PROVA.bat`) | **Reale** (`AVVIA.bat`) |
|---|---|---|
| Chi entra | utenti **fittizi** (pulsanti nella pagina di accesso) | tu e i colleghi, con le **credenziali dipartimentali** |
| Password | `dev` | quella della posta @vigilfuoco.it |
| Dati del personale | WAUC **simulato** | **WAUC vero** |
| Serve la VPN? | **no** | **sì: FortiClient VPN collegata** (o un PC sulla rete VVF) |
| Dove salva | cartella `data_prova\` | cartella `data\` |

Le due modalità non si mescolano mai: quello che fai in prova non finisce nei dati reali.

---

## 1. Cosa serve (una volta sola)

1. **Python 3.9 o più recente.** Per controllare: apri il *Prompt dei comandi* e scrivi `py --version`.
   Se non c'è, scaricalo da <https://www.python.org/downloads/>. Durante l'installazione **spunta «Add python.exe to PATH»** e poi premi *Install Now*.
2. **La cartella di PUMA.** Da GitHub (`gesaddvvf/PUMAofficial`): pulsante verde **Code → Download ZIP**, poi estrai lo zip, per esempio sul Desktop.
   La cartella deve contenere `AVVIA.bat`, `app.py` e la cartella `libs`.
3. **Per l'accesso reale:** FortiClient VPN installato e configurato con il tuo account (quello che usi già da casa).

> Se Windows mostra «Windows ha protetto il PC» al primo doppio clic su un file `.bat`, premi **Ulteriori informazioni → Esegui comunque**: succede perché i file arrivano da uno zip scaricato da Internet.

---

## Com'è fatto

PUMA ha la stessa grafica del sito <https://gesaddvvf.github.io/PUMA/>. In alto ci sono i pulsanti delle aree, e le pagine di ogni area compaiono come schede subito sotto:

| Area | Cosa contiene |
|---|---|
| **Home Page** | presentazione, aree, addestramenti di oggi, settori abilitati |
| **Attività** (rosso) | **Pianifica addestramento**, **Documento d'impianto** («＋ Crea»: date e orari, sezioni con titolo libero, mappe e immagini, stampa/PDF), (guidato: data, orari, area corsi, corso, finalità, squadra, località e RV da elenchi, persone previste), **Calendario addestramenti**, **Partecipa ad addestramento** (conferma presenza / «➕ Mi aggiungo»), **Redazione piano di sicurezza addestramento**, **Registrazione attività individuali** (solo corsi in possesso) |
| **Real Time** (verde) | Presenze Odierne, Mappa Real Time, Riepilogo Globale, Registro odierno |
| **Didattica e documentazione** (blu) | Manuali P.U.M.A., Manuali di settore, Circolari di settore, Archivio; qui arriveranno i moduli didattici (lezioni, video, quiz, schede tecniche) |
| **Area personale** (viola) | i tuoi dati, i tuoi livelli di accesso, corsi in possesso, situazione dell'anno, **Report individuale** (libretto), le tue attività, Interventi reali, Profilazione |
| **Reportistica** (giallo) | Report collettivo e Cruscotto corsi, per chi ha la capacità «report» (solo nelle sue aree corsi) |
| **Area Comando** (bianco) | Località, **Livelli di accesso**, **Inviti**, Aree corsi, Impostazioni, Corsi e foglio PUMA e — per l'Amministratore Generale — Utenti, Organico, Configurazione e WAUC, Comandi e Direzioni, Registro |

### Livelli di accesso
Ogni persona può avere uno o più livelli; ognuno vale per una **sede** e per un'**area corsi** (SAF, TPSS, NBCR… oppure tutte):

- **Amministratore Generale** (tutta Italia)
- **Direzione** (sede = Direzione Regionale, valgono anche per i suoi Comandi): Amministratore, Funzionario di settore, ROR, Staff, Magazzino
- **Comando** (sede = Comando, CON o SOCAV): Amministratore, Funzionario di settore, ROP, Staff, Magazzino
- **Operatore**: tutti gli altri (partecipa e registra le proprie attività)

Si assegnano da **Area Comando → Livelli di accesso** (l'Amministratore di Comando o di Direzione assegna quelli della sua sede e può abilitare chi è in attesa). Cosa può fare ogni livello è nella tabella in fondo a quella pagina: **è provvisoria** e si cambia in un solo punto, `moduli/puma/ruoli.py` (MATRICE). Le aree corsi si gestiscono da **Area Comando → Aree corsi**.

### Presenza: in turno / fuori turno
Chi conferma la presenza indica **In turno** o **Fuori turno** (PUMA lo propone dal turno e salto del profilo all'ora di inizio) ed eventuale **anticipo** o **posticipo** con i minuti. Il responsabile può correggerli quando conferma i previsti o convalida le presenze. Nella casella in alto a destra c'è il **tuo** turno e salto: pallino verde = in servizio adesso, arancio = di salto.

### Utenti non VVF
Amministrazioni dello Stato, Forze armate e di polizia, volontariato, Croce Rossa, CNSAS… si registrano da **Registrati** nella pagina di accesso e poi entrano con **codice fiscale** (gli spazi vengono tolti) e **password**. Possono solo partecipare agli addestramenti, vedere il proprio report individuale e i propri dati. Li abilita l'Amministratore del Comando scelto (**Livelli di accesso**, dove si può anche reimpostare la password o disabilitarli); chi si registra dal **link d'invito** di un addestramento è abilitato subito. SPID e CIE richiedono che PUMA sia un servizio accreditato su un indirizzo https pubblico: si potranno collegare quando sarà ospitato sui server del Dipartimento.

### Trento, Bolzano, Aosta (campi personalizzabili)
Queste sedi non sono in WAUC: nel profilo qualifica e distaccamento si scrivono liberamente e compaiono i campi decisi in **Area Comando → Campi personalizzati** (di serie: Corpo di appartenenza, Corpo/distaccamento, Matricola). La stessa funzione si può attivare per qualunque sede.

### Mail del Comando
In **Comandi e Direzioni** ogni sede ha anche **Email TEP** ed **Email Formazione**: il piano di sicurezza va anche a loro, oltre ai destinatari delle Impostazioni.

### Mappe
In tutte le mappe: **📍 Centra la mappa su un Comando** (poi sposti la mappa e scegli il luogo), **🎯 Localizzami** (funziona aprendo PUMA dal PC stesso o in https), **✛ croce** al centro con il pulsante **Usa la croce**, e una casella dove incollare le coordinate in qualunque formato: gradi decimali (`44.2225, 12.0408`), gradi-primi-secondi (`44°13'21"N 12°02'27"E`), gradi e primi, **UTM** (`33T 263634 4900845`), **MGRS**, link di Google Maps o OpenStreetMap. Sotto la mappa il punto è riportato in tutti i formati. Chi programma un addestramento parte dalla mappa centrata sul proprio Comando; le località salvate (Area Comando → Località) riempiono da sole area, RV elicottero e RV ambulanza.

**Come si usa un addestramento collettivo:** il responsabile lo *pianifica* per un giorno (corso, manovre previste, località) e indica le **persone previste** → dalla scheda copia il **link d'invito** e lo manda (e-mail o WhatsApp): chi lo apre entra con le credenziali dipartimentali e si segna tra i previsti → il giorno stabilito l'addestramento compare in *Partecipa ad addestramento*: i previsti premono **Confermo la presenza** (o li conferma il responsabile, presente/assente con il ruolo ICS), gli altri **Mi aggiungo** → il responsabile redige il *piano di sicurezza* e convalida le presenze → ore e manovre finiscono nel libretto di ognuno.

Il riquadro **Turno / Salto** mostra chi è in servizio adesso, come nel sito e in FireOps. Il menu **☰** contiene tutte le pagine, i tuoi dati e il pulsante **Esci**.

---

## 2. Provarlo subito, senza VPN

1. Doppio clic su **`AVVIA_PROVA.bat`**.
2. Si apre una finestra nera e, dopo un paio di secondi, il browser su <http://localhost:8080>.
3. Nella pagina di accesso scegli chi impersonare:
   - **Amministratore**: gestisce utenti, permessi e livelli;
   - **ROP / Responsabile**: crea addestramenti, piano di sicurezza, scadenze;
   - **Operatore**: check-in, addestramenti individuali, il mio profilo;
   - **ROR (regione)** e **Nazionale**: vedono più Comandi, in sola lettura;
   - **Primo accesso**: vedi come un utente nuovo riceve i dati da WAUC e resta in attesa che l'amministratore lo abiliti.
4. Per fermare PUMA **chiudi la finestra nera**.

Per ripartire da zero con i dati di prova: doppio clic su **`AZZERA_PROVA.bat`** (cancella solo `data_prova\`).

---

## 3. Accesso reale con la VPN

1. **Collega FortiClient VPN** come fai di solito, con il codice OTP se te lo chiede. Aspetta che risulti *Connesso*.
2. *(Facoltativo)* doppio clic su **`VERIFICA_VPN.bat`**. Deve comparire:
   ```
   [OK] Posta dipartimentale   imap-s.vigilfuoco.it:993 raggiungibile
   [OK] WAUC (http)            wauc.dipvvf.it:80 raggiungibile
   [OK] WAUC (https)           wauc.dipvvf.it:443 raggiungibile
   [OK] Lettura dati WAUC      … qualifiche ricevute
   ```
3. Doppio clic su **`AVVIA.bat`**. Il programma:
   - **[1/3]** ricontrolla la VPN. Se non è collegata te lo dice: collegala e riavvia, oppure premi un tasto per andare avanti lo stesso;
   - **[2/3]** solo la **prima volta** chiede l'utente dell'amministratore: scrivi il tuo `nome.cognome` e premi Invio;
   - **[3/3]** avvia PUMA e apre il browser su <http://localhost:8080>.
4. Accedi con **`nome.cognome`** (il dominio `@vigilfuoco.it` si aggiunge da solo) e la **password dipartimentale**.
   Sotto il modulo di accesso un riquadro mostra se la rete VVF è raggiungibile (✔ verde) oppure no (✖ rosso).
5. **Al primo accesso** PUMA ti cerca in WAUC e precompila i dati (comando, distaccamento, qualifica, turno, specializzazioni). Controllali e premi **Conferma**: entri direttamente in PUMA.
6. **I colleghi** che accedono restano *in attesa* finché tu, da **Area Comando → Utenti e permessi**, non li abiliti e assegni i settori:
   - **P.U.M.A.**: `lettura` per entrare, `scrittura` per creare e registrare, `gestore` per le Impostazioni;
   - **SAF / TPSS**: `lettura` = partecipa, `scrittura` = Responsabile, `gestore` = ROP (vede le scadenze).

   I livelli di accesso (Amministratore, Funzionario, ROR/ROP, Staff, Magazzino per sede e area corsi) si assegnano da **Area Comando → Livelli di accesso**.
7. Per fermare PUMA **chiudi la finestra nera**. I dati restano in `data\`.

### Corsi, ore minime e manovre previste (una volta, poi a ogni aggiornamento)
I report usano gli stessi dati del sito: i fogli *Formazione*, *Manovre_PREVISTE* ed *Elenco_Filtrato* del Google Sheet «PUMA VVF Database Personale».
1. Apri il foglio Google → **File → Scarica → Microsoft Excel (.xlsx)**.
2. In PUMA: **Area Comando → Corsi e foglio PUMA → Importa** e scegli il file (oppure `py manage.py importa-foglio "file.xlsx"`).
Gli altri fogli (registrazioni, piani) non vengono letti. I corsi in possesso arrivano da WAUC (specializzazioni, es. S1A, SBA, TPS…) e, per chi WAUC non trova, da *Elenco_Filtrato*.

### Velocizzare il primo accesso (consigliato)
Senza indicazioni PUMA cerca la persona in WAUC in tutte le 107 province, e la prima volta può volerci un po'. Per cercare solo nel tuo Comando:
1. copia `puma.env.esempio` e chiama la copia **`puma.env`**;
2. aprila con il Blocco note e togli il `#` davanti alla riga `PUMA_WAUC_SEDI=FC` (metti le sigle che ti servono, separate da virgola, es. `FC,RA,RN`);
3. salva e riavvia `AVVIA.bat`.

### Usarlo da altri PC della rete e mandare i link ai colleghi
1. Chiudi PUMA e avvialo con **`AVVIA_RETE.bat`** (invece di `AVVIA.bat`). La finestra nera mostra gli indirizzi da usare, es. `http://10.12.34.56:8080`. Se Windows chiede il permesso del firewall, consenti le reti **private / di dominio**.
2. In **Area Comando → Inviti** scrivi `nome.cognome` del collega, il Comando e il livello: PUMA crea un **link** (con il pulsante «Scrivi l'e-mail» lo mandi subito).
3. Il collega apre il link, entra con le sue credenziali dipartimentali e il suo account è **già attivo** con il livello scelto.

Cosa serve perché funzioni: il PC con PUMA deve restare **acceso con la finestra aperta** e i colleghi devono essere **nella stessa rete** (rete VVF del Comando). Da casa con FortiClient di solito due PC non si vedono tra loro: il link funziona per chi è in sede. Per un uso stabile serve un PC o server sempre acceso nella rete VVF, da concordare con chi gestisce la rete. Non va esposto su Internet.

---

## 4. Se qualcosa non va

| Cosa vedi | Cosa fare |
|---|---|
| `Python non trovato su questo PC` | Installa Python (punto 1) spuntando **Add python.exe to PATH**, poi riprova. |
| `server di posta dipartimentale non raggiungibile … FortiClient VPN` | La VPN non è collegata o è caduta: ricollegala e riprova. Controlla con `VERIFICA_VPN.bat`. |
| `Credenziali non valide` | Scrivi solo `nome.cognome` (senza @vigilfuoco.it) e la password della posta dipartimentale. Se è giusta, vedi «Il login non funziona» qui sotto. |
| Profilo non precompilato («Non risulti ancora in anagrafica») | Il login ha funzionato ma WAUC non ha risposto o non ti ha trovato. Fai doppio clic su **`PROVA_WAUC.bat`** (con la VPN): dice quante sedi rispondono e come risulti in WAUC (email, sede). Il risultato resta anche in `data\diagnosi_wauc.txt`. |
| `Errno 10048` / porta già in uso | PUMA è già aperto in un'altra finestra nera: chiudila. Oppure in `puma.env` imposta `PUMA_PORT=8081`. |
| La mappa resta grigia | Il PC non raggiunge `tile.openstreetmap.org`: controlla l'accesso a Internet (con alcune VPN Internet passa dalla rete VVF). |
| Pagina «Account in attesa di abilitazione» | Un amministratore deve abilitarti da *Area Comando → Utenti e permessi*. |

### Il login non funziona (con la VPN collegata)
1. Doppio clic su **`PROVA_LOGIN.bat`**: scrivi `nome.cognome` e la password (mentre scrivi non compare nulla). Il programma si collega al server di posta e mostra **la risposta esatta**:
   - `[!!] collegamento …` → il server di posta non si raggiunge: la VPN non è collegata o non instrada la posta;
   - `[!!] login: login rifiutato come «nome.cognome@vigilfuoco.it»: …` → il server rifiuta le credenziali. Controlla la password sulla webmail; se lì funziona, in `puma.env` aggiungi la riga `PUMA_IMAP_UTENTE=nome` (prova senza dominio) e ripeti la prova;
   - `[OK] login …` → le credenziali sono giuste: il login in PUMA funziona.
2. Ogni accesso negato, con il motivo, è scritto anche in `data\puma.log` e in **Area Comando → Registro attività**. La password non viene mai scritta.
3. Attenzione: troppi tentativi sbagliati possono bloccare l'account di posta.

Senza file `.bat`, dal Prompt dei comandi aperto nella cartella di PUMA:
```
py manage.py verifica-vpn      (controlla la VPN)
py manage.py prova-login       (prova le credenziali sul server di posta)
py manage.py diagnosi-wauc     (perché WAUC non trova una persona)
py app.py                      (avvio reale)
set PUMA_MODALITA=prova
py app.py                      (avvio di prova)
```
Su Linux: `./avvia_prova.sh`, `./verifica_vpn.sh`, `./prova_login.sh`, `./prova_wauc.sh`, `./avvia.sh`.

---

## 5. Aggiornare PUMA

Scarica la nuova versione e **sostituisci tutti i file tranne** la cartella `data\` (i tuoi dati), la cartella `data_prova\` e il file `puma.env`.
All'avvio PUMA aggiorna da solo il database, dopo averne fatto un backup in `data\backup\`.

Altre guide: [docs/GUIDA_PUMA.md](docs/GUIDA_PUMA.md) (uso di PUMA), [docs/GUIDA_ACCESSO_E_PROFILO.md](docs/GUIDA_ACCESSO_E_PROFILO.md) (login, WAUC, amministrazione), [docs/SVILUPPO.md](docs/SVILUPPO.md) (come aggiungere funzioni e moduli).
