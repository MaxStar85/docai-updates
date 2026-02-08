__version__ = "1.0"
# ai_module.py - Modulo AI centralizzato (Gemini + Groq)
# Questo file è UGUALE PER TUTTI i clienti e può essere aggiornato da remoto

import re

# ============================================================================
# CONFIGURAZIONE LIBRERIE DISPONIBILI
# ============================================================================

# --- GEMINI (Google) ---
HAS_GEMINI = False
GEMINI_VERSION = None  # "new" o "old"

# Prova prima la nuova libreria (google-genai)
try:
    from google import genai
    HAS_GEMINI = True
    GEMINI_VERSION = "new"
except ImportError:
    # Fallback alla vecchia libreria (google-generativeai)
    try:
        import google.generativeai as genai_old
        HAS_GEMINI = True
        GEMINI_VERSION = "old"
    except ImportError:
        pass

# --- GROQ ---
HAS_GROQ = False
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    pass

# --- DEEPGRAM (solo check, resta in transcriber.py) ---
HAS_DEEPGRAM = False
try:
    from deepgram import Deepgram
    HAS_DEEPGRAM = True
except ImportError:
    try:
        from deepgram import DeepgramClient
        HAS_DEEPGRAM = True
    except ImportError:
        pass


# ============================================================================
# CLASSE GEMINI OCR (Lettura Foto)
# ============================================================================

class GeminiOCR:
    """Legge testo da immagini usando Google Gemini (supporta entrambe le librerie)."""
    
    # Modelli in ordine di priorità
    MODELS_PRIORITY = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-pro-vision",
    ]
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.model_name = None
        
        if not HAS_GEMINI:
            raise ImportError("Nessuna libreria Gemini installata. Installa: pip install google-generativeai")
        
        # Configura in base alla versione
        if GEMINI_VERSION == "new":
            self.client = genai.Client(api_key=api_key)
        else:
            genai_old.configure(api_key=api_key)
            self.client = None
    
    def read_image(self, image_path, prompt=None):
        """
        Legge il testo da un'immagine.
        
        Args:
            image_path: Percorso dell'immagine
            prompt: Prompt personalizzato (opzionale)
        
        Returns:
            str: Testo estratto dall'immagine
        """
        from PIL import Image
        img = Image.open(image_path)
        
        if prompt is None:
            prompt = self._get_default_prompt()
        
        if GEMINI_VERSION == "new":
            return self._read_with_new_api(img, prompt)
        else:
            return self._read_with_old_api(img, prompt)
    
    def _get_default_prompt(self):
        """Prompt ottimizzato per appunti medici manoscritti."""
        return """
Trascrivi questo appunto manoscritto correggendo la formattazione.

REGOLE RIGIDE:
1. EMAIL: Se l'indirizzo email è spezzato su due righe, UNISCILO in una riga sola senza spazi.
2. NUMERI: Fai estrema attenzione ai numeri manoscritti. Il '6' spesso sembra un '8' o viceversa.
3. ORARI: Scrivi gli orari (es. 8:30 - 12:30) sulla stessa riga.
4. Restituisci solo il testo pulito, senza commenti.
"""
    
    def _read_with_new_api(self, img, prompt):
        """Usa la nuova API google-genai."""
        last_error = None
        
        for model_name in self.MODELS_PRIORITY:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[prompt, img]
                )
                self.model_name = model_name
                return response.text
            except Exception as e:
                last_error = e
                continue
        
        raise Exception(f"Nessun modello Gemini disponibile. Ultimo errore: {last_error}")
    
    def _read_with_old_api(self, img, prompt):
        """Usa la vecchia API google-generativeai."""
        last_error = None
        
        # Cerca modelli disponibili
        available_models = []
        try:
            for m in genai_old.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name.replace("models/", ""))
        except:
            available_models = self.MODELS_PRIORITY
        
        # Prova in ordine di priorità
        models_to_try = []
        for model in self.MODELS_PRIORITY:
            if model in available_models or not available_models:
                models_to_try.append(model)
        
        # Aggiungi anche i modelli disponibili non in lista
        for model in available_models:
            if model not in models_to_try and 'flash' in model.lower():
                models_to_try.insert(0, model)
        
        for model_name in models_to_try:
            try:
                model = genai_old.GenerativeModel(model_name)
                response = model.generate_content([prompt, img])
                self.model_name = model_name
                return response.text
            except Exception as e:
                last_error = e
                continue
        
        raise Exception(f"Nessun modello Gemini disponibile. Ultimo errore: {last_error}")


# ============================================================================
# CLASSE GROQ GENERATOR (Generazione Testi AI)
# ============================================================================

class GroqGenerator:
    """Genera testi usando Groq AI con auto-discovery dei modelli."""
    
    # Modelli in ordine di priorità
    MODELS_PRIORITY = [
        "llama-3.3-70b-versatile",
        "llama-3.2-90b-text-preview",
        "llama-3.1-70b-versatile",
        "llama3-70b-8192",
        "mixtral-8x7b-32768",
    ]
    
    def __init__(self, api_key, preferred_model=None):
        if not HAS_GROQ:
            raise ImportError("Libreria Groq non installata. Installa: pip install groq")
        
        self.client = Groq(api_key=api_key)
        self.model = preferred_model or self._find_best_model()
    
    def _find_best_model(self):
        """Trova il miglior modello disponibile."""
        try:
            available = []
            for model in self.client.models.list().data:
                available.append(model.id)
            
            # Cerca in ordine di priorità
            for preferred in self.MODELS_PRIORITY:
                if preferred in available:
                    return preferred
            
            # Se nessuno trovato, usa il primo della lista
            return self.MODELS_PRIORITY[0]
        except:
            return self.MODELS_PRIORITY[0]
    
    def generate(self, prompt, system_prompt=None, max_tokens=4000, temperature=0.3):
        """
        Genera testo con Groq.
        
        Args:
            prompt: Il prompt utente
            system_prompt: Il prompt di sistema (opzionale)
            max_tokens: Numero massimo di token
            temperature: Creatività (0.0 - 1.0)
        
        Returns:
            str: Testo generato
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            # Prova con un altro modello
            old_model = self.model
            self.model = self._find_alternative_model(old_model)
            
            if self.model != old_model:
                return self.generate(prompt, system_prompt, max_tokens, temperature)
            
            raise e
    
    def _find_alternative_model(self, exclude_model):
        """Trova un modello alternativo."""
        for model in self.MODELS_PRIORITY:
            if model != exclude_model:
                try:
                    # Test veloce
                    self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5
                    )
                    return model
                except:
                    continue
        return exclude_model
    
    def genera_relazione(self, trascrizione, info_paziente=None, info_medico=None, 
                         template=None, system_prompt=None):
        """
        Genera una relazione clinica (wrapper per compatibilità con ai_generator.py).
        """
        # Determina Sig. o Sig.ra
        titolo_paziente = "Sig."
        nome_completo = "Paziente"
        
        if info_paziente and info_paziente.get('nome'):
            nome_completo = info_paziente['nome']
            nome_first = nome_completo.split()[0].lower()
            nomi_f = ['giorgia', 'maria', 'anna', 'giulia', 'sara', 'laura', 'francesca', 
                      'elena', 'chiara', 'valentina', 'alessia', 'martina', 'sofia', 'emma', 
                      'federica', 'silvia', 'paola', 'roberta', 'monica', 'simona', 'barbara', 
                      'cristina', 'daniela', 'elisa', 'alessandra', 'beatrice', 'camilla', 
                      'gina', 'igea', 'lella', 'rosa', 'giovanna', 'angela', 'lucia', 'emily',
                      'nella', 'emanuela', 'uma', 'linda', 'alice', 'aurora', 'gaia', 'grazia']
            if nome_first.endswith('a') or nome_first in nomi_f:
                titolo_paziente = "Sig.ra"
        
        # Prepara stringa dati paziente
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
        
        # Usa template passato o generico
        if template:
            full_prompt = template.format(
                dati_paziente=str_dati_paziente,
                trascrizione=trascrizione
            )
        else:
            full_prompt = f"Dati paziente:\n{str_dati_paziente}\n\nTrascrizione:\n{trascrizione}"
        
        # Default system prompt
        if not system_prompt:
            system_prompt = "Sei un medico. Scrivi relazioni cliniche dettagliate, empatiche e tecnicamente precise."
        
        try:
            relazione = self.generate(full_prompt, system_prompt)
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
            'Al paziente è stato prescritto', testo, flags=re.IGNORECASE
        )
        testo = re.sub(
            r'(?:riferisce|riferito|dice|afferma)\s+di\s+essere\s+stato\s+prescritto', 
            'riferisce di assumere', testo, flags=re.IGNORECASE
        )
        
        # 3. FIX MAIUSCOLE FARMACI
        farmaci = ["RAMIPRIL", "IBUPROFENE", "PENICILLINA", "AMOXICILLINA", "AUGMENTIN", "OKI", "AULIN"]
        for f in farmaci:
            testo = re.sub(r'\b' + f + r'\b', f.capitalize(), testo)
        
        # 4. PULIZIA FORMATTAZIONE
        testo = re.sub(r'_{3,}.*$', '', testo, flags=re.MULTILINE | re.DOTALL)
        testo = re.sub(r'\n\s*dott\.?ssa\s+Francesca\s+Manfrini.*$', '', testo, 
                       flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
        testo = re.sub(r'\n\s*Medico Chirurgo.*$', '', testo, flags=re.MULTILINE | re.DOTALL)
        testo = re.sub(r'^OGGETTO:.*?\n', '', testo, flags=re.IGNORECASE | re.MULTILINE)
        testo = re.sub(r'^PAZIENTE:.*?\n', '', testo, flags=re.IGNORECASE | re.MULTILINE)
        testo = re.sub(r'[Ss]ar[aà]\s+inviat.*?[Mm]ail.*?[.\n]', '', testo)
        testo = re.sub(r'\n{3,}', '\n\n', testo)
        
        return testo.strip()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ai_status():
    """Ritorna lo stato di tutte le integrazioni AI."""
    return {
        "gemini": {
            "available": HAS_GEMINI,
            "version": GEMINI_VERSION,
            "library": "google-genai" if GEMINI_VERSION == "new" else "google-generativeai" if GEMINI_VERSION == "old" else None
        },
        "groq": {
            "available": HAS_GROQ,
        },
        "deepgram": {
            "available": HAS_DEEPGRAM,
        }
    }


def check_all_ai_available():
    """Verifica se tutte le AI sono disponibili."""
    return HAS_GEMINI and HAS_GROQ and HAS_DEEPGRAM