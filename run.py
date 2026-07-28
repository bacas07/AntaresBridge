import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
WHEELS = ROOT / "wheels"
REQ = ROOT / "requirements.txt"


def _is_venv():
    return sys.prefix != sys.base_prefix


def _venv_python():
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _has_wheels():
    return WHEELS.exists() and any(WHEELS.glob("*.whl"))


def _bootstrap():
    print("=== Antares Bridge — Configuracion inicial ===\n")

    if not VENV.exists():
        print("Creando entorno virtual...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    python = str(_venv_python())

    print("Instalando dependencias...")
    try:
        subprocess.check_call([python, "-m", "pip", "install", "-r", str(REQ)])
    except subprocess.CalledProcessError:
        if _has_wheels():
            print("(online fallo, usando carpeta wheels offline...)")
            subprocess.check_call([
                python, "-m", "pip", "install",
                "--no-index", "--find-links", str(WHEELS),
                "-r", str(REQ),
            ])
        else:
            print("\nERROR: No se pudo instalar desde internet.")
            print("Si la maquina no tiene conexion, copia la carpeta 'wheels/'")
            print("junto con el proyecto y vuelve a intentar.")
            input("\nPresiona Enter para salir...")
            sys.exit(1)

    print("\nIniciando...")
    os.execv(python, [python, __file__])


def _start():
    try:
        env_file = ROOT / ".env"
        if not env_file.exists():
            print("ERROR: Archivo .env no encontrado.")
            print(f"  Copia .env.example como .env y editalo:")
            print(f"  copy .env.example .env")
            input("\nPresiona Enter para salir...")
            sys.exit(1)

        content = env_file.read_text()
        if "host.docker.internal" in content or "agenda-system-api-1" in content:
            print("ADVERTENCIA: .env contiene hostnames de Docker.")
            print("  Cambia ANTARES_SERVER y AGENDA_SYSTEM_URL en .env")
            print("  por los valores reales de la maquina on-premise.\n")

        from src.main import main as app_main
        import asyncio

        print("Dashboard: http://localhost:8001")
        print("Ctrl+C para detener\n")
        asyncio.run(app_main())

    except KeyboardInterrupt:
        print("\nDetenido.")
    except Exception as e:
        print(f"\nERROR: {e}\n")
        traceback.print_exc()
        input("\nPresiona Enter para salir...")
        sys.exit(1)


if __name__ == "__main__":
    if _is_venv():
        _start()
    else:
        _bootstrap()
