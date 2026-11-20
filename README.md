# P.U.M.A. — Piattaforma Unificata Monitoraggio Addestramenti

*Forma. Qualifica. Avanza.* — Corpo Nazionale dei Vigili del Fuoco

Applicazione web per gli addestramenti del personale: addestramenti collettivi (con check-in, piano di sicurezza e PDF), individuali, interventi reali, mappa live, scadenze, documentazione e archivio.

- **Accesso diretto a PUMA** con le credenziali dipartimentali (posta @vigilfuoco.it).
- **Profilo compilato da WAUC** (comando, distaccamento, qualifica, turno, specializzazioni).
- **Modalità prova** con utenti fittizi e WAUC simulato: si prova tutto senza VPN e senza dati reali.
- Python puro, **nessuna installazione**: le librerie sono in `libs/`.

## Avvio rapido (Windows)

| Voglio… | Faccio doppio clic su |
|---|---|
| provarlo con utenti fittizi, senza VPN | `AVVIA_PROVA.bat` |
| controllare che la VPN funzioni | `VERIFICA_VPN.bat` |
| usarlo davvero (FortiClient VPN collegata) | `AVVIA.bat` |

Si apre il browser su <http://localhost:8080>. Per fermarlo chiudi la finestra nera.
Su Linux: `./avvia_prova.sh`, `./verifica_vpn.sh`, `./avvia.sh`.

👉 **Istruzioni passo-passo: [ISTRUZIONI.md](ISTRUZIONI.md)**

## Documentazione
- [ISTRUZIONI.md](ISTRUZIONI.md): installazione, prova, accesso reale con VPN, problemi frequenti
- [docs/GUIDA_PUMA.md](docs/GUIDA_PUMA.md): funzioni di PUMA, permessi, piano di sicurezza
- [docs/GUIDA_ACCESSO_E_PROFILO.md](docs/GUIDA_ACCESSO_E_PROFILO.md): login, WAUC, amministrazione, comandi da terminale
- [docs/SVILUPPO.md](docs/SVILUPPO.md): struttura del codice, nuovi moduli, utenti di prova

Requisiti: Python 3.9 o successivo. Per l'accesso reale: rete VVF oppure FortiClient VPN.
