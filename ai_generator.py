__version__ = "2.1"
# ai_generator.py - Generatore relazioni con Groq AI
# CODICE UNIVERSALE - Legge template dalla cartella templates/
# NON contiene nessun riferimento a specialità mediche specifiche
# Modelli AI qui dentro (aggiornabili da GitHub)

from groq import Groq
import re
import os
import importlib

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

        # 1. Determina Sig. o Sig.ra
        titolo_paziente = "Sig."
        nome_completo = "Paziente"

        if info_paziente and info_paziente.get('nome'):
            nome_completo = info_paziente['nome']
            nome_first = nome_completo.split()[0].lower()

            if nome_first.endswith('a') or nome_first in NOMI_FEMMINILI:
                titolo_paziente = "Sig.ra"

        # 2. Prepara stringa Dati Paziente
        str_dati_paziente = ""

        if info_paziente:
            destinatari_extra = ""
            if info_paziente.get('destinatari'):
                destinatari_extra = "\nATTENZIONE: Indirizza la lettera a: " + ", ".join(
                    [f"{d['ruolo']} {d['nome']}" for d in info_paziente['destinatari']]
                )

            str_dati_paziente = f"""
Nome: {nome_completo}
Titolo: {titolo_paziente}
{destinatari_extra}
"""

        # 3. Formatta il Prompt dal template
        ai_system_message = getattr(self.template, 'AI_SYSTEM_MESSAGE', '')
        relazione_template = getattr(self.template, 'RELAZIONE_TEMPLATE', '')

        full_prompt = relazione_template.format(
            dati_paziente=str_dati_paziente,
            trascrizione=trascrizione
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
        if self.template and hasattr(self.template, 'post_processing'):
            testo = self.template.post_processing(testo)

        # 1.5 FIX GRAMMATICALI COMUNI (UNIVERSALI - lingua italiana)
        testo = re.sub(
            r"\bun'(?=intervento|appuntamento|esame|elemento|impianto|antibiotico|antidolorifico|ulteriore)",
            "un ",
            testo,
            flags=re.IGNORECASE
        )
        testo = re.sub(
            r"\bun (?=terapia|corona|protesi|radiotrasparenza|fistola|carie|lesione|ricostruzione|estrazione|rivalutazione|levigatura|seduta|visita|allergia|reazione|infezione|infiammazione)",
            "una ",
            testo,
            flags=re.IGNORECASE
        )
        testo = re.sub(
            r"\bil (terapia|corona|protesi|carie|lesione|estrazione|rivalutazione|seduta|visita|allergia|infezione)\b",
            r"la \1",
            testo,
            flags=re.IGNORECASE
        )

        testo = re.sub(r'\bsu i\b', 'sui', testo)
        testo = re.sub(r'\bsu il\b', 'sul', testo)
        testo = re.sub(r'\bsu gli\b', 'sugli', testo)
        testo = re.sub(r'\bsu le\b', 'sulle', testo)
        testo = re.sub(r'\bsu la\b', 'sulla', testo)
        testo = re.sub(r'\bsu lo\b', 'sullo', testo)

        # 1.6 FIX APOSTROFI USATI COME ACCENTI
        testo = re.sub(r"\bE'", "È", testo)
        testo = re.sub(r"e'(\s|[,;.\)]|$)", r"è\1", testo)
        testo = re.sub(r"a'(\s|[,;.\)]|$)", r"à\1", testo)
        testo = re.sub(r"i'(\s|[,;.\)]|$)", r"ì\1", testo)
        testo = re.sub(r"o'(\s|[,;.\)]|$)", r"ò\1", testo)
        testo = re.sub(r"u'(\s|[,;.\)]|$)", r"ù\1", testo)

        # 2. CORREZIONE GRAMMATICA "PRESCRITTO"
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
