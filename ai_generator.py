__version__ = "1.2"
# ai_generator.py - Generatore relazioni con Groq AI
# CODICE PURO - Legge tutte le personalizzazioni da config.py

from groq import Groq
import re

from config import (
    AI_MODEL, 
    AI_SYSTEM_MESSAGE,
    RELAZIONE_TEMPLATE, 
    NOMI_FEMMINILI,
    CORREZIONI_FARMACI,
    PATTERN_FIRMA_DOTTORE
)


class AIGenerator:
    
    # Tabella descrizioni denti (notazione FDI)
    DESCRIZIONI_DENTI = {
        # Superiore destro (1.x)
        '1.1': 'incisivo centrale superiore di destra',
        '1.2': 'incisivo laterale superiore di destra',
        '1.3': 'canino superiore di destra',
        '1.4': 'primo premolare superiore di destra',
        '1.5': 'secondo premolare superiore di destra',
        '1.6': 'primo molare superiore di destra',
        '1.7': 'secondo molare superiore di destra',
        '1.8': 'dente del giudizio superiore di destra',
        # Superiore sinistro (2.x)
        '2.1': 'incisivo centrale superiore di sinistra',
        '2.2': 'incisivo laterale superiore di sinistra',
        '2.3': 'canino superiore di sinistra',
        '2.4': 'primo premolare superiore di sinistra',
        '2.5': 'secondo premolare superiore di sinistra',
        '2.6': 'primo molare superiore di sinistra',
        '2.7': 'secondo molare superiore di sinistra',
        '2.8': 'dente del giudizio superiore di sinistra',
        # Inferiore sinistro (3.x)
        '3.1': 'incisivo centrale inferiore di sinistra',
        '3.2': 'incisivo laterale inferiore di sinistra',
        '3.3': 'canino inferiore di sinistra',
        '3.4': 'primo premolare inferiore di sinistra',
        '3.5': 'secondo premolare inferiore di sinistra',
        '3.6': 'primo molare inferiore di sinistra',
        '3.7': 'secondo molare inferiore di sinistra',
        '3.8': 'dente del giudizio inferiore di sinistra',
        # Inferiore destro (4.x)
        '4.1': 'incisivo centrale inferiore di destra',
        '4.2': 'incisivo laterale inferiore di destra',
        '4.3': 'canino inferiore di destra',
        '4.4': 'primo premolare inferiore di destra',
        '4.5': 'secondo premolare inferiore di destra',
        '4.6': 'primo molare inferiore di destra',
        '4.7': 'secondo molare inferiore di destra',
        '4.8': 'dente del giudizio inferiore di destra',
    }
    
    # Stessa tabella ma senza punto (notazione alternativa: 15, 27, 36, 48...)
    DESCRIZIONI_DENTI_NOPUNTO = {}
    for k, v in DESCRIZIONI_DENTI.items():
        DESCRIZIONI_DENTI_NOPUNTO[k.replace('.', '')] = v
    
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.model = AI_MODEL
    
    def genera_relazione(self, trascrizione, info_paziente=None, info_medico=None):
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
        
        # 3. Formatta il Prompt
        full_prompt = RELAZIONE_TEMPLATE.format(
            dati_paziente=str_dati_paziente,
            trascrizione=trascrizione
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": AI_SYSTEM_MESSAGE
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
    
    def _aggiungi_descrizione_denti(self, testo):
        """
        Post-processing: aggiunge la descrizione tra parentesi alla PRIMA 
        menzione di ogni dente, se Groq non l'ha fatto.
        
        Gestisce sia notazione con punto (1.7) che senza (17).
        NON tocca i denti che hanno già la parentesi dopo.
        NON tocca i denti dentro elenchi multipli tipo "(14, 21 e 37)".
        """
        denti_gia_descritti = set()
        
        def _sostituisci_match(match):
            """Callback per re.sub - aggiunge descrizione se è la prima menzione."""
            prefisso = match.group(1)        # "elemento " o "dente " o "dell'elemento "
            numero = match.group(2)           # "1.7" o "17"
            dopo = match.group(3)             # carattere dopo il numero
            
            # Normalizza il numero (con o senza punto)
            numero_norm = numero.replace('.', '')
            
            # Se dopo c'è una parentesi aperta, Groq ha già messo la descrizione
            if dopo and dopo.strip().startswith('('):
                denti_gia_descritti.add(numero_norm)
                return match.group(0)
            
            # Se questo dente è già stato descritto prima, non aggiungere
            if numero_norm in denti_gia_descritti:
                return match.group(0)
            
            # Cerca la descrizione nella tabella
            descrizione = None
            if numero in self.DESCRIZIONI_DENTI:
                descrizione = self.DESCRIZIONI_DENTI[numero]
            elif numero_norm in self.DESCRIZIONI_DENTI_NOPUNTO:
                descrizione = self.DESCRIZIONI_DENTI_NOPUNTO[numero_norm]
            
            if descrizione:
                denti_gia_descritti.add(numero_norm)
                return f"{prefisso}{numero} ({descrizione}){dopo}"
            else:
                # Numero non riconosciuto, lascia com'è
                return match.group(0)
        
        # Pattern: cattura "elemento/dente X.Y" seguito da qualsiasi cosa
        # Gruppo 1: prefisso (elemento, dente, dell'elemento, ecc.)
        # Gruppo 2: numero dente (1.7 o 17 o 48)
        # Gruppo 3: carattere dopo il numero
        pattern = (
            r"((?:dell(?:'|'))?(?:elemento|dente)\s+)"   # prefisso
            r"(\d\.\d|\d{2})"                             # numero dente
            r"(\s*(?:\(|[,;.\s]))"                        # dopo
        )
        
        testo = re.sub(pattern, _sostituisci_match, testo, flags=re.IGNORECASE)
        
        return testo
    
    def _pulisci_relazione(self, testo):
        """Correttore automatico post-generazione."""
        
        # 0. RIMUOVI MARKDOWN (l'AI a volte genera formattazione Markdown)
        testo = re.sub(r'#{1,6}\s*', '', testo)           # Rimuove ### titoli
        testo = re.sub(r'\*\*([^*]+)\*\*', r'\1', testo)  # Rimuove **grassetto**
        testo = re.sub(r'\*([^*]+)\*', r'\1', testo)      # Rimuove *corsivo*
        testo = re.sub(r'__([^_]+)__', r'\1', testo)      # Rimuove __sottolineato__
        testo = re.sub(r'`([^`]+)`', r'\1', testo)        # Rimuove `codice`
        
        # 0.5 AGGIUNGI DESCRIZIONE DENTI (se Groq non l'ha fatto)
        testo = self._aggiungi_descrizione_denti(testo)
        
        # 1. CORREZIONI MEDICHE E ORTOGRAFICHE
        testo = re.sub(r'\bmucose(\s+\w+)?\s+rose\b', r'mucose\1 rosee', testo, flags=re.IGNORECASE)
        testo = re.sub(r'\bclori[xcs]idina\b', 'Clorexidina', testo, flags=re.IGNORECASE)
        testo = re.sub(r'\bcardio\w*pirina\b', 'Cardioaspirina', testo, flags=re.IGNORECASE)
        testo = re.sub(r'\blipobrufene\b', 'Ibuprofene', testo, flags=re.IGNORECASE)
        
        # 1.5 FIX GRAMMATICALI COMUNI
        # "un'" davanti a parole maschili → "un "
        testo = re.sub(
            r"\bun'(?=intervento|appuntamento|esame|elemento|impianto|antibiotico|antidolorifico|ulteriore)",
            "un ",
            testo,
            flags=re.IGNORECASE
        )
        # "su i" → "sui", "su il" → "sul", "su gli" → "sugli", "su le" → "sulle", "su la" → "sulla"
        testo = re.sub(r'\bsu i\b', 'sui', testo)
        testo = re.sub(r'\bsu il\b', 'sul', testo)
        testo = re.sub(r'\bsu gli\b', 'sugli', testo)
        testo = re.sub(r'\bsu le\b', 'sulle', testo)
        testo = re.sub(r'\bsu la\b', 'sulla', testo)
        testo = re.sub(r'\bsu lo\b', 'sullo', testo)
        # "E'" a inizio frase → "È"
        testo = re.sub(r"\bE'", "È", testo)
        
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
        
        # 3. FIX MAIUSCOLE FARMACI (da config.py)
        for farmaco in CORREZIONI_FARMACI:
            testo = re.sub(r'\b' + farmaco.upper() + r'\b', farmaco, testo)
            testo = re.sub(r'\b' + farmaco.lower() + r'\b', farmaco, testo)
        
        # 4. PULIZIA FORMATTAZIONE
        testo = re.sub(r'_{3,}.*$', '', testo, flags=re.MULTILINE | re.DOTALL)
        
        # Rimuove firma duplicata (pattern da config.py)
        if PATTERN_FIRMA_DOTTORE:
            testo = re.sub(
                r'\n\s*dott\.?ssa\s+' + PATTERN_FIRMA_DOTTORE + r'.*$', 
                '', 
                testo, 
                flags=re.MULTILINE | re.IGNORECASE | re.DOTALL
            )
        
        testo = re.sub(r'\n\s*Medico Chirurgo.*$', '', testo, flags=re.MULTILINE | re.DOTALL)
        testo = re.sub(r'^OGGETTO:.*?\n', '', testo, flags=re.IGNORECASE | re.MULTILINE)
        testo = re.sub(r'^PAZIENTE:.*?\n', '', testo, flags=re.IGNORECASE | re.MULTILINE)
        testo = re.sub(r'[Ss]ar[aà]\s+inviat.*?[Mm]ail.*?[.\n]', '', testo)
        testo = re.sub(r'\n{3,}', '\n\n', testo)
        
        return testo.strip()