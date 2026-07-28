#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Antares Bridge${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# ── Detectar Python ────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python py; do
    if command -v "$cmd" &> /dev/null; then
        ver=$("$cmd" --version 2>&1)
        case "$ver" in
            "Python 3"*) PYTHON="$cmd"; break ;;
            *) ;;
        esac
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}[ERROR] No se encontró Python 3.${NC}"
    echo ""
    echo "  Asegúrate de que Python 3.8+ esté instalado y en el PATH."
    echo "  Descarga: https://www.python.org/downloads/"
    echo ""
    read -r -p "Presiona Enter para salir..."
    exit 1
fi
echo -e "${GREEN}[OK] Python: $($PYTHON --version 2>&1)${NC}"

# ── Crear venv si no existe ────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo -n "Creando entorno virtual... "
    if $PYTHON -m venv venv 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FALLÓ${NC}"
        echo ""
        echo -e "${RED}No se pudo crear el venv. Verifica que:${NC}"
        echo "  - El módulo 'venv' esté instalado"
        echo "  - Tengas permisos de escritura en este directorio"
        echo ""
        read -r -p "Presiona Enter para salir..."
        exit 1
    fi
else
    echo -e "${GREEN}[OK] Entorno virtual existente.${NC}"
fi

# ── Activar venv ───────────────────────────────────────────────────
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo -e "${RED}[ERROR] No se encontró activate en el venv.${NC}"
    read -r -p "Presiona Enter para salir..."
    exit 1
fi

# ── Verificar .env ─────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[AVISO] Archivo .env no encontrado.${NC}"
    cp .env.example .env
    echo "  Se creó desde .env.example."
    echo ""
    echo -e "${RED}  ¡EDITA .env antes de continuar!${NC}"
    echo "  Debes configurar al menos:"
    echo "    ANTARES_SERVER  = IP/hostname del MySQL"
    echo "    AGENDA_SYSTEM_URL = URL del sistema de agenda"
    echo ""
    read -r -p "Presiona Enter para salir..."
    exit 1
fi

# ── Instalar dependencias ──────────────────────────────────────────
echo -n "Instalando dependencias... "
if pip install --quiet -r requirements.txt 2>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FALLÓ${NC}"
    echo ""
    echo "  Intenta manualmente:"
    echo "    source venv/bin/activate"
    echo "    pip install -r requirements.txt"
    echo ""
    read -r -p "Presiona Enter para salir..."
    exit 1
fi

# ── Verificar credenciales ─────────────────────────────────────────
if grep -q "host.docker.internal" .env 2>/dev/null; then
    echo -e "${YELLOW}[AVISO] .env contiene hostnames Docker (host.docker.internal).${NC}"
    echo "  Si estás ejecutando sin Docker, actualiza ANTARES_SERVER y AGENDA_SYSTEM_URL."
    echo ""
fi

echo ""
echo -e "${CYAN}Iniciando Antares Bridge...${NC}"
echo "  Dashboard: http://localhost:8001"
echo "  Ctrl+C para detener"
echo ""

python -m src.main

echo ""
echo -e "${YELLOW}El proceso terminó.${NC}"
read -r -p "Presiona Enter para cerrar..."
