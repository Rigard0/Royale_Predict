# royale/cards/battlelog.py
from __future__ import annotations

import os
import json
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

API = "https://api.clashroyale.com/v1"

# ✅ Preferisci usare la variabile d'ambiente:
#    export CLASH_ROYALE_TOKEN="..."
TOKEN = os.getenv(
    "CLASH_ROYALE_TOKEN",
    # fallback (sconsigliato: rimuovi il token hardcoded appena possibile)
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImExYjczYzAwLTExZjEtNGJmYi05YmFmLTk1YjlkYzk1ODYxMCIsImlhdCI6MTc1ODU3MzM5Nywic3ViIjoiZGV2ZWxvcGVyLzAzYTU5YTVlLTUzNjktNDMyZS0zYWE5LTQ5NWZmYjJjN2Q5ZSIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyI4Mi41OC4xNTkuNzEiXSwidHlwZSI6ImNsaWVudCJ9XX0.UUCOGflcVpBEHomoSpV3uhO-_oeN47KMWPJSFPO4l-JUSnjYDpFA5fKhDkEYdUWqxgNtmLxyCYM4Ms6pkWQQgw",
)

# ---------------------- Percorsi dati di default ----------------------
# Default richiesto: /home/simonetto/royale/data/all
# Puoi override con ROYALE_DATA_DIR=/un/percorso/qualsiasi
_DEFAULT_DATA_ROOT = Path("/home/simonetto/royale/Royale_Predict/data").resolve()

def get_data_dir(player_tag: Optional[str] = None) -> Path:
    """
    Restituisce la cartella in cui salvare i battlelog.
    - Default root: /home/simonetto/royale/data
    - Sottocartelle: 'all' per tutti, 'mine' per #88V8GQU
    - Override con env ROYALE_DATA_DIR (punta alla root dati; le sottocartelle restano 'all' / 'mine')
    """
    root = Path(os.getenv("ROYALE_DATA_DIR", str(_DEFAULT_DATA_ROOT))).expanduser().resolve()
    if player_tag and player_tag.upper() == "#88V8GQU":
        d = root / "mine"
    else:
        d = root / "all"
    d.mkdir(parents=True, exist_ok=True)
    return d

# ---------------------- Utils tag/encoding ----------------------
def enc_tag(tag: str) -> str:
    """Normalizza e URL-encoda il player tag per l'endpoint API."""
    t = tag.strip().upper()
    if t.startswith("#"):
        t = t[1:]
    return "%23" + urllib.parse.quote(t, safe="")

def tag_clean(tag: str) -> str:
    """Restituisce il tag senza #, in uppercase (utile per confronti/log)."""
    t = tag.strip().upper()
    return t[1:] if t.startswith("#") else t

# ---------------------- API ----------------------
def get_battlelog(player_tag: str) -> List[Dict[str, Any]]:
    """Chiama l'API e ritorna il battlelog (lista di match)."""
    if not TOKEN:
        raise RuntimeError(
            "TOKEN mancante. Imposta CLASH_ROYALE_TOKEN oppure definisci TOKEN nel file."
        )
    url = f"{API}/players/{enc_tag(player_tag)}/battlelog"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            return data
        raise RuntimeError(f"Formato risposta inatteso: {type(data)}")
    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

# ---------------------- Dedup/ordinamento ----------------------
def _match_key(m: Dict[str, Any]) -> str:
    """Chiave univoca robusta per dedup (battleTime + type + tags ordinati)."""
    bt = m.get("battleTime", "") or ""
    tp = (m.get("type") or "").lower()
    players: List[str] = []
    for side in ("team", "opponent"):
        for p in (m.get(side) or []):
            tag = p.get("tag")
            if tag:
                players.append(str(tag).upper())
    players.sort()
    return f"{bt}|{tp}|{'-'.join(players)}"

def _parse_battletime(bt: str) -> datetime:
    """Parsa battleTime in datetime (fallback se non riconosciuto)."""
    for fmt in ("%Y%m%dT%H%M%S.%fZ", "%Y%m%dT%H%M%SZ"):
        try:
            return datetime.strptime(bt, fmt)
        except Exception:
            pass
    return datetime.min

# ---------------------- Persistenza ----------------------
def save_or_update_battlelog(
    player_tag: str,
    folder: Optional[str | os.PathLike] = None,
) -> Dict[str, Any]:
    """
    Scarica il battlelog del player e lo unisce al file esistente (se c'è),
    aggiungendo solo i match nuovi (dedup by _match_key).
    Salva per default in:
      - /home/simonetto/royale/data/all/<TAG>.json
      - /home/simonetto/royale/data/mine/<TAG>.json  se TAG == #88V8GQU
    (Override root con ROYALE_DATA_DIR)
    """
    base_dir = Path(folder).resolve() if folder else get_data_dir(player_tag)
    base_dir.mkdir(parents=True, exist_ok=True)

    # Mantieni il '#' nel filename, come da tua convenzione
    path = (base_dir / f"{player_tag}.json").resolve()

    # 1) carica esistenti
    existing: List[Dict[str, Any]] = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                existing = data
        except Exception:
            existing = []

    # 2) chiavi già viste
    seen = {_match_key(m) for m in existing}

    # 3) fetch nuovi
    fresh = get_battlelog(player_tag)

    # 4) aggiungi solo i nuovi
    to_add = [m for m in fresh if _match_key(m) not in seen]

    # 5) merge
    merged = existing + to_add

    # 6) ordina per data (più recenti prima)
    merged.sort(key=lambda m: _parse_battletime(str(m.get("battleTime", ""))), reverse=True)

    # 7) salva (scrittura “atomica” semplice)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

    return {
        "file": str(path),
        "previous": len(existing),
        "fetched": len(fresh),
        "added": len(to_add),
        "total": len(merged),
    }

def save_opponents_from_battlelog(battlelog: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Per ogni match del tuo battlelog salva/aggiorna il file dell'avversario.
    Ritorna la lista delle statistiche per ciascun avversario processato.
    """
    stats: List[Dict[str, Any]] = []
    for match in (battlelog or []):
        opps = (match.get("opponent") or [])
        if not opps:
            continue
        tag = opps[0].get("tag")
        if not tag:
            continue
        try:
            stats.append(save_or_update_battlelog(tag))
        except Exception as e:
            stats.append({"file": None, "error": str(e), "tag": tag})
    return stats

# ---------------------- Loader da file ----------------------
def load_battlelog_from_file(path: str | Path) -> List[Dict[str, Any]]:
    """
    Carica un battlelog Clash Royale da un file JSON già scaricato.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"File non trovato: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Formato non valido in {p}, attesa una lista di match")
    return data

def load_battlelog_by_tag(player_tag: str) -> List[Dict[str, Any]]:
    """
    Legge il battlelog locale per un dato tag dalla cartella di default
    (rispetta la regola all/mine). Utile per evitare di passare il path a mano.
    """
    base_dir = get_data_dir(player_tag)
    path = (base_dir / f"{player_tag}.json").resolve()
    return load_battlelog_from_file(path)

__all__ = [
    "enc_tag",
    "tag_clean",
    "get_battlelog",
    "save_or_update_battlelog",
    "save_opponents_from_battlelog",
    "load_battlelog_from_file",
    "load_battlelog_by_tag",
    "get_data_dir",
]
