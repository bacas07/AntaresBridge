"""Estado interno del sync engine — consultable desde el dashboard.

Un dict simple por operación que registra:
- nombre de la operación
- timestamp del último intento (UTC ISO)
- si fue exitosa o fallida
- cantidad de registros procesados
- mensaje de error si falló
"""

from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class OperationStatus:
    name: str
    last_attempt: Optional[str] = None
    success: bool = False
    records_processed: int = 0
    error_message: str = ""
    duration_ms: int = 0


class SyncStatus:
    """Estado interno del sync engine."""

    def __init__(self):
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.mysql_connected: bool = False
        self.mysql_last_ping: Optional[str] = None
        self.mysql_ping_latency_ms: int = 0
        self.mysql_last_error: str = ""
        self.agenda_last_sync: Optional[str] = None
        self.agenda_last_status_code: int = 0
        self.agenda_last_error: str = ""

        self.operations: dict[str, OperationStatus] = {}
        self._cycle_history: list[dict] = []

        # Inicializar operaciones conocidas
        for op_name in (
            "fetch_services",
            "fetch_doctors",
            "fetch_schedules",
            "fetch_unavailability",
            "fetch_plan_limits",
            "fetch_patients",
            "fetch_appointments",
            "push_to_antares",
        ):
            self.operations[op_name] = OperationStatus(name=op_name)

    def record_operation(
        self,
        op_name: str,
        success: bool,
        records_processed: int = 0,
        error_message: str = "",
        duration_ms: int = 0,
    ):
        """Registra el resultado de una operación de sync."""
        if op_name not in self.operations:
            self.operations[op_name] = OperationStatus(name=op_name)
        self.operations[op_name] = OperationStatus(
            name=op_name,
            last_attempt=datetime.now(timezone.utc).isoformat(),
            success=success,
            records_processed=records_processed,
            error_message=error_message,
            duration_ms=duration_ms,
        )

    def record_mysql_ping(self, success: bool, latency_ms: int = 0, error: str = ""):
        """Registra el resultado de un ping a SQL Server."""
        self.mysql_last_ping = datetime.now(timezone.utc).isoformat()
        self.mysql_connected = success
        self.mysql_ping_latency_ms = latency_ms
        if error:
            self.mysql_last_error = error

    def record_agenda_sync(self, status_code: int, error: str = ""):
        """Registra el resultado del último POST de sync a agenda-system."""
        self.agenda_last_sync = datetime.now(timezone.utc).isoformat()
        self.agenda_last_status_code = status_code
        self.agenda_last_error = error

    def record_cycle_complete(self, duration_s: float, failed_ops: int, success_ops: int):
        """Registra un ciclo completo en el historial (máx 20)."""
        self._cycle_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_s": round(duration_s, 2),
            "operations_failed": failed_ops,
            "operations_success": success_ops,
        })
        if len(self._cycle_history) > 20:
            self._cycle_history = self._cycle_history[-20:]

    def to_dict(self) -> dict:
        """Convierte el estado completo a dict para el dashboard JSON."""
        return {
            "service": {
                "started_at": self.started_at,
                "uptime_s": int(
                    (datetime.now(timezone.utc) - datetime.fromisoformat(self.started_at)).total_seconds()
                ),
            },
            "mysql": {
                "connected": self.mysql_connected,
                "last_ping": self.mysql_last_ping,
                "ping_latency_ms": self.mysql_ping_latency_ms,
                "last_error": self.mysql_last_error,
            },
            "agenda": {
                "last_sync": self.agenda_last_sync,
                "last_status_code": self.agenda_last_status_code,
                "last_error": self.agenda_last_error,
            },
            "operations": {k: asdict(v) for k, v in self.operations.items()},
            "cycle_history": self._cycle_history,
        }


# Singleton accesible desde cualquier módulo
sync_status = SyncStatus()
