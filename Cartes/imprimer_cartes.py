# -*- coding: utf-8 -*-
"""
Planche d'impression A4 — cartes d'accès Weyland-Yutani
--------------------------------------------------------
Rassemble tous les PNG de ./cartes_acces/ sur des pages A4 (PDF)
à la taille réelle d'une carte Pokémon en hauteur (88 mm),
proportions conservées (~55,4 x 88 mm), avec repères de découpe.

Usage :  python imprimer_cartes.py
Sortie :  cartes_acces/planche_impression.pdf  (imprimer à 100 %, sans mise à l'échelle !)

Dépendance : Pillow  ->  pip install pillow
"""

import os
import sys
import glob

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Il faut installer Pillow :  pip install pillow")
    sys.exit(1)

# ---------------------------------------------------------------- réglages
DPI = 300
MM = DPI / 25.4                       # pixels par millimètre
A4_W, A4_H = int(210 * MM), int(297 * MM)

CARD_H = int(88 * MM)                 # hauteur carte Pokémon
GAP = int(5 * MM)                     # espace entre cartes
MARK = int(3 * MM)                    # longueur des traits de coupe
MARK_COLOR = (150, 150, 150)

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cartes_acces")
OUT = os.path.join(DIR, "planche_impression.pdf")


def main():
    files = sorted(glob.glob(os.path.join(DIR, "carte_*.png")))
    if not files:
        print("Aucune carte trouvée dans", DIR)
        sys.exit(1)

    # tri : recto puis verso de chaque perso restent côte à côte
    print(f"{len(files)} cartes à mettre en page…")

    # dimensions d'une carte (à partir de la première image)
    with Image.open(files[0]) as im0:
        card_w = round(im0.width / im0.height * CARD_H)

    cols = max(1, (A4_W - GAP) // (card_w + GAP))
    rows = max(1, (A4_H - GAP) // (CARD_H + GAP))
    per_page = cols * rows
    margin_x = (A4_W - cols * card_w - (cols - 1) * GAP) // 2
    margin_y = (A4_H - rows * CARD_H - (rows - 1) * GAP) // 2

    pages = []
    for start in range(0, len(files), per_page):
        page = Image.new("RGB", (A4_W, A4_H), "white")
        d = ImageDraw.Draw(page)
        for k, path in enumerate(files[start:start + per_page]):
            r, c = divmod(k, cols)
            x = margin_x + c * (card_w + GAP)
            y = margin_y + r * (CARD_H + GAP)
            with Image.open(path) as im:
                page.paste(im.resize((card_w, CARD_H), Image.LANCZOS), (x, y))
            # repères de découpe aux 4 coins
            for cx in (x, x + card_w):
                for cy in (y, y + CARD_H):
                    d.line([(cx - MARK, cy), (cx + MARK, cy)], fill=MARK_COLOR, width=2)
                    d.line([(cx, cy - MARK), (cx, cy + MARK)], fill=MARK_COLOR, width=2)
        pages.append(page)

    try:
        pages[0].save(OUT, save_all=True, append_images=pages[1:],
                      resolution=DPI, quality=95)
    except (KeyError, OSError):
        # Pillow sans support JPEG : PDF sans perte (fichier plus gros)
        pages = [p.convert("P", palette=Image.ADAPTIVE, colors=256) for p in pages]
        pages[0].save(OUT, save_all=True, append_images=pages[1:], resolution=DPI)
    print(f"OK : {len(pages)} page(s), {cols}x{rows} cartes par page")
    print("->", OUT)
    print("Imprimer à taille réelle (100 %, sans ajustement à la page).")


if __name__ == "__main__":
    main()
