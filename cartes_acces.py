# -*- coding: utf-8 -*-
"""
Générateur de cartes d'accès Weyland-Yutani — JDR Alien
--------------------------------------------------------
Demande les infos du personnage puis génère deux PNG (recto/verso)
dans le dossier ./cartes_acces/

Dépendance : Pillow  ->  pip install pillow
"""

import os
import random
import re
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Il faut installer Pillow :  pip install pillow")
    sys.exit(1)

# ---------------------------------------------------------------- constantes
W, H = 1276, 2026          # 54 x 85.6 mm à 600 dpi (format carte bancaire, portrait)
DPI = (600, 600)
BG = (10, 10, 12)          # noir profond
FG = (235, 235, 235)       # blanc / argent
DIM = (150, 150, 150)      # argent atténué
R_CORNER = 90

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cartes_acces")

# ---------------------------------------------------------------- polices
def _find_font(candidates):
    roots = ["C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/",
             "/usr/share/fonts/truetype/", "/System/Library/Fonts/", ""]
    for name in candidates:
        for root in roots:
            p = os.path.join(root, name)
            if os.path.exists(p):
                return p
    return None

FONT_BOLD = _find_font(["bahnschrift.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
                        "Arial Bold.ttf", "Helvetica.ttc"])
FONT_REG = _find_font(["arial.ttf", "DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"])
FONT_MONO = _find_font(["consola.ttf", "DejaVuSansMono.ttf", "cour.ttf", "Menlo.ttc"])
FONT_CJK = _find_font(["msgothic.ttc", "meiryo.ttc", "YuGothM.ttc",
                       "NotoSansCJK-Regular.ttc", "unifont.ttf"])

def font(path, size):
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)

# ---------------------------------------------------------------- helpers
def text_size(draw, txt, fnt, spacing=0):
    total, hmax = 0, 0
    for c in txt:
        x0, y0, x1, y1 = draw.textbbox((0, 0), c, font=fnt)
        total += (x1 - x0) + spacing
        hmax = max(hmax, y1)
    return total - spacing if txt else 0, hmax

def spaced_text(draw, xy, txt, fnt, fill, spacing=0, anchor_center_x=None):
    """Texte avec interlettrage. Si anchor_center_x est donné, centre sur ce x."""
    w, _ = text_size(draw, txt, fnt, spacing)
    x, y = xy
    if anchor_center_x is not None:
        x = anchor_center_x - w / 2
    for c in txt:
        draw.text((x, y), c, font=fnt, fill=fill)
        x0, y0, x1, y1 = draw.textbbox((0, 0), c, font=fnt)
        x += (x1 - x0) + spacing
    return w

def vertical_text(img, xy, txt, fnt, fill, spacing=0, up=True):
    """Texte vertical (tourné 90°). up=True : se lit de bas en haut."""
    tmp = Image.new("RGBA", (2200, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    w = spaced_text(d, (10, 10), txt, fnt, fill, spacing)
    bbox = tmp.getbbox()
    if bbox is None:
        return
    tmp = tmp.crop(bbox)
    tmp = tmp.rotate(90 if up else -90, expand=True)
    img.paste(tmp, (int(xy[0]), int(xy[1])), tmp)
    return tmp.size

def polyline(draw, pts, width, fill=FG, closed=False):
    seq = list(pts) + ([pts[0]] if closed else [])
    draw.line(seq, fill=fill, width=width, joint="curve")

# ---------------------------------------------------------------- logo W/Y
def wy_logo(img, cx, cy, scale, color=FG):
    """Logo Weyland-Yutani (double V entrelacé) dessiné en haute résolution."""
    S = 4  # suréchantillonnage pour l'anticrénelage
    w = int(2.3 * scale) * S
    h = int(1.15 * scale) * S
    tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    s = scale * S
    t = 0.16 * s                     # épaisseur des branches
    top, bot = 0.06 * s, 1.06 * s    # y haut / bas

    def slant(x_top, x_bot, y_a=top, y_b=bot):
        """Trait incliné à extrémités coupées horizontalement."""
        dx = t / 2 * (1 + abs(x_bot - x_top) / (y_b - y_a) ** 1) ** 0
        d.polygon([(x_top - t * 0.62, y_a), (x_top + t * 0.62, y_a),
                   (x_bot + t * 0.62, y_b), (x_bot - t * 0.62, y_b)], fill=color)

    mid = w / 2
    # V extérieur gauche
    slant(mid - 0.95 * s, mid - 0.38 * s)
    slant(mid + 0.19 * s, mid - 0.38 * s)
    # V extérieur droit
    slant(mid - 0.19 * s, mid + 0.38 * s)
    slant(mid + 0.95 * s, mid + 0.38 * s)
    tmp = tmp.resize((w // S, h // S), Image.LANCZOS)
    img.paste(tmp, (int(cx - tmp.width / 2), int(cy - tmp.height / 2)), tmp)

# ---------------------------------------------------------------- icônes
def icon_warning(d, cx, cy, r, color=FG, lw=7):
    import math
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
           for a in (-90, 30, 150)]
    polyline(d, pts, lw, color, closed=True)
    d.line([(cx, cy - r * 0.35), (cx, cy + r * 0.18)], fill=color, width=lw + 2)
    d.ellipse([cx - lw * 0.7, cy + r * 0.38 - lw * 0.7,
               cx + lw * 0.7, cy + r * 0.38 + lw * 0.7], fill=color)

def icon_radiation(d, cx, cy, r, color=FG):
    for a in (90, 210, 330):
        d.pieslice([cx - r, cy - r, cx + r, cy + r], a - 30, a + 30, fill=color)
    d.ellipse([cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42], fill=BG)
    d.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=color)

def icon_biohazard(d, cx, cy, r, color=FG):
    import math
    lw = max(5, int(r * 0.19))
    for a in (30, 150, 270):
        ox = cx + 0.62 * r * math.cos(math.radians(a))
        oy = cy - 0.62 * r * math.sin(math.radians(a))
        rr = 0.46 * r
        d.ellipse([ox - rr, oy - rr, ox + rr, oy + rr], outline=color, width=lw)
    d.ellipse([cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4], fill=BG)
    d.ellipse([cx - r * 0.24, cy - r * 0.24, cx + r * 0.24, cy + r * 0.24],
              outline=color, width=lw - 1)

def hazard_badge(d, cx, cy, r, kind):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=FG, width=5)
    # petits crans autour du cercle
    import math
    for a in range(0, 360, 30):
        x1 = cx + (r + 3) * math.cos(math.radians(a))
        y1 = cy + (r + 3) * math.sin(math.radians(a))
        x2 = cx + (r + 10) * math.cos(math.radians(a))
        y2 = cy + (r + 10) * math.sin(math.radians(a))
        d.line([(x1, y1), (x2, y2)], fill=DIM, width=3)
    ir = r * 0.58
    if kind == "warn":
        icon_warning(d, cx, cy + r * 0.08, ir)
    elif kind == "rad":
        icon_radiation(d, cx, cy, ir)
    else:
        icon_biohazard(d, cx, cy, ir)

# ---------------------------------------------------------------- barcode
def barcode(d, x, y, w, h, seed, color=FG):
    rnd = random.Random(seed)
    cx = x
    while cx < x + w:
        bw = rnd.choice([3, 3, 5, 5, 8, 12])
        if rnd.random() < 0.55:
            d.rectangle([cx, y, cx + bw, y + h], fill=color)
        cx += bw + rnd.choice([3, 5, 7])

# ---------------------------------------------------------------- cadre tech
def tech_frame(d, inset=56, lw=6):
    """Cadre anguleux à coins chanfreinés, façon interface Weyland."""
    i = inset
    c = 70   # chanfrein
    pts = [
        (i + c, i), (W - i - 170, i),                # haut (encoche à droite)
        (W - i - 130, i + 40), (W - i, i + 40),
        (W - i, H - i - c), (W - i - c, H - i),      # coin bas-droit chanfreiné
        (i + 170, H - i), (i + 130, H - i - 40),
        (i, H - i - 40),
        (i, i + c),                                   # coin haut-gauche chanfreiné
    ]
    polyline(d, pts, lw, FG, closed=True)
    # double ligne d'accent en haut à gauche et en bas à droite
    d.line([(i + c, i + 16), (W // 2, i + 16)], fill=DIM, width=3)
    d.line([(W // 2, H - i - 16), (W - i - c, H - i - 16)], fill=DIM, width=3)
    # triangles décoratifs
    t = 26
    d.polygon([(W - i - 60, i - 26), (W - i - 60 + t, i - 26),
               (W - i - 60 + t / 2, i - 4)], fill=FG)
    d.polygon([(i + 60, H - i + 26), (i + 60 + t, H - i + 26),
               (i + 60 + t / 2, H - i + 4)], fill=FG)

def deco_left(d, x, y0, y1):
    """Blocs 'circuit' en escalier sur la gauche (comme le verso du modèle)."""
    rnd = random.Random(7)
    y = y0
    while y < y1:
        w = rnd.choice([18, 30, 44])
        h = rnd.choice([12, 20, 34])
        d.rectangle([x, y, x + w, y + h], fill=FG if rnd.random() < .5 else DIM)
        y += h + rnd.choice([10, 18, 30])

def deco_dots(d, x, y0, y1, step=52, size=16):
    y = y0
    while y < y1:
        d.rectangle([x, y, x + size, y + size], fill=FG)
        y += step

def deco_ruler(d, x, y0, y1):
    y = y0
    k = 0
    while y < y1:
        w = 34 if k % 5 == 0 else 18
        d.line([(x, y), (x + w, y)], fill=FG, width=4)
        y += 14
        k += 1

# ---------------------------------------------------------------- carte de base
def new_card():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, W - 3, H - 3], radius=R_CORNER, outline=(90, 90, 90), width=3)
    return img, d

def fit_font(d, txt, path, size, max_w, spacing=0):
    while size > 20:
        f = font(path, size)
        w, _ = text_size(d, txt, f, spacing)
        if w <= max_w:
            return f
        size -= 4
    return font(path, size)

# ---------------------------------------------------------------- RECTO
def make_front(p):
    img, d = new_card()
    tech_frame(d)

    left_x, right_x = 150, 990

    # --- textes verticaux
    f_vert = font(FONT_BOLD, 46)
    vertical_text(img, (W - 130, 150), (p["division"].upper() + " DIVISION")
                  if "DIVISION" not in p["division"].upper() else p["division"].upper(),
                  f_vert, FG, spacing=6)
    vertical_text(img, (W - 196, 150), "YUTANI CORPORATION", f_vert, FG, spacing=6)
    vertical_text(img, (W - 196, 1240), "WEYLAND", f_vert, FG, spacing=6)
    vertical_text(img, (86, 660), "BUILDING BETTER WORLDS", font(FONT_BOLD, 40), FG, spacing=8)

    # --- bloc identité
    y = 200
    name = (p["prenom"] + " " + p["nom"]).upper()
    f_name = fit_font(d, name, FONT_BOLD, 82, right_x - left_x - 60, spacing=4)
    spaced_text(d, (left_x, y), name, f_name, FG, spacing=4)
    y += f_name.size + 34
    f_sub = font(FONT_BOLD, 46)
    spaced_text(d, (left_x, y), p["profession"].upper(), f_sub, DIM, spacing=4)
    y += 78
    f_id = font(FONT_MONO, 46)
    d.text((left_x, y + 40), "I.D.:  #" + p["id"], font=f_id, fill=FG)
    d.text((left_x, y + 108), "REF:  #" + p["ref"], font=f_id, fill=FG)
    d.line([(left_x, y + 200), (right_x - 60, y + 200)], fill=DIM, width=3)

    # --- icônes de danger (colonne gauche)
    for i, kind in enumerate(("warn", "rad", "bio")):
        hazard_badge(d, 260, 900 + i * 230, 82, kind)

    # --- emblème Yutani + kanji (droite des icônes)
    ex, ey = 660, 930
    d.rounded_rectangle([ex - 95, ey - 80, ex + 95, ey + 80], radius=26, outline=FG, width=6)
    wy_logo(img, ex - 8, ey + 10, 46)
    d.ellipse([ex + 36, ey - 50, ex + 62, ey - 24], fill=FG)   # petites bulles du logo
    d.ellipse([ex + 62, ey - 26, ex + 78, ey - 10], fill=FG)
    if FONT_CJK:
        f_jp = font(FONT_CJK, 40)
        d.text((ex, ey + 130), "湯谷株式会社", font=f_jp, fill=FG, anchor="mm")
    else:
        spaced_text(d, (0, ey + 112), "YUTANI CORP.", font(FONT_BOLD, 34), FG, 6,
                    anchor_center_x=ex)

    # petit texte technique
    f_tiny = font(FONT_MONO, 26)
    d.text((660, 1120), "CLEARANCE LEVEL 3-A", font=f_tiny, fill=DIM, anchor="ma")
    d.text((660, 1160), "PROPERTY OF W-Y CORP", font=f_tiny, fill=DIM, anchor="ma")

    # --- grand logo bas
    wy_logo(img, W // 2, 1560, 130)
    spaced_text(d, (0, 1660), "WEYLAND YUTANI CORP", font(FONT_BOLD, 40), FG, 10,
                anchor_center_x=W // 2)

    # --- code-barres
    barcode(d, 300, 1800, 680, 110, p["id"])
    return img

# ---------------------------------------------------------------- VERSO
def make_back(p):
    img, d = new_card()
    tech_frame(d)

    # --- logo + titres
    wy_logo(img, W // 2, 330, 170)
    spaced_text(d, (0, 470), "WEYLAND YUTANI CORP", font(FONT_BOLD, 54), FG, 8,
                anchor_center_x=W // 2)
    spaced_text(d, (0, 550), "BUILDING BETTER WORLDS", font(FONT_BOLD, 30), DIM, 12,
                anchor_center_x=W // 2)

    # --- déco
    deco_ruler(d, 96, 150, 420)
    deco_left(d, 110, 700, 1160)
    deco_dots(d, W - 160, 760, 1560)
    vertical_text(img, (W - 210, 690), "TERMINAL ACCESS", font(FONT_BOLD, 52), FG, spacing=8)

    # --- icônes de danger
    for i, kind in enumerate(("warn", "rad", "bio")):
        hazard_badge(d, 300, 800 + i * 230, 82, kind)

    # --- bloc identifiants
    bx0, by0, bx1, by1 = 470, 1330, W - 270, 1690
    pts = [(bx0 + 40, by0), (bx1, by0), (bx1, by1 - 40), (bx1 - 40, by1),
           (bx0, by1), (bx0, by0 + 40)]
    polyline(d, pts, 5, FG, closed=True)
    f_lab = font(FONT_BOLD, 34)
    max_w = bx1 - bx0 - 100
    d.text((bx0 + 50, by0 + 42), "USER ID", font=f_lab, fill=DIM)
    d.text((bx0 + 50, by0 + 92), p["username"],
           font=fit_font(d, p["username"], FONT_MONO, 52, max_w), fill=FG)
    d.line([(bx0 + 50, by0 + 180), (bx1 - 50, by0 + 180)], fill=DIM, width=3)
    d.text((bx0 + 50, by0 + 204), "ACCESS CODE", font=f_lab, fill=DIM)
    d.text((bx0 + 50, by0 + 254), p["password"],
           font=fit_font(d, p["password"], FONT_MONO, 52, max_w), fill=FG)

    # remplissage tech de la zone centrale
    f_tech = font(FONT_MONO, 28)
    d.text((580, 1060), "MU-TH-UR 6500 UPLINK", font=f_tech, fill=DIM, anchor="la")
    d.text((580, 1110), "ID: #" + p["id"] + "-" + p["ref"][:4], font=f_tech, fill=DIM, anchor="la")
    d.text((580, 1160), "CLEARANCE: LVL 3-A", font=f_tech, fill=DIM, anchor="la")

    f_tiny = font(FONT_MONO, 26)
    d.text((W // 2, 1740), "MU-TH-UR 6500 // AUTHORIZED PERSONNEL ONLY",
           font=f_tiny, fill=DIM, anchor="ma")

    # --- code-barres
    barcode(d, 300, 1800, 680, 110, p["ref"])
    return img

# ---------------------------------------------------------------- entrée / sortie
def ask(label):
    while True:
        v = input(label).strip()
        if v:
            return v
        print("  (champ obligatoire)")

def sanitize(s):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s)
    return s.strip("_") or "perso"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 52)
    print("  WEYLAND-YUTANI — GÉNÉRATEUR DE CARTES D'ACCÈS")
    print("=" * 52)
    while True:
        print()
        p = {
            "prenom":     ask("Prénom            : "),
            "nom":        ask("Nom               : "),
            "profession": ask("Profession        : "),
            "division":   ask("Division          : "),
            "username":   ask("Username (site)   : "),
            "password":   ask("Password (site)   : "),
            "id":  "".join(random.choices("0123456789", k=8)),
            "ref": "".join(random.choices("0123456789", k=8)),
        }
        base = os.path.join(OUT_DIR, f"carte_{sanitize(p['prenom'])}_{sanitize(p['nom'])}")
        make_front(p).save(base + "_recto.png", dpi=DPI)
        make_back(p).save(base + "_verso.png", dpi=DPI)
        print(f"\n  -> {base}_recto.png")
        print(f"  -> {base}_verso.png")
        again = input("\nCréer une autre carte ? (o/n) : ").strip().lower()
        if again not in ("o", "oui", "y", "yes"):
            break
    print("\nCartes générées dans :", OUT_DIR)

if __name__ == "__main__":
    main()
