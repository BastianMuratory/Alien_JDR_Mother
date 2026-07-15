#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveur local « Terminal de bord » — pour une partie d'Alien (jeu de rôle).

Aucune dépendance : uniquement la bibliothèque standard de Python 3.
  1) Mets  serveur.py  et  index.html  dans le MÊME dossier.
  2) Lance :   python3 serveur.py
  3) Toi (MJ) : ouvre  http://localhost:8000  et coche « Je suis le Maître du Jeu ».
  4) Joueurs  : sur le même réseau Wi-Fi, ouvrent  http://IP-DE-TON-PC:8000
                (trouve l'IP avec  hostname -I  ou  ip addr ).

Le MJ peut envoyer un message à UN joueur précis (canal privé) ou à TOUS.
Les joueurs ne voient que ce qui leur est adressé. Ils peuvent poser des
questions qui n'arrivent qu'au MJ.
"""

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ----------------------- CONFIGURATION -----------------------
VERSION = "1.3"           # affiché au démarrage — si le bandeau ne montre pas cette
                          # version, un ANCIEN serveur tourne encore (port occupé)
HOST = "0.0.0.0"          # 0.0.0.0 = accessible depuis tout le réseau local
PORT = 8000
ADMIN_CODE = "nostromo"   # <-- CHANGE-LE : c'est le code que TOI (MJ) tapes pour être admin
ONLINE_WINDOW = 30        # secondes sans activité avant qu'un joueur soit « hors-ligne »
PERSIST = True            # sauvegarde la partie dans partie.json (survit à un redémarrage)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(HERE, "index.html")
SAVE_FILE = os.path.join(HERE, "partie.json")
RESERVED = {"mj", "gm", "maitre", "maître", "admin", "ia", "tous", "all"}

# ----------------------- ÉTAT PARTAGÉ -----------------------
lock = threading.Lock()
state = {"users": {}, "messages": [], "next_id": 1, "codes": {}, "timer": None}
# users : token -> {"name":..., "role":"player"/"gm", "last_seen":epoch}
# messages : [{"id","frm","to","text","kind","speed","ts"}]
# codes : nom_en_minuscules -> code d'accès du personnage (choisi au 1er login)
# timer : None ou {"remaining":sec, "total":sec, "rate":float, "updated":epoch}
#         rate = vitesse d'écoulement (0 = pause, 1 = temps réel, 2 = double)


def load_state():
    if not PERSIST or not os.path.exists(SAVE_FILE):
        return
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        state["messages"] = data.get("messages", [])
        state["next_id"] = data.get("next_id", 1)
        state["codes"] = data.get("codes", {})
        state["timer"] = data.get("timer")
        print("[i] Partie précédente rechargée depuis partie.json")
    except Exception as e:
        print("[!] Impossible de recharger partie.json :", e)


def save_state():
    if not PERSIST:
        return
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"messages": state["messages"], "next_id": state["next_id"],
                       "codes": state["codes"], "timer": state.get("timer")},
                      f, ensure_ascii=False)
    except Exception as e:
        print("[!] Sauvegarde impossible :", e)


def player_list():
    now = time.time()
    seen = {}
    for u in state["users"].values():
        if u["role"] != "player":
            continue
        nm = u["name"]
        if nm not in seen or u["last_seen"] > seen[nm]:
            seen[nm] = u["last_seen"]
    return [{"name": nm, "online": (now - ls) < ONLINE_WINDOW}
            for nm, ls in sorted(seen.items())]


def timer_snapshot():
    """État actuel du compte à rebours (temps restant calculé côté serveur)."""
    t = state.get("timer")
    if not t:
        return None
    rem = max(0.0, t["remaining"] - (time.time() - t["updated"]) * t["rate"])
    return {"remaining": rem, "total": t.get("total", 0), "rate": t["rate"]}


def visible_for(user, msg):
    """Un joueur ne voit que ce qui le concerne ; le MJ voit tout."""
    if user["role"] == "gm":
        return True
    nm = user["name"]
    return msg["to"] == nm or msg["to"] == "all" or msg["frm"] == nm


# ----------------------- SERVEUR HTTP -----------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silence les logs verbeux

    # --- utilitaires ---
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return {}

    def _auth(self, token):
        u = state["users"].get(token)
        if u:
            u["last_seen"] = time.time()
        return u

    # --- GET ---
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            return self._serve_index()

        if path == "/api/poll":
            qs = parse_qs(parsed.query)
            token = (qs.get("token") or [""])[0]
            since = int((qs.get("since") or ["0"])[0] or 0)
            with lock:
                user = self._auth(token)
                if not user:
                    return self._json({"error": "Session expirée. Reconnecte-toi."}, 200)
                msgs = [m for m in state["messages"]
                        if m["id"] > since and visible_for(user, m)]
                players = player_list() if user["role"] == "gm" else []
                return self._json({"messages": msgs, "players": players,
                                   "timer": timer_snapshot(), "now": time.time()})

        return self._json({"error": "not found"}, 404)

    # --- POST ---
    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_body()

        if path == "/api/login":
            name = (data.get("name") or "").strip()[:32]
            role = data.get("role", "player")
            if not name:
                return self._json({"error": "Nom manquant."})
            if role == "gm":
                if data.get("code", "") != ADMIN_CODE:
                    return self._json({"error": "Code admin incorrect."})
                name = "MJ"
                token = uuid.uuid4().hex
                with lock:
                    state["users"][token] = {"name": name, "role": role, "last_seen": time.time()}
                return self._json({"token": token, "name": name, "role": role})
            # --- joueur : code d'accès personnel ---
            if name.lower() in RESERVED:
                return self._json({"error": "Ce nom est réservé, choisis-en un autre."})
            code = (data.get("code") or "").strip()[:64]
            if not code:
                return self._json({"error": "Code d'accès requis."})
            key = name.lower()
            with lock:
                codes = state.setdefault("codes", {})
                if key in codes:
                    if codes[key] != code:
                        return self._json({"error": "Code incorrect pour ce personnage."})
                else:
                    codes[key] = code   # premier accès : le code est enregistré
                    save_state()
                token = uuid.uuid4().hex
                state["users"][token] = {"name": name, "role": role, "last_seen": time.time()}
            return self._json({"token": token, "name": name, "role": role})

        if path == "/api/resetcode":
            # MJ uniquement : efface le code d'un personnage (il en choisira
            # un nouveau à sa prochaine connexion)
            token = data.get("token", "")
            with lock:
                user = self._auth(token)
                if not user or user["role"] != "gm":
                    return self._json({"error": "Non autorisé."})
                name = (data.get("name") or "").strip().lower()
                if not name:
                    return self._json({"error": "Nom manquant."})
                state.setdefault("codes", {}).pop(name, None)
                # déconnecte les sessions actives de ce personnage
                for tk in [t for t, u in state["users"].items()
                           if u["role"] == "player" and u["name"].lower() == name]:
                    del state["users"][tk]
                save_state()
            return self._json({"ok": True})

        if path == "/api/delmsg":
            # MJ uniquement : supprime UN message (historique + écran du joueur).
            # Un message de contrôle kind="delete" est diffusé aux destinataires
            # concernés pour retirer les lignes déjà affichées.
            token = data.get("token", "")
            with lock:
                user = self._auth(token)
                if not user or user["role"] != "gm":
                    return self._json({"error": "Non autorisé."})
                try:
                    mid = int(data.get("id", 0))
                except (TypeError, ValueError):
                    mid = 0
                target = next((m for m in state["messages"] if m["id"] == mid), None)
                if not target:
                    return self._json({"error": "Message introuvable."})
                if target["kind"] not in ("text", "alert"):
                    return self._json({"error": "Ce message ne peut pas être supprimé."})
                state["messages"].remove(target)
                audience = target["to"] if target["to"] != "MJ" else target["frm"]
                msg = {"id": state["next_id"], "frm": "MJ", "to": audience,
                       "text": str(mid), "kind": "delete", "speed": 0, "ts": time.time()}
                state["next_id"] += 1
                state["messages"].append(msg)
                save_state()
                return self._json({"ok": True})

        if path == "/api/clearall":
            # MJ uniquement : vide le fil de diffusion générale (historique
            # supprimé) et efface l'écran de tous les joueurs.
            token = data.get("token", "")
            with lock:
                user = self._auth(token)
                if not user or user["role"] != "gm":
                    return self._json({"error": "Non autorisé."})
                state["messages"] = [m for m in state["messages"] if m.get("to") != "all"]
                msg = {"id": state["next_id"], "frm": "MJ", "to": "all",
                       "text": "", "kind": "clear", "speed": 0, "ts": time.time()}
                state["next_id"] += 1
                state["messages"].append(msg)
                save_state()
                return self._json({"ok": True, "id": msg["id"]})

        if path == "/api/timer":
            # MJ uniquement : compte à rebours diffusé à tous les joueurs.
            # actions : start (minutes, rate) / rate (rate) / stop
            token = data.get("token", "")
            with lock:
                user = self._auth(token)
                if not user or user["role"] != "gm":
                    return self._json({"error": "Non autorisé."})
                action = data.get("action")
                now = time.time()

                def clamp_rate(v):
                    try:
                        return min(max(float(v), 0.0), 4.0)
                    except (TypeError, ValueError):
                        return 1.0

                if action == "start":
                    try:
                        minutes = float(data.get("minutes", 0))
                    except (TypeError, ValueError):
                        minutes = 0
                    if not (0 < minutes <= 24 * 60):
                        return self._json({"error": "Durée invalide."})
                    secs = minutes * 60
                    state["timer"] = {"remaining": secs, "total": secs,
                                      "rate": clamp_rate(data.get("rate", 1)),
                                      "updated": now}
                elif action == "rate":
                    t = state.get("timer")
                    if t:
                        # fige le temps déjà écoulé puis applique la nouvelle vitesse
                        t["remaining"] = max(0.0, t["remaining"] - (now - t["updated"]) * t["rate"])
                        t["updated"] = now
                        t["rate"] = clamp_rate(data.get("rate", 1))
                elif action == "stop":
                    state["timer"] = None
                else:
                    return self._json({"error": "Action inconnue."})
                save_state()
                return self._json({"ok": True, "timer": timer_snapshot()})

        if path == "/api/send":
            token = data.get("token", "")
            with lock:
                user = self._auth(token)
                if not user:
                    return self._json({"error": "Session expirée."})
                if user["role"] == "gm":
                    to = (data.get("to") or "all").strip()
                    frm = "MJ"
                    kind = data.get("kind", "text")
                    speed = int(data.get("speed", 24))
                else:
                    to = "MJ"                     # un joueur écrit toujours au MJ
                    frm = user["name"]
                    kind = "text"
                    speed = 0
                text = (data.get("text") or "")[:4000]
                if kind == "text" and not text.strip() and kind not in ("clear", "boot"):
                    if not text.strip():
                        return self._json({"error": "Message vide."})
                msg = {"id": state["next_id"], "frm": frm, "to": to,
                       "text": text, "kind": kind, "speed": speed, "ts": time.time()}
                state["next_id"] += 1
                state["messages"].append(msg)
                save_state()
                return self._json({"ok": True, "id": msg["id"]})

        if path.startswith("/api/"):
            print(f"[!] Requête API inconnue : {path} — ce serveur (v{VERSION}) "
                  "est-il bien la dernière version ?")
        return self._json({"error": "not found"}, 404)

    def _serve_index(self):
        try:
            with open(INDEX_FILE, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            body = (b"<h1>index.html introuvable</h1>"
                    b"<p>Place index.html dans le meme dossier que serveur.py.</p>")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def local_ips():
    ips = []
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return ips


def main():
    load_state()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 56)
    print(f" TERMINAL DE BORD — serveur en ligne (v{VERSION})")
    print("=" * 56)
    print(f"  MJ (toi)     : http://localhost:{PORT}")
    for ip in local_ips():
        print(f"  Joueurs      : http://{ip}:{PORT}")
    print(f"  Code admin   : {ADMIN_CODE!r}  (à donner à personne !)")
    print("  Arrêter      : Ctrl+C")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[i] Arrêt du serveur.")
        server.shutdown()


if __name__ == "__main__":
    main()
