__version__ = "1.2"
# ai_module.py - Modulo AI centralizzato
# Check librerie disponibili + Gemini OCR
# CODICE UNIVERSALE - Aggiornabile da GitHub

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

# --- DEEPGRAM ---
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
    
    # Modelli in ordine di priorità (aggiornabile da GitHub)
    MODELS_PRIORITY = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-flash-latest",
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
        """Legge il testo da un'immagine."""
        from PIL import Image
        img = Image.open(image_path)
        
        if prompt is None:
            prompt = self._get_default_prompt()
        
        if GEMINI_VERSION == "new":
            return self._read_with_new_api(img, prompt)
        else:
            return self._read_with_old_api(img, prompt)
    
    def _get_default_prompt(self):
        """Prompt ottimizzato per appunti manoscritti."""
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
        
        available_models = []
        try:
            for m in genai_old.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name.replace("models/", ""))
        except:
            available_models = self.MODELS_PRIORITY
        
        models_to_try = []
        for model in self.MODELS_PRIORITY:
            if model in available_models or not available_models:
                models_to_try.append(model)
        
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
