#!/usr/bin/env bash
# Equivalente do iniciar_aplicacao_schulz.bat para Linux e macOS (mesmos 4 passos).
# Uso: ./iniciar_aplicacao_schulz.sh [--lan]      Porta: SCHULZ_PORTA (padrão 5000).
set -euo pipefail
cd "$(dirname "$0")"
PORTA="${SCHULZ_PORTA:-5000}"; export SCHULZ_PORTA="$PORTA"
URL="http://127.0.0.1:${PORTA}/"
VENV_PY=".venv/bin/python"

echo "[1/4] Verificando o Python 3.10 ou superior no PATH..."
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || { echo "[ERRO] Python 3.10+ não encontrado no PATH (https://www.python.org/downloads/)."; exit 1; }
echo "       OK: $($PY --version)"

echo "[2/4] Preparando o ambiente virtual (.venv)..."
[ -x "$VENV_PY" ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/4] Instalando as bibliotecas do requirements.txt..."
if ! cmp -s requirements.txt .venv/requirements.instalado || ! "$VENV_PY" -c 'import flask, openpyxl, fpdf, segno' 2>/dev/null; then
  "$VENV_PY" -m pip install --disable-pip-version-check --quiet -r requirements.txt
  cp requirements.txt .venv/requirements.instalado
fi

saude() { "$VENV_PY" -c "import urllib.request as u; u.build_opener(u.ProxyHandler({})).open('${URL}api/saude', timeout=1)" 2>/dev/null; }

echo "[4/4] Iniciando a API e abrindo a interface..."
if ! saude; then
  "$VENV_PY" app.py "$@" &
  API=$!
  trap 'kill $API 2>/dev/null' INT TERM
  for _ in $(seq 40); do saude && break; sleep 1; done
  saude || { echo "[ERRO] A API não respondeu em ${URL}."; kill $API 2>/dev/null; exit 1; }
fi
if command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null; then open "$URL" || true; fi
echo "Pronto: ${URL}  (Ctrl+C encerra a API)"
wait "${API:-}" 2>/dev/null || true
