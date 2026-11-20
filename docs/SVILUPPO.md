# Sviluppare PUMA

## Come è fatto

```
PUMAofficial/
├── app.py            nucleo: login, profilo da WAUC, utenti/permessi, amministrazione, caricamento dei moduli
├── config.py         impostazioni (modalità prova/reale, puma.env, WAUC, rete)
├── auth_imap.py      verifica delle credenziali dipartimentali sul server di posta (nessuna password salvata)
├── wauc.py           lettura dell'anagrafica del personale dall'API WAUC
├── profilo.py        ricerca della persona (WAUC → organico locale) e compilazione del profilo
├── rete.py           verifica dei collegamenti alla rete VVF (VPN) e del server di posta
├── db.py             SQLite + migrazioni automatiche (migrazioni/NNN_nome.sql)
├── manage.py         comandi da terminale (verifica-vpn, nomina-admin, backup…)
├── moduli/
│   ├── puma/         ★ modulo principale: si apre subito dopo il login (/puma/)
│   └── _esempio/     modello per nuove applicazioni (non viene caricato)
├── prova/            modalità prova: utenti fittizi e WAUC simulato (wauc_finto.json)
├── migrazioni/       schema del db, una migrazione per file
├── templates/ static/  pagine e grafica del nucleo (testata, login, amministrazione)
├── libs/             librerie Python pure (Flask, Waitress…): nessuna installazione
└── docs/             guide
```

**Flusso di una richiesta.** Il nucleo controlla la sessione e il CSRF, carica l'utente con i suoi permessi (`g.utente`, `g.perm`) e verifica che abbia accesso al settore del modulo. Il modulo si occupa solo delle proprie pagine.

**Grafica e navigazione.** Riprendono il sito gesaddvvf.github.io/PUMA: `templates/base.html` (intestazione, schede, menu ☰), `static/css/puma-app.css`, `static/js/puma-sito.js` (menu, turno/salto, ricerca documenti). Aree, schede e titoli delle pagine sono in `moduli/puma/navigazione.py`: per una pagina nuova aggiungi il suo endpoint a `PAGINE` e, se serve, una scheda in `GRUPPI`.

**Accesso diretto.** La pagina `/` porta al modulo indicato da `MODULO_PRINCIPALE` (default `puma`). Se un utente non è abilitato a PUMA ma lo è ad altre applicazioni, vede l'elenco delle app.

## Aggiungere una nuova applicazione (modulo)

1. Copia `moduli/_esempio` in `moduli/<nome>` (senza `_` iniziale: le cartelle con `_` vengono ignorate).
2. In `__init__.py` cambia `MODULO`:
   ```python
   MODULO = dict(codice='lance', nome='Lance', descrizione='Registro lance', settore='lance', settore_nome='Lance', icona='🚒')
   bp = Blueprint('lance', __name__, template_folder='templates', static_folder='static', static_url_path='/lance-static')
   ```
   - `codice`: indirizzo dell'app (`/lance/`) e nome del blueprint;
   - `settore`: permesso richiesto, creato da solo nella tabella `settori` e assegnabile da *Area Comando → Utenti e permessi*.
3. Pagine: `@bp.route('/')` con nome `index` (obbligatoria), template che fanno `{% extends 'base.html' %}`.
   Per i permessi di modifica usa `puo('lance', 'scrittura')` nel template e `current_app.extensions['puo']('lance', 'scrittura')` nel codice Python (non fare `import app` da un modulo: ricaricherebbe tutto).
4. Tabelle nuove: un file `migrazioni/007_lance.sql`. Non modificare mai una migrazione già distribuita: aggiungine una nuova.
5. Riavvia: il modulo compare nel menu **☰ → Applicazioni** di chi ha il settore.

Per fare di un altro modulo la pagina iniziale: `PUMA_MODULO_PRINCIPALE=<codice>` in `puma.env`.

## Lavorare su PUMA

- Codice del modulo: `moduli/puma/` (`__init__.py`: visibilità dei dati, home, attività, documenti; `addestramenti.py`: collettivi, individuali, interventi, mappa, scadenze, impostazioni; `piano.py` e `piano_pdf.py`: piano di sicurezza e PDF).
- Regole di visibilità: ogni record ha `comando_id`, `direzione_id`, `is_blindato`, `is_condiviso_nazionale`. Usa sempre `elenco()` o `scope_sql()` per leggere: così ognuno vede solo ciò che gli spetta.
- Dettagli funzionali: [GUIDA_PUMA.md](GUIDA_PUMA.md).

## Modalità prova e utenti fittizi

`PUMA_MODALITA=prova` (lo imposta `AVVIA_PROVA.bat`):
- db separato in `data_prova/`, password `dev`, nessuna VPN;
- `wauc._get()` non chiama la rete ma `prova/wauc_finto.py`, che risponde con i dati di `prova/wauc_finto.json` nella **stessa struttura dell'API reale** (`/api/Personale`, `/api/Specializzazioni`, `/api/ElencoQualifiche`, `/api/Sedi`): il codice provato è quello del login reale;
- all'avvio `prova.prepara()` crea l'amministratore di prova, gli utenti PUMA (`moduli/puma/demo.py`) e alcuni addestramenti di oggi.

**Aggiungere un utente di prova:** in `wauc_finto.json` copia una voce di `personale` e cambiane account, nome, sede e specializzazioni. Se deve avere un pulsante nella pagina di accesso, aggiungilo anche a `utenti_prova`. Per permessi e livelli PUMA aggiungilo anche a `UTENTI` in `moduli/puma/demo.py`. Poi `AZZERA_PROVA.bat` e riavvia.

## Provare il percorso reale senza VPN

Per controllare la lettura di WAUC via HTTP si può puntare PUMA a un server finto:
```
PUMA_WAUC_HTTP=http://127.0.0.1:8799  PUMA_WAUC_HTTPS=http://127.0.0.1:8799  PUMA_DEV_AUTH=1  PUMA_DATA=/tmp/prova_reale  python app.py
```
(`PUMA_DEV_AUTH=1` salta il server di posta: password `dev`. Mai in uso reale.)

## Git

- Branch per ogni modifica, poi pull request su `main`.
- **Mai** su GitHub: `data/`, `data_prova/`, `puma.env` (sono nel `.gitignore`).
- **Sì** su GitHub: `libs/`. Senza, PUMA non parte (era il problema del vecchio repository).
- I file `.bat` hanno fine riga Windows (CRLF), gli `.sh` Linux (LF): lo garantisce `.gitattributes`.
- Ogni script per Windows ha anche la versione `.sh` per Linux.


## Aggiungere pagine alle aree (v1.3)

Un modulo nuovo può comparire nelle aree di PUMA (schede sotto l'intestazione e menu ☰) senza toccare i template:

```python
from moduli.puma.navigazione import registra
registra('didattica', 'quiz.index', 'Quiz di autoverifica')          # Didattica e documentazione
registra('comando', 'magazzino.index', 'Magazzino', 'magazzino')     # Area Comando, solo con la capacità «magazzino»
```

Le capacità (permessi) dei livelli di accesso sono in `moduli/puma/ruoli.py` (CAPACITA e MATRICE). Nel codice:
`from moduli.puma.ruoli import accessi` → `accessi().puo('programma', 'SAF', sede_id)`, `accessi().sedi('report')`, `accessi().aree('programma')`.
