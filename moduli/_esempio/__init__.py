"""Modello per una nuova applicazione accanto a PUMA (vedi docs/SVILUPPO.md).
Le cartelle che iniziano con «_» non vengono caricate: copia questa cartella con un nome senza «_» (es. moduli/lance)
e cambia MODULO. Il nucleo controlla già l'accesso al settore: nelle route basta usare puo('settore','scrittura')
per i permessi di modifica. L'app sarà raggiungibile su /<codice>/ e comparirà nel menu «App»."""
from flask import Blueprint, render_template
MODULO = dict(codice='esempio', nome='Modulo di esempio', descrizione='Traccia per integrare altre app (Lance, Personale, Vigilanza…)',
              settore='demo', settore_nome='Demo', icona='🧩')
bp = Blueprint('esempio', __name__, template_folder='templates')
@bp.route('/')
def index(): return render_template('esempio/index.html')
