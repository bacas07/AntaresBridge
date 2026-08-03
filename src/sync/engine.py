import asyncio
import httpx
import time
from datetime import datetime, date, timezone
from typing import Optional

from src.config import get_settings
from src.logger import logger
from src.db.antares import antares_db
from src.db.status import sync_status


def serialize_row(row: dict) -> dict:
    """Convierte tipos no JSON (datetime, date, time, Decimal) a formatos serializables.
    También normaliza strings numéricos de MySQL LONGTEXT."""
    import decimal
    from datetime import time as dt_time
    result = {}
    for key, val in row.items():
        if isinstance(val, (datetime, date)):
            result[key] = val.isoformat()
        elif isinstance(val, dt_time):
            result[key] = val.isoformat()
        elif isinstance(val, decimal.Decimal):
            result[key] = float(val) if val is not None else None
        elif isinstance(val, bytes):
            result[key] = val.decode("utf-8", errors="replace")
        elif val is None:
            result[key] = None
        else:
            result[key] = val
    return result


REQUIRED_ENV_VARS = [
    "antares_server",
    "antares_port",
    "antares_database",
    "antares_user",
    "antares_password",
    "agenda_system_url",
    "sync_api_key",
]


def validate_environment() -> bool:
    """Valida que todas las variables de entorno críticas estén presentes.

    Retorna True si todo está bien. Si falta alguna, hace log fatal y lanza excepción.
    """
    settings = get_settings()
    missing = []
    for var in REQUIRED_ENV_VARS:
        value = getattr(settings, var, None)
        if not value:
            missing.append(var)

    if missing:
        for var in missing:
            logger.error("falta_variable_entorno",
                         mensaje=f"Falta la variable de entorno: {var}",
                         variable=var,
                         sugerencia="Revisa el archivo .env y asegúrate de que todas las variables tengan valor")
        raise RuntimeError(
            f"Faltan variables de entorno críticas: {', '.join(missing)}"
        )

    logger.info("variables_entorno_ok",
                mensaje="Todas las variables de entorno requeridas están presentes",
                total=len(REQUIRED_ENV_VARS))
    return True


async def wait_for_mysql_with_backoff() -> bool:
    """Intenta conexión MySQL con backoff exponencial hasta tener éxito.

    Empieza en 5 segundos, máximo 60 segundos entre reintentos.
    Retorna True cuando la conexión es exitosa.
    """
    attempt = 0
    settings = get_settings()
    while True:
        attempt += 1
        logger.info("intento_conexion_mysql",
                    mensaje=f"Intentando conectar a MySQL ({settings.antares_server}:{settings.antares_port})",
                    intento=attempt)
        ok, latency, err = antares_db.ping()
        if ok:
            logger.info("conexion_mysql_exitosa",
                        mensaje="Conexión a MySQL establecida correctamente",
                        latencia_ms=latency,
                        intento=attempt)
            return True

        wait_s = min(5 * (2 ** (attempt - 1)), 60)
        logger.warning(
            "fallo_conexion_mysql",
            mensaje=f"No se pudo conectar a MySQL en {settings.antares_server}:{settings.antares_port}",
            error=err,
            intento=attempt,
            reintento_en_s=wait_s,
            sugerencia="Verifica que el servidor MySQL esté encendido, "
                       "que ANTARES_SERVER y ANTARES_PORT en .env sean correctos, "
                       "y que el firewall permita la conexión",
        )
        await asyncio.sleep(wait_s)


class SyncEngine:
    def __init__(self):
        self.settings = get_settings()
        self.last_sync_dt: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def last_sync(self) -> Optional[str]:
        return self.last_sync_dt.isoformat() if self.last_sync_dt else None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.settings.agenda_system_url,
                headers={
                    "X-API-Key": self.settings.sync_api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http_client

    async def _ping_loop(self):
        """Ping MySQL cada 60 segundos para mantener la conexión viva."""
        while self._running:
            await asyncio.sleep(60)
            if not self._running:
                break
            ok, latency, err = antares_db.ping()
            if ok:
                logger.debug("ping_mysql_ok",
                             mensaje="Ping a MySQL exitoso",
                             latencia_ms=latency)
            else:
                logger.warning("ping_mysql_fallo",
                               mensaje="Ping a MySQL falló, reintentando...",
                               error=err)
                ok2, latency2, err2 = antares_db.ping()
                if ok2:
                    logger.info("mysql_reconectado",
                                mensaje="MySQL reconectado exitosamente",
                                latencia_ms=latency2)
                else:
                    logger.error("mysql_reconexion_fallo",
                                 mensaje="No se pudo reconectar a MySQL",
                                 error=err2,
                                 sugerencia="Verifica que el servidor MySQL siga encendido")

    async def run(self):
        logger.info("motor_sync_iniciando",
                    mensaje="Motor de sincronización iniciando")

        # 1. Validar variables de entorno
        validate_environment()

        # 2. Health check MySQL con backoff exponencial
        await wait_for_mysql_with_backoff()

        # 3. Iniciar ping periódico
        self._running = True
        self._ping_task = asyncio.create_task(self._ping_loop())

        logger.info(
            "motor_sync_activo",
            mensaje="Motor de sincronización activo — conectado a MySQL y listo",
            intervalo_sync=f"{self.settings.sync_interval_seconds}s",
            mysql=f"{self.settings.antares_server}:{self.settings.antares_port}",
            agenda=self.settings.agenda_system_url,
        )

        while True:
            try:
                await self.sync_cycle()
            except Exception as e:
                logger.error("error_ciclo_sync",
                             mensaje="Error inesperado en el ciclo de sincronización",
                             error=str(e))
            await asyncio.sleep(self.settings.sync_interval_seconds)

    async def sync_cycle(self):
        cycle_start = time.monotonic()
        logger.info("inicio_ciclo_sync",
                    mensaje="Iniciando ciclo de sincronización",
                    ultima_sync=self.last_sync)
        client = await self._get_client()

        ops_success = 0
        ops_failed = 0

        # ── fetch_services ────────────────────────────────────────────
        try:
            services = antares_db.fetch_services()
            if services:
                logger.info("sync_servicios_enviados",
                            mensaje=f"Enviando {len(services)} servicios al sistema de agenda")
                try:
                    resp = await client.post(
                        "/api/v1/sync/services",
                        json={"services": [serialize_row(s) for s in services]},
                    )
                    sync_status.record_agenda_sync(status_code=resp.status_code)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    ops_failed += 1
                    sync_status.record_agenda_sync(status_code=0, error=str(e))
                    logger.error("sync_servicios_fallo",
                                 mensaje="Fallo al enviar servicios al sistema de agenda",
                                 error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_servicios_error",
                         mensaje="Error inesperado al sincronizar servicios",
                         error=str(e))

        # ── fetch_doctors ────────────────────────────────────────────
        try:
            doctors = antares_db.fetch_doctors()
            if doctors:
                logger.info("sync_doctores_enviados",
                            mensaje=f"Enviando {len(doctors)} doctores al sistema de agenda")
                try:
                    resp = await client.post(
                        "/api/v1/sync/doctors",
                        json={"doctors": [serialize_row(d) for d in doctors]},
                    )
                    sync_status.record_agenda_sync(status_code=resp.status_code)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    ops_failed += 1
                    sync_status.record_agenda_sync(status_code=0, error=str(e))
                    logger.error("sync_doctores_fallo",
                                 mensaje="Fallo al enviar doctores",
                                 error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_doctores_error",
                         mensaje="Error inesperado al sincronizar doctores",
                         error=str(e))

        # ── fetch_schedules ──────────────────────────────────────────
        try:
            schedules = antares_db.fetch_schedules()
            if schedules:
                logger.info("sync_horarios_enviados",
                            mensaje=f"Enviando {len(schedules)} horarios al sistema de agenda")
                try:
                    resp = await client.post(
                        "/api/v1/sync/schedules",
                        json={"schedules": [serialize_row(s) for s in schedules]},
                    )
                    sync_status.record_agenda_sync(status_code=resp.status_code)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    ops_failed += 1
                    sync_status.record_agenda_sync(status_code=0, error=str(e))
                    logger.error("sync_horarios_fallo",
                                 mensaje="Fallo al enviar horarios",
                                 error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_horarios_error",
                         mensaje="Error inesperado al sincronizar horarios",
                         error=str(e))

        # ── fetch_unavailability ──────────────────────────────────────
        try:
            unavailability = antares_db.fetch_unavailability()
            if unavailability:
                logger.info("sync_no_disponibilidad_enviados",
                            mensaje=f"Enviando {len(unavailability)} días no disponibles")
                try:
                    resp = await client.post(
                        "/api/v1/sync/unavailability",
                        json={"unavailability": [serialize_row(u) for u in unavailability]},
                    )
                    sync_status.record_agenda_sync(status_code=resp.status_code)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    ops_failed += 1
                    sync_status.record_agenda_sync(status_code=0, error=str(e))
                    logger.error("sync_no_disponibilidad_fallo",
                                 mensaje="Fallo al enviar días no disponibles",
                                 error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_no_disponibilidad_error",
                         mensaje="Error inesperado al sincronizar no disponibilidad",
                         error=str(e))

        # ── fetch_plan_limits ────────────────────────────────────────
        try:
            plan_limits = antares_db.fetch_plan_limits()
            if plan_limits:
                logger.info("sync_limites_plan_enviados",
                            mensaje=f"Enviando {len(plan_limits)} límites de plan")
                try:
                    resp = await client.post(
                        "/api/v1/sync/plan-limits",
                        json={"plan_limits": [serialize_row(p) for p in plan_limits]},
                    )
                    sync_status.record_agenda_sync(status_code=resp.status_code)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    ops_failed += 1
                    sync_status.record_agenda_sync(status_code=0, error=str(e))
                    logger.error("sync_limites_plan_fallo",
                                 mensaje="Fallo al enviar límites de plan",
                                 error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_limites_plan_error",
                         mensaje="Error inesperado al sincronizar límites de plan",
                         error=str(e))

        # ── fetch_patients (antes de citas por FK) ───────────────────
        try:
            patients = antares_db.fetch_patients(self.last_sync_dt)
            if patients:
                logger.info("sync_pacientes_enviados",
                            mensaje=f"Enviando {len(patients)} pacientes al sistema de agenda")
                try:
                    resp = await client.post(
                        "/api/v1/sync/patients",
                        json={"patients": [serialize_row(p) for p in patients]},
                    )
                    sync_status.record_agenda_sync(status_code=resp.status_code)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    ops_failed += 1
                    sync_status.record_agenda_sync(status_code=0, error=str(e))
                    logger.error("sync_pacientes_fallo",
                                 mensaje="Fallo al enviar pacientes",
                                 error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_pacientes_error",
                         mensaje="Error inesperado al sincronizar pacientes",
                         error=str(e))

        # ── fetch_appointments ───────────────────────────────────────
        try:
            appointments = antares_db.fetch_new_appointments(self.last_sync_dt)
            if appointments:
                logger.info("sync_citas_enviando",
                            mensaje=f"Enviando {len(appointments)} citas al sistema de agenda")
                for appt in appointments:
                    try:
                        resp = await client.post(
                            "/api/v1/sync/appointments",
                            json={"action": "upsert", "data": serialize_row(appt)},
                        )
                        sync_status.record_agenda_sync(status_code=resp.status_code)
                        resp.raise_for_status()
                    except httpx.HTTPError as e:
                        ops_failed += 1
                        sync_status.record_agenda_sync(status_code=0, error=str(e))
                        logger.error("sync_cita_fallo",
                                     mensaje="Fallo al enviar cita",
                                     id_cita=appt.get("id"),
                                     error=str(e))
            ops_success += 1
        except Exception as e:
            ops_failed += 1
            logger.error("sync_citas_error",
                         mensaje="Error inesperado al sincronizar citas",
                         error=str(e))

        # ── PUSH INVERSO: citas desde agenda → MySQL ────────────────
        push_success = 0
        push_failed = 0
        try:
            resp = await client.get("/api/v1/sync/pending-updates")
            sync_status.record_agenda_sync(status_code=resp.status_code)
            if resp.status_code == 200:
                updates = resp.json()
                appointments_to_push = updates.get("appointments", [])
                if appointments_to_push:
                    logger.info("sync_push_inverso_pendientes",
                                mensaje=f"Recibidas {len(appointments_to_push)} citas para insertar en MySQL")
                    pushed_ids = []
                    for appt in appointments_to_push:
                        if appt.get("source") in ("whatsapp", "system"):
                            try:
                                antares_db.insert_cit(appt)
                                pushed_ids.append(appt["id"])
                                push_success += 1
                            except Exception as e:
                                push_failed += 1
                                logger.error("sync_push_inverso_fallo",
                                             mensaje="Fallo al insertar cita en MySQL",
                                             id_cita=appt.get("id"),
                                             error=str(e))
                    if pushed_ids:
                        try:
                            resp2 = await client.post(
                                "/api/v1/sync/push-result",
                                json={"ids": pushed_ids},
                            )
                            sync_status.record_agenda_sync(status_code=resp2.status_code)
                        except httpx.HTTPError as e:
                            logger.error("sync_push_resultado_fallo",
                                         mensaje="Fallo al notificar resultado del push inverso",
                                         error=str(e))
            else:
                ops_failed += 1
        except httpx.HTTPError as e:
            ops_failed += 1
            sync_status.record_agenda_sync(status_code=0, error=str(e))
            logger.error("sync_push_inverso_error_http",
                         mensaje="Error HTTP al obtener citas pendientes",
                         error=str(e))
        except Exception as e:
            ops_failed += 1
            logger.error("sync_push_inverso_error",
                         mensaje="Error inesperado en push inverso",
                         error=str(e))

        sync_status.record_operation(
            "push_to_antares",
            success=(push_failed == 0),
            records_processed=push_success,
            error_message=f"{push_failed} fallos" if push_failed else "",
        )

        self.last_sync_dt = datetime.now(timezone.utc)
        duration_s = time.monotonic() - cycle_start

        sync_status.record_cycle_complete(
            duration_s=duration_s,
            failed_ops=ops_failed,
            success_ops=ops_success,
        )

        logger.info(
            "ciclo_sync_completado",
            mensaje="Ciclo de sincronización completado",
            duracion_s=round(duration_s, 2),
            operaciones_exitosas=ops_success,
            operaciones_fallidas=ops_failed,
            push_exitosos=push_success,
            push_fallidos=push_failed,
        )

    async def close(self):
        self._running = False
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
