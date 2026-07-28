#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "========================================"
echo "  Antares Bridge"
echo "========================================"
echo ""

[ -f .env ] || { echo "ERROR: .env no encontrado. cp .env.example .env"; exit 1; }

python3 -m venv venv 2>/dev/null || true
source venv/bin/activate

pip install -r requirements.txt 2>/dev/null || {
    echo "Online fallo, usando wheels offline..."
    pip install --no-index --find-links wheels/ -r requirements.txt
}

echo ""
echo "Dashboard: http://localhost:8001"
echo "Ctrl+C para detener"
echo ""

python -m src.main
