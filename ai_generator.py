__version__ = "1.1"
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
    
    def _pulisci_relazione(self, testo):
        """Correttore automatico post-generazione."""
        
        # 1. CORREZIONI MEDICHE E ORTOGRAFICHE
        testo = re.sub(r'\bmucose(\s+\w+)?\s+rose\b', r'mucose\1 rosee', testo, flags=re.IGNORECASE)
        testo = re.sub(r'\bclori[xcs]idina\b', 'Clorexidina', testo, flags=re.IGNORECASE)
        testo = re.sub(r'\bcardio\w*pirina\b', 'Cardioaspirina', testo, flags=re.IGNORECASE)
        testo = re.sub(r'\blipobrufene\b', 'Ibuprofene', testo, flags=re.IGNORECASE)
        
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