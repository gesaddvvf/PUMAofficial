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
6. **I colleghi** che accedono restano *in attesa* finché tu, da **Amministrazione → Utenti e permessi**, non li abiliti e assegni i settori:
   - **P.U.M.A.**: `lettura` per entrare, `scrittura` per creare e registrare, `gestore` per le Impostazioni;
   - **SAF / TPSS**: `lettura` = partecipa, `scrittura` = Responsabile, `gestore` = ROP (vede le scadenze).

   Il livello di visibilità (comando / regione / nazionale) si assegna da **P.U.M.A. → Livelli utenti**.
7. Per fermare PUMA **chiudi la finestra nera**. I dati restano in `data\`.

### Velocizzare il primo accesso (consigliato)
Senza indicazioni PUMA cerca la persona in WAUC in tutte le 107 province, e la prima volta può volerci un po'. Per cercare solo nel tuo Comando:
1. copia `puma.env.esempio` e chiama la copia **`puma.env`**;
2. aprila con il Blocco note e togli il `#` davanti alla riga `PUMA_WAUC_SEDI=FC` (metti le sigle che ti servono, separate da virgola, es. `FC,RA,RN`);
3. salva e riavvia `AVVIA.bat`.

### Usarlo da altri PC della rete
Di default PUMA si apre **solo dal PC su cui gira**. Per farlo usare anche ai colleghi, in `puma.env` togli il `#` da `PUMA_HOST=0.0.0.0` e riavvia. Gli altri PC aprono `http://<nome-o-IP-del-tuo-PC>:8080`; se Windows chiede il permesso del firewall, consenti la rete privata/di dominio.
Un PC personale con la VPN va bene per provare. Per un uso stabile serve un PC o server sempre acceso nella rete VVF, da concordare con chi gestisce la rete.

---

## 4. Se qualcosa non va

| Cosa vedi | Cosa fare |
|---|---|
| `Python non trovato su questo PC` | Installa Python (punto 1) spuntando **Add python.exe to PATH**, poi riprova. |
| `server di posta dipartimentale non raggiungibile … FortiClient VPN` | La VPN non è collegata o è caduta: ricollegala e riprova. Controlla con `VERIFICA_VPN.bat`. |
| `Credenziali non valide` | Scrivi solo `nome.cognome` (senza @vigilfuoco.it) e la password della posta dipartimentale. |
| Profilo non precompilato («Non risulti ancora in anagrafica») | Il login ha funzionato ma WAUC non ha risposto o non ti ha trovato: completa i dati a mano, oppure imposta `PUMA_WAUC_SEDI` e riprova più tardi. |
| `Errno 10048` / porta già in uso | PUMA è già aperto in un'altra finestra nera: chiudila. Oppure in `puma.env` imposta `PUMA_PORT=8081`. |
| La mappa resta grigia | Il PC non raggiunge `tile.openstreetmap.org`: controlla l'accesso a Internet (con alcune VPN Internet passa dalla rete VVF). |
| Pagina «Account in attesa di abilitazione» | Un amministratore deve abilitarti da *Amministrazione → Utenti e permessi*. |

Senza file `.bat`, dal Prompt dei comandi aperto nella cartella di PUMA:
```
py manage.py verifica-vpn      (controlla la VPN)
py app.py                      (avvio reale)
set PUMA_MODALITA=prova
py app.py                      (avvio di prova)
```
Su Linux: `./avvia_prova.sh`, `./verifica_vpn.sh`, `./avvia.sh`.

---

## 5. Aggiornare PUMA

Scarica la nuova versione e **sostituisci tutti i file tranne** la cartella `data\` (i tuoi dati), la cartella `data_prova\` e il file `puma.env`.
All'avvio PUMA aggiorna da solo il database, dopo averne fatto un backup in `data\backup\`.

Altre guide: [docs/GUIDA_PUMA.md](docs/GUIDA_PUMA.md) (uso di PUMA), [docs/GUIDA_ACCESSO_E_PROFILO.md](docs/GUIDA_ACCESSO_E_PROFILO.md) (login, WAUC, amministrazione), [docs/SVILUPPO.md](docs/SVILUPPO.md) (come aggiungere funzioni e moduli).
