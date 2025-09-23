# royale/cards/cards.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Percorsi di default (indipendenti dalla cwd)
_THIS = Path(__file__).resolve()
_BASE = _THIS.parent
_DEFAULT_DICT = _BASE / "cards_dict.json"
_DEFAULT_IMG_DIR = _BASE / "cards_images"

# ---------------- Loader ----------------
def load_card_map(
    map_path: Optional[str | os.PathLike] = None,
    img_dir: Optional[str | os.PathLike] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Carica il mapping id -> {name, image} dal cards_dict.json
    e aggiunge il path assoluto al file immagine.
    """
    chosen = Path(map_path).resolve() if map_path else _DEFAULT_DICT
    img_dir_path = Path(img_dir).resolve() if img_dir else _DEFAULT_IMG_DIR

    with open(chosen, "r", encoding="utf-8") as f:
        raw = json.load(f)

    out: Dict[str, Dict[str, Any]] = {}
    for cid, val in raw.items():
        # val deve già essere {name, image}
        name = val.get("name")
        image = val.get("image")
        path = str(img_dir_path / image) if image else None
        out[str(cid)] = {"name": name, "image": image, "path": path}
    return out

# ---------------- Visualizzazioni ----------------
def show_cards(
    card_ids: List[str | int],
    ncols: int = 4,
    card_map: Optional[Dict[str, Dict[str, Any]]] = None,
):
    """
    Mostra le immagini delle carte date le loro ID.
    """
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    if card_map is None:
        card_map = load_card_map()

    n = len(card_ids)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(3 * ncols, 4 * nrows))
    axes = axes.flatten() if nrows * ncols > 1 else [axes]

    for i, cid in enumerate(card_ids):
        ax = axes[i]
        ax.axis("off")
        info = card_map.get(str(cid))
        if not info:
            ax.text(0.5, 0.5, f"ID {cid}\n(sconosciuta)", ha="center", va="center")
            continue

        name = info["name"]
        path = info.get("path")
        if path and Path(path).exists():
            img = mpimg.imread(path)
            ax.imshow(img)
            ax.set_title(name, fontsize=10)
        else:
            ax.text(0.5, 0.5, name, ha="center", va="center")
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
    plt.tight_layout()
    plt.show()

def _extract_side(side: dict) -> dict:
    name = side.get("name", "Unknown")
    tag = side.get("tag", "")
    crowns = side.get("crowns", 0)
    cards = side.get("cards", []) or []
    deck = [{"id": c.get("id"), "name": c.get("name")} for c in cards]
    return {"name": name, "tag": tag, "crowns": crowns, "deck": deck}

def show_match_decks(
    match: dict,
    card_map: Optional[Dict[str, Dict[str, Any]]] = None,
    title: Optional[str] = None,
):
    """
    Mostra i deck dei due giocatori con layout:
      [ 2x4 carte Player ] | [ 2x4 carte Opponent ]
    e stampa il risultato in corone.
    """
    if match['gameMode']['name'] != 'Ladder':
        return print("show_match_decks() funziona solo per partite Ladder, il match è di tipo:", match['gameMode']['name'])
    
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    if card_map is None:
        card_map = load_card_map()

    team = match.get("team", [])
    opp = match.get("opponent", [])
    if not team or not opp:
        print("Match non valido: mancano team/opponent")
        return

    team0 = _extract_side(team[0])
    opp0 = _extract_side(opp[0])

    # stampa risultato
    left = f"{team0['name']} {team0['tag']}".strip()
    right = f"{opp0['name']} {opp0['tag']}".strip()
    score = f"{team0['crowns']} - {opp0['crowns']}"
    print(f"Risultato: {left}  {score}  {right}")

    fig = plt.figure(figsize=(18, 6))
    gs = fig.add_gridspec(
        2, 9, width_ratios=[1, 1, 1, 1, 0.08, 1, 1, 1, 1], hspace=0.3, wspace=0.15
    )
    if title:
        fig.suptitle(title, fontsize=14)

    def draw_block(row_start, col_start, deck, block_title):
        idx = 0
        for r in range(2):
            for c in range(4):
                ax = fig.add_subplot(gs[row_start + r, col_start + c])
                ax.axis("off")
                if idx < len(deck):
                    cid = deck[idx]["id"]
                    info = card_map.get(str(cid), {})
                    name = deck[idx]["name"] or info.get("name", "Unknown")
                    path = info.get("path")
                    if path and Path(path).exists():
                        img = mpimg.imread(path)
                        ax.imshow(img)
                        ax.set_title(name, fontsize=9)
                    else:
                        ax.text(0.5, 0.5, name, ha="center", va="center", wrap=True)
                idx += 1
        ax_title = fig.add_subplot(gs[row_start, col_start : col_start + 4])
        ax_title.axis("off")
        ax_title.set_title(block_title, fontsize=12, pad=10)

    draw_block(0, 0, team0["deck"], f"{team0['name']} ({team0['crowns']})")
    draw_block(0, 5, opp0["deck"], f"{opp0['name']} ({opp0['crowns']})")

    # separatore centrale
    ax_sep_top = fig.add_subplot(gs[0, 4])
    ax_sep_bot = fig.add_subplot(gs[1, 4])
    for ax_sep in (ax_sep_top, ax_sep_bot):
        ax_sep.axis("off")
        ax_sep.plot([0.5, 0.5], [0, 1])
        ax_sep.set_xlim(0, 1)
        ax_sep.set_ylim(0, 1)

    plt.show()

__all__ = ["load_card_map", "show_cards", "show_match_decks"]
