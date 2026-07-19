#!/usr/bin/env bash
# lancer.sh — tout-en-un : serveur + tunnel cloudflared + QR code dans le terminal.
#
#   ./lancer.sh
#
# 1) Démarre serveur.py en arrière-plan
# 2) Ouvre un tunnel public avec cloudflared (URL *.trycloudflare.com)
# 3) Affiche l'URL publique en QR code + toutes les infos utiles
# 4) Ctrl+C arrête proprement le serveur ET le tunnel
#
# Seule dépendance externe : cloudflared. L'outil QR (lib python « qrcode »)
# s'installe tout seul dans .venv/ au premier lancement.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"   # modifiable :  PORT=8123 ./lancer.sh
VENV="$HERE/.venv"
LOG_SERVEUR="/tmp/mother_serveur_$PORT.log"
LOG_TUNNEL="/tmp/mother_tunnel_$PORT.log"

VERT=$'\033[32m'; GRAS=$'\033[1m'; ROUGE=$'\033[31m'; JAUNE=$'\033[33m'; FIN=$'\033[0m'

# ----------------------- vérifications -----------------------
if ! command -v cloudflared >/dev/null; then
  echo "${ROUGE}[!] cloudflared introuvable. Installe-le : https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/${FIN}"
  exit 1
fi

if curl -s -o /dev/null --max-time 2 "http://localhost:$PORT"; then
  echo "${ROUGE}[!] Le port $PORT est déjà occupé — un ancien serveur tourne encore ?${FIN}"
  echo "    Arrête-le d'abord :  pkill -f serveur.py"
  exit 1
fi

# ------------- venv pour le QR (créé une seule fois) -------------
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import qrcode" 2>/dev/null; then
  echo "[i] Première utilisation : installation de l'outil QR dans .venv/ (une seule fois)…"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q qrcode
fi

# ----------------------- arrêt propre -----------------------
PID_SERVEUR=""; PID_TUNNEL=""; PID_TAIL=""
cleanup() {
  trap - EXIT INT TERM   # évite un double passage (INT puis EXIT)
  echo
  echo "[i] Arrêt du tunnel et du serveur…"
  [ -n "$PID_TAIL" ]    && kill "$PID_TAIL"    2>/dev/null || true
  [ -n "$PID_TUNNEL" ]  && kill "$PID_TUNNEL"  2>/dev/null || true
  [ -n "$PID_SERVEUR" ] && kill "$PID_SERVEUR" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "[i] Terminé. Bonne partie !"
}
trap cleanup EXIT INT TERM

# ----------------------- 1) serveur -----------------------
echo "[i] Démarrage du serveur (journal : $LOG_SERVEUR)…"
PORT="$PORT" python3 "$HERE/serveur.py" >"$LOG_SERVEUR" 2>&1 &
PID_SERVEUR=$!

for _ in $(seq 1 40); do
  curl -s -o /dev/null --max-time 1 "http://localhost:$PORT" && break
  if ! kill -0 "$PID_SERVEUR" 2>/dev/null; then
    echo "${ROUGE}[!] Le serveur n'a pas démarré. Journal :${FIN}"
    cat "$LOG_SERVEUR"
    exit 1
  fi
  sleep 0.25
done

# ----------------------- 2) tunnel -----------------------
echo "[i] Ouverture du tunnel cloudflared (journal : $LOG_TUNNEL)…"
cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG_TUNNEL" 2>&1 &
PID_TUNNEL=$!

URL=""
for _ in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_TUNNEL" | head -1 || true)
  [ -n "$URL" ] && break
  if ! kill -0 "$PID_TUNNEL" 2>/dev/null; then
    echo "${ROUGE}[!] cloudflared s'est arrêté. Journal :${FIN}"
    tail -20 "$LOG_TUNNEL"
    exit 1
  fi
  sleep 0.5
done

if [ -z "$URL" ]; then
  echo "${ROUGE}[!] Pas d'URL de tunnel après 30 s. Journal :${FIN}"
  tail -20 "$LOG_TUNNEL"
  exit 1
fi

# ----------------------- 3) infos + QR -----------------------
IP_LOCALE=$(hostname -I 2>/dev/null | awk '{print $1}')
VERSION=$(grep -oP 'VERSION = "\K[^"]+' "$HERE/serveur.py" || echo "?")
CODE_MJ=$(grep -oP 'ADMIN_CODE = "\K[^"]+' "$HERE/serveur.py" || echo "?")

clear 2>/dev/null || true
echo "${VERT}${GRAS}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║   MU/TH/UR 6000 — TERMINAL DE BORD  (v$VERSION)       ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo "${FIN}"
echo "  ${GRAS}MJ (toi)        :${FIN} http://localhost:$PORT"
[ -n "$IP_LOCALE" ] && \
echo "  ${GRAS}Joueurs (wifi)  :${FIN} http://$IP_LOCALE:$PORT"
echo "  ${GRAS}Joueurs (web)   :${FIN} ${VERT}$URL${FIN}"
echo "  ${GRAS}Code MJ         :${FIN} $CODE_MJ"
echo
echo "  ${GRAS}Scannez pour rejoindre :${FIN}"
echo
"$VENV/bin/python" - "$URL" <<'PYEOF'
import sys, qrcode
qr = qrcode.QRCode(border=1)
qr.add_data(sys.argv[1])
qr.print_ascii(invert=True)
PYEOF
echo
echo "  ${JAUNE}Ctrl+C pour tout arrêter.${FIN}  Journal du serveur ci-dessous :"
echo "  ──────────────────────────────────────────────────"

# ----------------------- 4) suivi du serveur -----------------------
tail -f "$LOG_SERVEUR" &
PID_TAIL=$!
wait "$PID_SERVEUR"
