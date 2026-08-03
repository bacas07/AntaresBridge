#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "========================================"
echo "  Antares Bridge"
echo "========================================"
echo ""

if [ ! -f ".env" ]; then
    echo "ERROR: Archivo .env no encontrado."
    echo "  Copialo: cp .env.example .env"
    echo "  Luego editalo con tus credenciales."
    exit 1
fi

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        ver=$("$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null && echo "ok")
        if [ "$ver" = "ok" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: No se encontro Python 3.8+."
    echo "  Instala Python 3.8 o superior."
    exit 1
fi

echo "[OK] Python: $($PYTHON --version 2>&1)"

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    $PYTHON -m venv venv || {
        echo "ERROR: No se pudo crear el entorno virtual."
        exit 1
    }
fi

source venv/bin/activate

echo "Instalando dependencias..."
pip install -r requirements.txt 2>/dev/null || {
    echo "  Online fallo, probando offline desde wheels/..."
    pip install --no-index --find-links wheels/ -r requirements.txt || {
        echo ""
        echo "ERROR: No se pudieron instalar las dependencias."
        echo "  Verifica que tengas conexion a internet o la carpeta wheels/"
        exit 1
    }
}

echo ""
echo "Dashboard: http://localhost:8001"
echo "Ctrl+C para detener"
echo ""

$PYTHON -m src.main
