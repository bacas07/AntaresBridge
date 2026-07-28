#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "==> Creando entorno virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f ".env" ]; then
    echo "==> ERROR: Archivo .env no encontrado."
    echo "    Cópialo desde .env.example y edítalo con tus credenciales:"
    echo "    cp .env.example .env"
    exit 1
fi

echo "==> Instalando dependencias..."
pip install --quiet -r requirements.txt

echo "==> Iniciando Antares Bridge..."
python -m src.main
