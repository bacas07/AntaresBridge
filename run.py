import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"


def _is_venv():
    return sys.prefix != sys.base_prefix


def _venv_python():
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _bootstrap():
    print("=== Antares Bridge — Configuración inicial ===\n")

    if not VENV.exists():
        print("Creando entorno virtual...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    python = str(_venv_python())
    print("Instalando dependencias...")
    subprocess.check_call(
        [python, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    )

    print("\nIniciando...")
    os.execv(python, [python, __file__])


def _start():
    try:
        env_file = ROOT / ".env"
        if not env_file.exists():
            print("ERROR: Archivo .env no encontrado.")
            print(f"  Cópialo: cp {ROOT / '.env.example'} {env_file}")
            print("  Luego edítalo con tus credenciales.")
            input("\nPresiona Enter para salir...")
            sys.exit(1)

        content = env_file.read_text()
        if "host.docker.internal" in content or "agenda-system-api-1" in content:
            print("ADVERTENCIA: .env contiene hostnames de Docker.")
            print("  Cambia ANTARES_SERVER y AGENDA_SYSTEM_URL en .env")
            print("  por los valores reales de la máquina on-premise.\n")

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
