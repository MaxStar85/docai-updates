__version__ = "1.3"
# transcriber.py - DEEPGRAM REAL-TIME
# CODICE UNIVERSALE - Parametri tecnici qui dentro (aggiornabili da GitHub)

import threading
import queue
from datetime import datetime
import numpy as np
import json
import websocket
import ssl

# =============================================================================
# PARAMETRI TECNICI (aggiornabili da GitHub - MAI in config.py)
# =============================================================================
SAMPLE_RATE = 16000
CHANNELS = 1

DEEPGRAM_CONFIG = {
    "model": "nova-2",
    "language": "it",
    "punctuate": True,
    "smart_format": True,
    "interim_results": False,
    "endpointing": 400,
}


class Transcriber:
    def __init__(self, api_key):
        print("")
        print("=" * 55)
        print("   DEEPGRAM REAL-TIME TRANSCRIPTION")
        print("=" * 55)
        print(f"   Modello: {DEEPGRAM_CONFIG.get('model', 'nova-2')}")
        print(f"   Lingua: {DEEPGRAM_CONFIG.get('language', 'it')}")
        print("   Latenza: < 300ms")
        print("=" * 55)
        print("")
        
        self.api_key = api_key
        self.sample_rate = SAMPLE_RATE
        self.config = DEEPGRAM_CONFIG
        self.full_transcription = []
        self.is_running = False
        self.ws = None
        self.callback = None
        self.audio_queue = queue.Queue()
        
    def _get_deepgram_url(self):
        """Costruisce URL Deepgram leggendo parametri da config.py."""
        params = [
            f"model={self.config.get('model', 'nova-2')}",
            f"language={self.config.get('language', 'it')}",
            f"punctuate={'true' if self.config.get('punctuate', True) else 'false'}",
            f"smart_format={'true' if self.config.get('smart_format', True) else 'false'}",
            f"interim_results={'true' if self.config.get('interim_results', False) else 'false'}",
            f"endpointing={self.config.get('endpointing', 400)}",
            f"sample_rate={self.sample_rate}",
            "encoding=linear16",
            "channels=1"
        ]
        return f"wss://api.deepgram.com/v1/listen?{'&'.join(params)}"
        
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            if data.get("type") == "Results":
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])
                
                if alternatives:
                    transcript = alternatives[0].get("transcript", "").strip()
                    is_final = data.get("is_final", False)
                    
                    if transcript and is_final:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        entry = f"[{timestamp}] {transcript}"
                        self.full_transcription.append(transcript)
                        
                        if self.callback:
                            self.callback(entry)
                            
        except Exception as e:
            print(f"Errore messaggio: {e}")
            
    def _on_error(self, ws, error):
        print(f"Errore WebSocket: {error}")
        
    def _on_close(self, ws, close_status, close_msg):
        print("Connessione Deepgram chiusa")
        
    def _on_open(self, ws):
        print("Connesso a Deepgram!")
        
        def send_audio():
            while self.is_running:
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    if audio_chunk is not None and len(audio_chunk) > 0:
                        if isinstance(audio_chunk, np.ndarray):
                            if audio_chunk.dtype == np.float32:
                                audio_int16 = (audio_chunk * 32767).astype(np.int16)
                            else:
                                audio_int16 = audio_chunk.astype(np.int16)
                            audio_bytes = audio_int16.tobytes()
                        else:
                            audio_bytes = audio_chunk
                        ws.send(audio_bytes, opcode=websocket.ABNF.OPCODE_BINARY)
                except queue.Empty:
                    continue
                except Exception as e:
                    if self.is_running:
                        print(f"Errore invio: {e}")
                    break
                    
        self.send_thread = threading.Thread(target=send_audio, daemon=True)
        self.send_thread.start()
        
    def start_realtime_transcription(self, audio_recorder, callback=None):
        self.is_running = True
        self.full_transcription = []
        self.callback = callback
        
        def audio_reader():
            while self.is_running:
                chunk = audio_recorder.get_audio_chunk(timeout=0.5)
                if chunk is not None:
                    self.audio_queue.put(chunk)
                    
        self.reader_thread = threading.Thread(target=audio_reader, daemon=True)
        self.reader_thread.start()
        
        def run_websocket():
            self.ws = websocket.WebSocketApp(
                self._get_deepgram_url(),
                header={"Authorization": f"Token {self.api_key}"},
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            
        self.ws_thread = threading.Thread(target=run_websocket, daemon=True)
        self.ws_thread.start()
        
    def stop_transcription(self):
        self.is_running = False
        if self.ws:
            try:
                self.ws.send(json.dumps({"type": "CloseStream"}))
                self.ws.close()
            except:
                pass
                
    def get_full_transcription(self):

        return "\n".join(self.full_transcription)
