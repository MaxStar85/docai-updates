__version__ = "1.0"
# update_from_github.py - Sistema aggiornamento file da GitHub
# CODICE UNIVERSALE - Aggiornabile da GitHub
# Controlla versioni remote e scarica aggiornamenti

import os
import re
import json
import threading
from urllib import request, error

# =============================================================================
# CONFIGURAZIONE GITHUB
# =============================================================================
GITHUB_BASE_URL = "https://raw.githubusercontent.com/MaxStar85/docai-updates/main/"

FILE_AGGIORNABILI = {
    "ai_generator": "ai_generator.py",
    "ai_module": "ai_module.py",
    "transcriber": "transcriber.py",
    "update_from_github": "update_from_github.py",
}

# Cartella locale dove stanno i file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# FUNZIONI DI LETTURA VERSIONI
# =============================================================================

def get_remote_versions(timeout=10):
    """Scarica versions.txt da GitHub e ritorna dict delle versioni."""
    url = GITHUB_BASE_URL + "versions.txt"
    try:
        req = request.Request(url, headers={"User-Agent": "DOCai-Updater"})
        with request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode("utf-8")
        
        versions = {}
        for line in content.strip().split("\n"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                versions[key.strip()] = value.strip()
        
        return versions
    except Exception as e:
        print(f"Errore lettura versioni remote: {e}")
        return None


def get_local_version(filename):
    """Legge __version__ da un file locale."""
    filepath = os.path.join(BASE_DIR, filename)
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                match = re.match(r'^__version__\s*=\s*["\'](.+?)["\']', line.strip())
                if match:
                    return match.group(1)
    except Exception as e:
        print(f"Errore lettura versione locale {filename}: {e}")
    
    return None


def get_local_versions():
    """Legge le versioni di tutti i file aggiornabili."""
    versions = {}
    for key, filename in FILE_AGGIORNABILI.items():
        ver = get_local_version(filename)
        if ver:
            versions[key] = ver
    return versions


def parse_version(v):
    """Converte '1.2' in tupla (1, 2) per confronto."""
    try:
        parts = v.replace("-", ".").split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except:
        return (0,)


# =============================================================================
# CONTROLLO AGGIORNAMENTI
# =============================================================================

def check_updates():
    """
    Confronta versioni locali con remote.
    Ritorna dict:
    {
        "available": True/False,
        "updates": [
            {"nome": "ai_generator", "file": "ai_generator.py", 
             "locale": "2.0", "remota": "2.1"}
        ],
        "error": None o stringa errore
    }
    """
    result = {
        "available": False,
        "updates": [],
        "error": None
    }
    
    # Scarica versioni remote
    remote = get_remote_versions()
    if remote is None:
        result["error"] = "Impossibile connettersi a GitHub.\nVerifica la connessione internet."
        return result
    
    # Leggi versioni locali
    local = get_local_versions()
    
    # Confronta
    for key, filename in FILE_AGGIORNABILI.items():
        remote_ver = remote.get(key)
        local_ver = local.get(key)
        
        if remote_ver and local_ver:
            if parse_version(remote_ver) > parse_version(local_ver):
                result["updates"].append({
                    "nome": key,
                    "file": filename,
                    "locale": local_ver,
                    "remota": remote_ver
                })
        elif remote_ver and not local_ver:
            # File non esiste localmente
            result["updates"].append({
                "nome": key,
                "file": filename,
                "locale": "non installato",
                "remota": remote_ver
            })
    
    result["available"] = len(result["updates"]) > 0
    return result


# =============================================================================
# DOWNLOAD E INSTALLAZIONE
# =============================================================================

def download_file(filename, timeout=15):
    """
    Scarica un file da GitHub e sostituisce quello locale.
    Ritorna (successo, messaggio).
    """
    url = GITHUB_BASE_URL + filename
    local_path = os.path.join(BASE_DIR, filename)
    backup_path = local_path + ".backup"
    
    try:
        # Backup del file corrente
        if os.path.exists(local_path):
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(local_path, backup_path)
            except Exception as e:
                print(f"Warning: backup fallito per {filename}: {e}")
        
        # Scarica il nuovo file
        req = request.Request(url, headers={"User-Agent": "DOCai-Updater"})
        with request.urlopen(req, timeout=timeout) as response:
            content = response.read()
        
        # Salva il nuovo file
        with open(local_path, "wb") as f:
            f.write(content)
        
        # Verifica che il file sia valido (contiene __version__)
        new_ver = get_local_version(filename)
        if new_ver is None:
            # File scaricato non valido, ripristina backup
            if os.path.exists(backup_path):
                os.remove(local_path)
                os.rename(backup_path, local_path)
            return False, f"File {filename} scaricato non valido"
        
        # Rimuovi backup
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except:
                pass
        
        return True, f"{filename} aggiornato a v{new_ver}"
    
    except Exception as e:
        # Ripristina backup in caso di errore
        if os.path.exists(backup_path) and not os.path.exists(local_path):
            try:
                os.rename(backup_path, local_path)
            except:
                pass
        return False, f"Errore download {filename}: {e}"


def download_updates(updates_list, progress_callback=None):
    """
    Scarica tutti gli aggiornamenti nella lista.
    progress_callback(nome, indice, totale, successo, messaggio)
    Ritorna (successi, errori) come liste di stringhe.
    """
    successi = []
    errori = []
    totale = len(updates_list)
    
    for i, update in enumerate(updates_list):
        filename = update["file"]
        nome = update["nome"]
        
        if progress_callback:
            progress_callback(nome, i + 1, totale, None, f"Download {filename}...")
        
        success, msg = download_file(filename)
        
        if success:
            successi.append(msg)
        else:
            errori.append(msg)
        
        if progress_callback:
            progress_callback(nome, i + 1, totale, success, msg)
    
    return successi, errori


# =============================================================================
# FUNZIONI ASINCRONE (per non bloccare la GUI)
# =============================================================================

def check_updates_async(callback):
    """
    Controlla aggiornamenti in background.
    callback(result_dict) chiamato quando finisce.
    """
    def _worker():
        try:
            result = check_updates()
            callback(result)
        except Exception as e:
            callback({"available": False, "updates": [], "error": str(e)})
    
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def download_updates_async(updates_list, on_complete, on_progress=None):
    """
    Scarica aggiornamenti in background.
    on_complete(successi, errori) chiamato quando finisce.
    on_progress(nome, indice, totale, successo, msg) chiamato ad ogni file.
    """
    def _worker():
        successi, errori = download_updates(updates_list, progress_callback=on_progress)
        on_complete(successi, errori)
    
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


# =============================================================================
# TEST (se eseguito direttamente)
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  DOCai - Controllo Aggiornamenti")
    print("=" * 60 + "\n")
    
    print("  Versioni locali:")
    local = get_local_versions()
    for key, ver in local.items():
        print(f"    {key}: {ver}")
    
    print("\n  Controllo versioni remote...")
    result = check_updates()
    
    if result["error"]:
        print(f"\n  ❌ Errore: {result['error']}")
    elif result["available"]:
        print(f"\n  🔄 Aggiornamenti disponibili:")
        for u in result["updates"]:
            print(f"    • {u['nome']}: {u['locale']} → {u['remota']}")
    else:
        print("\n  ✅ Tutto aggiornato!")
    
    print("\n" + "=" * 60 + "\n")