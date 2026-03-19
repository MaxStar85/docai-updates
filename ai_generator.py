__version__ = "2.2"
# ai_generator.py - Generatore relazioni con Groq AI
# CODICE UNIVERSALE - Legge template dalla cartella templates/
# NON contiene nessun riferimento a specialità mediche specifiche
# Modelli AI qui dentro (aggiornabili da GitHub)

from groq import Groq
import re
import os
import importlib
from datetime import datetime

from config import NOMI_FEMMINILI

# =============================================================================
# MODELLI AI (aggiornabili da GitHub - MAI in config.py)
# =============================================================================
AI_MODEL = "llama-3.3-70b-versatile"


class AIGenerator:

    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.model = AI_MODEL
        self.template = None

    def carica_template(self, nome_template):
        """Carica un template dalla cartella templates/."""
        try:
            modulo = importlib.import_module(f"templates.{nome_template}")
            self.template = modulo
            return True
        except ImportError as e:
            print(f"Errore caricamento template '{nome_template}': {e}")
            return False

    def get_templates_disponibili(self):
        """Restituisce la lista dei template disponibili."""
        templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
        templates = []
        if os.path.exists(templates_dir):
            for f in os.listdir(templates_dir):
                if f.endswith('.py') and not f.startswith('_') and f != '__init__.py':
                    nome = f.replace('.py', '')
                    try:
                        modulo = importlib.import_module(f"templates.{nome}")
                        nome_display = getattr(modulo, 'NOME', nome)
                        templates.append({'file': nome, 'nome': nome_display})
                    except:
                        templates.append({'file': nome, 'nome': nome})
        return templates

    def genera_relazione(self, trascrizione, info_paziente=None, info_medico=None):
        """Genera la relazione usando il template caricato."""
        if not self.template:
            return "ERRORE: Nessun template caricato. Seleziona un tipo di documento."

        # Protegge temporaneamente le date con logica universale
        trascrizione_protetta, mappa_date = self._proteggi_date(trascrizione)

        # Protezioni specialistiche opzionali delegate al template
        mappa_specialistica = {}
        if self.template and hasattr(self.template, 'proteggi_notazioni_specialistiche'):
            trascrizione_protetta, mappa_specialistica = self.template.proteggi_notazioni_specialistiche(trascrizione_protetta)

        # 1. Determina Sig. o Sig.ra (vuoto se minorenne, altrimenti da form)
        titolo_paziente = "Sig."
        nome_completo = "Paziente"
        is_minorenne = False

        if info_paziente:
            is_minorenne = info_paziente.get('is_minorenne', False)

            if info_paziente.get('nome'):
                nome_completo = info_paziente['nome']

                if is_minorenne:
                    # Minorenne: nessun titolo
                    titolo_paziente = ""
                else:
                    # Adulto: usa titolo dal form (scelto manualmente)
                    titolo_paziente = info_paziente.get('titolo', 'Sig.')

        # 2. Prepara stringa Dati Paziente
        str_dati_paziente = ""

        if info_paziente:
            destinatari_extra = ""
            if info_paziente.get('destinatari'):
                destinatari_extra = "\nATTENZIONE: Indirizza la lettera a: " + ", ".join(
                    [f"{d['ruolo']} {d['nome']}" for d in info_paziente['destinatari']]
                )

            # Istruzione specifica per minorenne
            istruzione_minorenne = ""
            if is_minorenne:
                istruzione_minorenne = "\nATTENZIONE: Il paziente e' MINORENNE. NON usare Sig. o Sig.ra, scrivi solo il nome."

            # Costruisci istruzione titolo/genere esplicita
            if is_minorenne:
                genere_paziente = info_paziente.get('titolo', 'Sig.')
                if genere_paziente == "Sig.ra":
                    istruzione_titolo = f"\nATTENZIONE: Il paziente e' MINORENNE e FEMMINA. NON usare 'Sig.' o 'Sig.ra', scrivi solo '{nome_completo}'. Usa il FEMMINILE in tutto il testo."
                else:
                    istruzione_titolo = f"\nATTENZIONE: Il paziente e' MINORENNE e MASCHIO. NON usare 'Sig.' o 'Sig.ra', scrivi solo '{nome_completo}'. Usa il MASCHILE in tutto il testo."
            elif titolo_paziente:
                istruzione_titolo = f"\nATTENZIONE: Usa ESATTAMENTE '{titolo_paziente}' come titolo. Se il titolo e' 'Sig.ra', scrivi 'la Sig.ra {nome_completo}' e usa il FEMMINILE in tutto il testo. Se il titolo e' 'Sig.', scrivi 'il Sig. {nome_completo}' e usa il MASCHILE in tutto il testo."
            else:
                istruzione_titolo = ""

            str_dati_paziente = f"""
Nome: {nome_completo}
Titolo: {titolo_paziente if not is_minorenne else "(minorenne - nessun titolo)"}
Genere: {"Femminile" if info_paziente.get('titolo', 'Sig.') == "Sig.ra" else "Maschile"}
{istruzione_titolo}
{istruzione_minorenne}
{destinatari_extra}
"""

        # 3. Formatta il Prompt dal template
        ai_system_message = getattr(self.template, 'AI_SYSTEM_MESSAGE', '')
        relazione_template = getattr(self.template, 'RELAZIONE_TEMPLATE', '')

        full_prompt = relazione_template.format(
            dati_paziente=str_dati_paziente,
            trascrizione=trascrizione_protetta
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": ai_system_message
                    },
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=4000
            )

            relazione = response.choices[0].message.content

            # Ripristina prima le notazioni specialistiche, poi le date
            if self.template and hasattr(self.template, 'ripristina_notazioni_specialistiche'):
                relazione = self.template.ripristina_notazioni_specialistiche(relazione, mappa_specialistica)

            relazione = self._ripristina_date(relazione, mappa_date)

            # Applica pulizia post-generazione
            relazione = self._pulisci_relazione(relazione)

            return relazione

        except Exception as e:
            return f"ERRORE AI: {e}\n\nTrascrizione originale salvata:\n{trascrizione}"

    def _pulisci_relazione(self, testo):
        """Correttore automatico post-generazione. Solo pulizie UNIVERSALI."""

        # 0. RIMUOVI MARKDOWN
        testo = re.sub(r'#{1,6}\s*', '', testo)
        testo = re.sub(r'\*\*([^*]+)\*\*', r'\1', testo)
        testo = re.sub(r'\*([^*]+)\*', r'\1', testo)
        testo = re.sub(r'__([^_]+)__', r'\1', testo)
        testo = re.sub(r'`([^`]+)`', r'\1', testo)

        # 0.5 POST-PROCESSING DAL TEMPLATE (se esiste)
        # Qui vengono chiamati i fix specifici (es: dentista)
        if self.template and hasattr(self.template, 'post_processing'):
            testo = self.template.post_processing(testo)

        # 1.5 FIX GRAMMATICALI COMUNI (UNIVERSALI - lingua italiana)
          
        # Fix articoli indeterminativi
        testo = re.sub(
            r"\bun'(?=intervento|appuntamento|esame|elemento|impianto|ulteriore|evento)",
            "un ",
            testo,
            flags=re.IGNORECASE
        )
        testo = re.sub(
            r"\bun (?=terapia|corona|protesi|carie|lesione|ricostruzione|estrazione|rivalutazione|levigatura|seduta|visita|allergia|reazione|infezione|infiammazione)",
            "una ",
            testo,
            flags=re.IGNORECASE
        )
        # Fix articoli determinativi
        testo = re.sub(
            r"\bil (terapia|corona|protesi|carie|lesione|estrazione|rivalutazione|seduta|visita|allergia|infezione)\b",
            r"la \1",
            testo,
            flags=re.IGNORECASE
        )

        # Fix preposizioni articolate separate
        testo = re.sub(r'\bsu i\b', 'sui', testo)
        testo = re.sub(r'\bsu il\b', 'sul', testo)
        testo = re.sub(r'\bsu gli\b', 'sugli', testo)
        testo = re.sub(r'\bsu le\b', 'sulle', testo)
        testo = re.sub(r'\bsu la\b', 'sulla', testo)
        testo = re.sub(r'\bsu lo\b', 'sullo', testo)

        # 1.6 FIX APOSTROFI USATI COME ACCENTI (E' -> È)
        testo = re.sub(r"\bE'", "È", testo)
        testo = re.sub(r"e'(\s|[,;.\)]|$)", r"è\1", testo)
        testo = re.sub(r"a'(\s|[,;.\)]|$)", r"à\1", testo)
        testo = re.sub(r"i'(\s|[,;.\)]|$)", r"ì\1", testo)
        testo = re.sub(r"o'(\s|[,;.\)]|$)", r"ò\1", testo)
        testo = re.sub(r"u'(\s|[,;.\)]|$)", r"ù\1", testo)

        # 1.7 FIX "UN PO'" (DOPO gli accenti, così ripara il danno di o'->ò)
        testo = re.sub(r"\bun\s+p[oòó]+[''`]?\s", "un po' ", testo, flags=re.IGNORECASE)
        testo = re.sub(r"\bun\s+p[oòó]+[''`]?([,;.\)])", r"un po'\1", testo, flags=re.IGNORECASE)
        testo = re.sub(r"\bun\s+p[oòó]+[''`]?$", "un po'", testo, flags=re.IGNORECASE)

        # 2. CORREZIONE GRAMMATICA "PRESCRITTO" (Passivo inglese -> Italiano)
        testo = re.sub(
            r'\b([Ii]l\s+paziente\s+(?:è|ha|era)\s+stato\s+prescritto)\b',
            'Al paziente è stato prescritto',
            testo,
            flags=re.IGNORECASE
        )
        testo = re.sub(
            r'(?:riferisce|riferito|dice|afferma)\s+di\s+essere\s+stato\s+prescritto',
            'riferisce di assumere',
            testo,
            flags=re.IGNORECASE
        )

        # 3. FIX MAIUSCOLE FARMACI (legge lista dal template)
        correzioni_farmaci = getattr(self.template, 'CORREZIONI_FARMACI', []) if self.template else []
        for farmaco in correzioni_farmaci:
            testo = re.sub(r'\b' + farmaco.upper() + r'\b', farmaco, testo)
            testo = re.sub(r'\b' + farmaco.lower() + r'\b', farmaco, testo)

        return testo.strip()

    def pulisci_appunti(self, testo_grezzo):
        """Step 1: Riscrive appunti grezzi in modo chiaro per la generazione relazione."""

        anno_corrente = datetime.now().strftime("%Y")

        # Prompt di pulizia: specifico del template se disponibile, altrimenti generico
        if self.template and hasattr(self.template, 'AI_CLEANUP_MESSAGE'):
            system_message = self.template.AI_CLEANUP_MESSAGE
        else:
            system_message = self._get_default_cleanup_prompt()

        # Inietta anno corrente nel prompt
        system_message = system_message.replace("{ANNO_CORRENTE}", anno_corrente)

        user_message = f"Ecco gli appunti da riscrivere:\n\n{testo_grezzo}"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=4000
        )

        testo_pulito = response.choices[0].message.content.strip()

        # Rimuovi eventuale Markdown
        testo_pulito = re.sub(r'^#{1,6}\s+', '', testo_pulito, flags=re.MULTILINE)
        testo_pulito = re.sub(r'\*\*([^*]+)\*\*', r'\1', testo_pulito)
        testo_pulito = re.sub(r'\*([^*]+)\*', r'\1', testo_pulito)
        testo_pulito = re.sub(r'`([^`]+)`', r'\1', testo_pulito)

        return testo_pulito

    def _get_default_cleanup_prompt(self):
        """Prompt generico di pulizia appunti (usato se il template non ne ha uno)."""
        return """Sei un assistente medico che riscrive appunti clinici.

IL TUO COMPITO: Riscrivere gli appunti in modo chiaro, strutturato e affidabile, SENZA PERDERE NESSUNA INFORMAZIONE.

REGOLE CRITICHE:

1. DATE:
- Le date con solo giorno/mese (es. 6/2, 18/2, dal 9/2 al 18/2) vanno completate con l'anno corrente {ANNO_CORRENTE}
- Esempio: 6/2 -> 06/02/{ANNO_CORRENTE}
- Le date NON sono mai numeri di denti
- Mantieni sempre le date nel formato gg/mm/aaaa

2. ABBREVIAZIONI:
- pz = paziente
- dx = destra
- sx = sinistra
- gg = giorni
- x 3 = 3 volte al giorno nel contesto farmaci
- x 1 = 1 volta al giorno nel contesto farmaci
- dr / dr.ssa = dottore / dottoressa
- RX = radiografie

3. NESSUNA INFORMAZIONE VA ELIMINATA:
- Ogni dato clinico, ogni numero, ogni farmaco e ogni indicazione deve essere preservata
- Non sintetizzare troppo
- Non eliminare dettagli apparentemente secondari

4. STRUTTURA OBBLIGATORIA:
Scrivi gli appunti in sezioni chiare e sempre nello stesso ordine:

NOTA SEGRETERIA:
INFORMAZIONI RIFERITE DAL/DALLA PAZIENTE:
FARMACI ASSUNTI:
STORIA CLINICA:
MOTIVO DELLA VISITA:
RISCONTRI CLINICI DEL MEDICO:
PIANO DI TRATTAMENTO PROPOSTO:
SPIEGAZIONI DATE AL/ALLA PAZIENTE:
APPUNTAMENTI PROGRAMMATI:

5. DETTAGLI DA MANTENERE ESPLICITAMENTE:
- farmaci
- dosaggi
- frequenza
- date complete
- numeri dei denti
- numeri esatti di radiografie
- foto iniziali
- impronte digitali
- esami consigliati
- esami ritenuti inutili
- notazioni cliniche e protesiche

6. NON INVENTARE:
- Non aggiungere informazioni non presenti
- Non trasformare ipotesi in fatti certi
- Non cambiare il significato clinico

7. NO MARKDOWN:
- Non usare ###, **, * o altri simboli di formattazione

Scrivi gli appunti in modo chiaro, completo e strutturato."""

    def _proteggi_date(self, testo):
        """Sostituisce temporaneamente le date con token molto rigidi per evitare che l'AI le trasformi in denti."""
        mappa_date = {}
        contatore = [0]

        def repl(match):
            data_originale = match.group(0)
            contatore[0] += 1
            token = f"§§DATA{contatore[0]}§§"
            mappa_date[token] = data_originale
            return token

        # Pattern date - ordine: prima i piu' lunghi, poi i corti
        patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',
            r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',
            r'\b\d{1,2}/\d{1,2}\b',
        ]

        for pattern in patterns:
            testo = re.sub(pattern, repl, testo)

        return testo, mappa_date

    def _ripristina_date(self, testo, mappa_date):
        """Ripristina le date originali dopo la generazione AI."""
        for token, data_originale in mappa_date.items():
            testo = testo.replace(token, data_originale)
        return testo

