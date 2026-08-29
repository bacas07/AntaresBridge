import asyncio
import os
import sys
import traceback

import uvicorn
from pydantic import ValidationError

from src.config import get_settings
from src.logger import setup_logging, logger
from src.sync.engine import SyncEngine
from src.dashboard import create_dashboard_app


def _banner(settings):
    print()
    print("=" * 56)
    print("  Antares Bridge — Puente de Sincronización")
    print("=" * 56)
    print(f"  Base datos  : {settings.antares_server}:{settings.antares_port}/{settings.antares_database}")
    print(f"  Usuario     : {settings.antares_user}")
    print(f"  Agenda      : {settings.agenda_system_url}")
    print(f"  Sync cada   : {settings.sync_interval_seconds}s")
    print(f"  Lookback    : {settings.sync_lookback_hours}h")
    print(f"  Dashboard   : http://localhost:8001")
    print("=" * 56)
    print()


async def run_sync_engine():
    engine = SyncEngine()
    await engine.run()


async def run_dashboard():
    app = create_dashboard_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    logger.info("dashboard_iniciando",
                mensaje="Iniciando servidor de monitoreo",
                puerto=8001)
    await server.serve()


async def main():
    settings = get_settings()
    setup_logging(settings.log_level)

    _banner(settings)

    logger.info("bridge_iniciando",
                mensaje="Antares Bridge iniciando",
                mysql=f"{settings.antares_server}:{settings.antares_port}",
                agenda=settings.agenda_system_url)

    await asyncio.gather(
        run_sync_engine(),
        run_dashboard(),
    )


def _is_interactive() -> bool:
    """True si hay una consola real (uso manual).

    Bajo Task Scheduler/SYSTEM no hay tty: devuelve False para que los
    errores fatales salgan con codigo != 0 y el scheduler reinicie el proceso.
    """
    flag = os.environ.get("BRIDGE_NONINTERACTIVE", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return False
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _pause():
    if _is_interactive():
        try:
            input("Presiona Enter para salir...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ValidationError as e:
        print()
        print("ERROR: El archivo .env tiene valores inválidos.")
        print(f"  Detalle: {e}")
        print("  Revisa que los números sean números (ej: ANTARES_PORT=3306)")
        print()
        logger.error("error_config_env",
                     mensaje="El archivo .env tiene valores inválidos",
                     detalle=str(e))
        _pause()
        sys.exit(1)
    except OSError as e:
        print()
        print(f"ERROR: No se pudo iniciar el servidor.")
        print(f"  {e}")
        if "address already in use" in str(e).lower() or "10048" in str(e):
            print("  El puerto 8001 ya está en uso.")
            print("  Cierra la otra instancia o cambia el puerto.")
        print()
        logger.error("error_fatal_arranque",
                     mensaje="Error fatal al iniciar el servidor",
                     error=str(e))
        _pause()
        sys.exit(1)
    except RuntimeError as e:
        print()
        print(f"ERROR DE CONFIGURACIÓN: {e}")
        print("  Revisa que todas las variables en .env tengan valor.")
        print()
        logger.error("error_config_faltante",
                     mensaje="Faltan variables de entorno críticas",
                     error=str(e))
        _pause()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAntares Bridge detenido por el usuario.")
    except Exception as e:
        print()
        print(f"ERROR INESPERADO: {e}")
        print()
        traceback.print_exc()
        print()
        logger.error("error_fatal_inesperado",
                     mensaje="Error inesperado en el bridge",
                     error=str(e))
        _pause()
        sys.exit(1)
