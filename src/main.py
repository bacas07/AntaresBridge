import asyncio
import uvicorn
from src.config import get_settings
from src.logger import setup_logging, logger
from src.sync.engine import SyncEngine
from src.dashboard import create_dashboard_app


async def run_sync_engine():
    engine = SyncEngine()
    await engine.run()


async def run_dashboard():
    """Corre el servidor web del dashboard en puerto 8001."""
    app = create_dashboard_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    logger.info("dashboard_server_starting", port=8001)
    await server.serve()


async def main():
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info(
        "antares_bridge_starting",
        interval=settings.sync_interval_seconds,
        antares_server=settings.antares_server,
        agenda_url=settings.agenda_system_url,
        dashboard_port=8001,
    )

    await asyncio.gather(
        run_sync_engine(),
        run_dashboard(),
    )


if __name__ == "__main__":
    asyncio.run(main())
