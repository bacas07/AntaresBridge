"""Capa de acceso a datos MySQL 8.0 (datosipspymr) vía PyMySQL."""

import pymysql
import time
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from typing import Generator, Optional

from src.config import get_settings
from src.logger import logger
from src.db.status import sync_status


# ── helpers de conversión ──────────────────────────────────────────────

def _parse_fechacita(fechacita_str: str) -> Optional[str]:
    """Convierte YYYYMMDDHHMM → ISO datetime string."""
    if not fechacita_str or len(str(fechacita_str)) < 12:
        return None
    s = str(fechacita_str).strip()
    try:
        y, m, d, hh, mi = int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12])
        return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mi:02d}:00"
    except (ValueError, IndexError):
        return None


def _to_fechacita(dt) -> str:
    """Convierte datetime/string ISO → YYYYMMDDHHMM."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return dt
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y%m%d%H%M")
    return str(dt)


def _str_val(v, default=""):
    """Normaliza: None → default, strip."""
    if v is None:
        return default
    return str(v).strip()


def _str_int(v, default=0) -> int:
    """Convierte a int."""
    try:
        return int(_str_val(v, str(default)))
    except (ValueError, TypeError):
        return default


def _datetime_iso(v) -> Optional[str]:
    """Convierte datetime/date/timestamp a string ISO, o None."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    return s or None


# ── cursor que devuelve dicts (pymysql devuelve tuple, no dict) ────────

def _rows_to_dicts(cursor):
    """Convierte todas las filas del cursor a lista de dicts."""
    if not cursor.description:
        return []
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _row_to_dict(cursor):
    """Convierte una fila del cursor a dict."""
    if not cursor.description:
        return None
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


# ── conexión ODBC ─────────────────────────────────────────────────────


class AntaresDB:
    def __init__(self):
        settings = get_settings()
        self.host = settings.antares_server
        self.port = settings.antares_port
        self.database = settings.antares_database
        self.user = settings.antares_user
        self.password = settings.antares_password

    @contextmanager
    def get_connection(self) -> Generator:
        conn = None
        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                autocommit=False,
                connect_timeout=30,
            )
        except pymysql.MySQLError as e:
            # Solo errores de CONEXIÓN (no errores de datos de una query).
            logger.error("error_conexion_mysql",
                         mensaje=f"Error al conectar a MySQL en {self.host}:{self.port}/{self.database}",
                         error=str(e),
                         sugerencia="Verifica que el servidor MySQL esté activo, "
                                    "que ANTARES_SERVER y ANTARES_PORT en .env sean correctos, "
                                    "y que el firewall permita la conexión")
            sync_status.record_mysql_ping(success=False, error=str(e))
            raise
        try:
            yield conn
        finally:
            conn.close()

    def ping(self) -> tuple[bool, int, str]:
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            latency_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_mysql_ping(success=True, latency_ms=latency_ms)
            return True, latency_ms, ""
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_mysql_ping(success=False, latency_ms=latency_ms, error=str(e))
            return False, latency_ms, str(e)

    # ── SERVICIOS ──────────────────────────────────────────────────────

    def fetch_services(self) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT
                        codigocups AS code,
                        codigocups AS service_id,
                        descripcioncups AS name,
                        30 AS duration,
                        'Activo' AS status
                    FROM codigossoat
                    WHERE codigocups IN (
                        '890275','890375','890283','890383','890245','890345',
                        '890247','890347','890242','890342','890269','890369',
                        '890281','890381','890285','890385','890229','890329',
                        '890206','890306','890272','890372','890208','890297',
                        '890397','891410','881202','895100','940701','930102',
                        '890279','895101','891402','890379','890243','890328','893805'
                    )
                    ORDER BY codigocups
                """)
                rows = _rows_to_dicts(cursor)
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_services", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_servicios_ok",
                        mensaje=f"Obtenidos {len(rows)} servicios CUPS desde MySQL",
                        total=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_services", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_servicios_error",
                         mensaje="Error al obtener servicios CUPS desde MySQL",
                         error=str(e))
            return []

    # ── DOCTORES ────────────────────────────────────────────────────────

    DOCTOR_NAMES = {
        "10409903": ("Dra. Coromoto Villalobos Danielline", "Gastroenterología Pediátrica"),
        "1118814810": ("Dra. Cindy Arregoces Álvarez", "Endocrinología Pediátrica"),
        "1118839778": ("Dra. Karen Dayana Suárez Maestre", "Neumología Pediátrica"),
        "111885355": ("Dra. María José Muñoz Zabaleta", "Neuropsicología"),
        "112447319": ("Dr. Pediatría (112447319)", "Pediatría"),
        "112761710": ("Dr. Carlos Tafur", "Neurología Pediátrica"),
        "1127961710": ("Dr. Carlos Tafur", "Neurología Pediátrica"),
        "1192783553": ("Dr. Neuropsicología (1192783553)", "Neuropsicología"),
        "17953649": ("Dr. Jorge Luis Pérez Molina", "Pediatría"),
        "27600964": ("Dr. Pediatría (27600964)", "Pediatría"),
        "36722127": ("Dra. Yajaira Ureche", "Psiquiatría Pediátrica"),
        "40924020": ("Dra. Karen Rodríguez Gómez", "Nutrición"),
        "40940131": ("Dra. Mayolis Mengual Armenta", "Psicología"),
        "53815": ("Dr. Herman Belisario", "Neurología Pediátrica"),
        "56081106": ("Dra. Yael Avila San", "Dermatología Pediátrica"),
        "6524194": ("Dra. Maritza de Jesús Malave Sáez", "Gastroenterología Pediátrica"),
        "6748712": ("Dra. María Navarro", "Nefrología Pediátrica"),
        "755042": ("Dr. José Mora", "Ortopedia Pediátrica"),
        "7570754": ("Dr. Antonio Amaris Ariza", "Neuropsicología"),
        "77105170": ("Dr. Pediatría (77105170)", "Pediatría"),
        "788196": ("Dr. Dermatología (788196)", "Dermatología"),
        "7938518": ("Dr. Pediatría (7938518)", "Pediatría"),
        "84088006": ("Dr. Gustavo Mendoza", "Cardiología Pediátrica"),
        "84089502": ("Dr. Dainer Freile", "Neumología Pediátrica"),
        "91430553": ("Dr. Psiquiatría (91430553)", "Psiquiatría"),
    }

    # Doctores que NO atienden sábados aunque citas_conf traiga trabaja6=-1
    # (verificado vs roster IPS mensual + 0 citas en sábado en 12 meses).
    # Belisario (53815) y gastro (6524194) SÍ atienden sábados: no tocar.
    SATURDAY_OFF_DOCTORS = {"17953649"}

    # idespecialidad de Antares (tabla especialidades) por especialidad.
    SPECIALTY_CODES = {
        "Gastroenterología Pediátrica": "114",
        "Endocrinología Pediátrica": "117",
        "Pediatría": "107",
        "Neuropsicología": "111",
        "Neurología Pediátrica": "106",
        "Psiquiatría Pediátrica": "116",
        "Nutrición": "120",
        "Psicología": "121",
        "Dermatología Pediátrica": "112",
        "Nefrología Pediátrica": "118",
        "Ortopedia Pediátrica": "108",
        "Cardiología Pediátrica": "113",
        "Neumología Pediátrica": "119",
        "Dermatología": "112",
        "Psiquiatría": "122",
    }

    def fetch_doctors(self) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT c.idmedico AS id,
                        (SELECT MAX(LEFT(c2.fechacita, 8))
                           FROM citas c2
                          WHERE c2.idmedico = c.idmedico) AS last_activity
                    FROM citas_conf c
                    WHERE c.activo = '-1'
                      AND c.idmedico IS NOT NULL
                      AND c.idmedico != ''
                """)
                rows = _rows_to_dicts(cursor)

            doctors = []
            for r in rows:
                doc_id = _str_val(r["id"])
                name, specialty = self.DOCTOR_NAMES.get(doc_id, (f"Dr. {doc_id}", ""))
                # Última cita en Antares (YYYYMMDD) o None si jamás atendió.
                # La agenda lo usa como regla antifantasma (actividad ≤120 días).
                last_activity = _str_val(r.get("last_activity", ""))
                if len(last_activity) == 8 and last_activity.isdigit():
                    last_activity = f"{last_activity[:4]}-{last_activity[4:6]}-{last_activity[6:]}"
                else:
                    last_activity = None
                doctors.append({
                    "id": doc_id,
                    "name": name,
                    "specialty_id": self.SPECIALTY_CODES.get(specialty, ""),
                    "specialty_name": specialty,
                    "phone": "",
                    "email": "",
                    "status": "ACTIVO",
                    "agenda_web": True,
                    "last_appointment_at": last_activity,
                })

            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_doctors", success=True, records_processed=len(doctors), duration_ms=duration_ms)
            logger.info("fetch_doctores_ok",
                        mensaje=f"Obtenidos {len(doctors)} doctores desde citas_conf",
                        total=len(doctors))
            return doctors
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_doctors", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_doctores_error",
                         mensaje="Error al obtener doctores",
                         error=str(e))
            return []

    # ── HORARIOS ────────────────────────────────────────────────────────

    def fetch_schedules(self) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        idmedico AS doctor_id,
                        duracioncita AS slot_duration,
                        activo,
                        trabaja0, trabaja1, trabaja2, trabaja3, trabaja4, trabaja5, trabaja6,
                        hiniciom0, hfinalm0, hiniciot0, hfinalt0,
                        hiniciom1, hfinalm1, hiniciot1, hfinalt1,
                        hiniciom2, hfinalm2, hiniciot2, hfinalt2,
                        hiniciom3, hfinalm3, hiniciot3, hfinalt3,
                        hiniciom4, hfinalm4, hiniciot4, hfinalt4,
                        hiniciom5, hfinalm5, hiniciot5, hfinalt5,
                        hiniciom6, hfinalm6, hiniciot6, hfinalt6
                    FROM citas_conf
                    WHERE activo = '-1'
                      AND idagenda = 0
                      AND idmedico IS NOT NULL
                      AND idmedico != ''
                """)
                rows = _rows_to_dicts(cursor)

            schedules = []
            for r in rows:
                doctor_id = _str_val(r["doctor_id"])
                slot_dur = _str_int(r["slot_duration"], 20)
                is_active = _str_val(r["activo"]) == "-1"

                for day_idx in range(7):
                    trabaja = _str_val(r.get(f"trabaja{day_idx}", "0"))
                    if trabaja != "-1":
                        continue
                    # Sábado desactivado por doctor (trabaja6 obsoleto en Antares).
                    if day_idx == 6 and doctor_id in self.SATURDAY_OFF_DOCTORS:
                        continue

                    # Antares usa 0=domingo; el API/agenda usa 0=lunes.
                    day_of_week = (day_idx + 6) % 7

                    h_ini_m = _extract_time(r.get(f"hiniciom{day_idx}"))
                    h_fin_m = _extract_time(r.get(f"hfinalm{day_idx}"))
                    if h_ini_m and h_fin_m:
                        schedules.append({
                            "doctor_id": doctor_id,
                            "day_of_week": day_of_week,
                            "start_time": h_ini_m,
                            "end_time": h_fin_m,
                            "slot_duration": slot_dur,
                            "is_active": is_active,
                        })

                    h_ini_t = _extract_time(r.get(f"hiniciot{day_idx}"))
                    h_fin_t = _extract_time(r.get(f"hfinalt{day_idx}"))
                    if h_ini_t and h_fin_t:
                        schedules.append({
                            "doctor_id": doctor_id,
                            "day_of_week": day_of_week,
                            "start_time": h_ini_t,
                            "end_time": h_fin_t,
                            "slot_duration": slot_dur,
                            "is_active": is_active,
                        })

            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_schedules", success=True, records_processed=len(schedules), duration_ms=duration_ms)
            logger.info("fetch_horarios_ok",
                        mensaje=f"Obtenidos {len(schedules)} horarios desde {len(rows)} configs",
                        total_horarios=len(schedules),
                        total_configs=len(rows))
            return schedules
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_schedules", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_horarios_error",
                         mensaje="Error al obtener horarios",
                         error=str(e))
            return []

    # ── CITAS ───────────────────────────────────────────────────────────

    def fetch_new_appointments(self, last_sync: Optional[datetime] = None) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT
                        c.idcita AS id,
                        c.fechacita,
                        c.fechasolicitud,
                        c.idmedico AS doctor_id,
                        c.numeropaciente AS patient_id,
                        c.IdServicio AS service_code,
                        c.estado,
                        c.cumplida AS is_fulfilled,
                        c.entidad,
                        c.admisionno,
                        c.observaciones AS observations,
                        c.fechamodificado AS updated_at,
                        c.creadopor AS created_by,
                        c.cancelada,
                        c.canceladapor,
                        c.fechacancelacion,
                        c.MotivoCancela,
                        c.bloqueado,
                        c.prioritaria,
                        c.turnos,
                        (SELECT pxc.cups FROM pxcita pxc
                          WHERE pxc.idcita = c.idcita
                          ORDER BY pxc.registrono
                          LIMIT 1) AS cups
                    FROM citas c
                """
                params = []

                if last_sync:
                    since_str = last_sync.strftime("%Y%m%d%H%M")
                    query += " WHERE c.fechacita > %s"
                    params.append(since_str)
                else:
                    from datetime import timedelta
                    since = datetime.now() - timedelta(days=30)
                    since_str = since.strftime("%Y%m%d%H%M")
                    query += " WHERE c.fechacita > %s"
                    params.append(since_str)

                query += " ORDER BY c.fechacita ASC LIMIT 5000"
                cursor.execute(query, params)
                rows = _rows_to_dicts(cursor)

            appointments = []
            for r in rows:
                raw_estado = _str_val(r["estado"], "0")
                status_map = {"-1": "disponible", "0": "agendada", "1": "atendida", "4": "cancelada"}
                mapped_status = status_map.get(raw_estado, raw_estado)

                iso_date = _parse_fechacita(r.get("fechacita"))
                cups_code = _str_val(r.get("cups", ""))
                svc_code = cups_code or _str_val(r.get("service_code", "")) or None

                appointments.append({
                    "id": _str_val(r["id"]),
                    "scheduled_date": iso_date,
                    "patient_id": _str_val(r["patient_id"]),
                    "doctor_id": _str_val(r["doctor_id"]),
                    "service_code": svc_code,
                    "appointment_type": "Primera vez" if cups_code.startswith("8902") else ("Control" if cups_code.startswith("8903") else "Procedimiento"),
                    "appointment_type_desc": cups_code,
                    "status": mapped_status,
                    "is_fulfilled": _str_val(r["is_fulfilled"]) == "-1",
                    "is_facturable": False,
                    "sede_id": "01",
                    "sede_attention_id": "01",
                    "phone_contact": "",
                    "observations": _str_val(r.get("observations", "")),
                    "source": "antares",
                    "diagnosis_code": cups_code,
                    "created_at": _datetime_iso(r.get("fechasolicitud")) or iso_date,
                    "updated_at": _datetime_iso(r.get("updated_at")) or iso_date,
                })

            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_appointments", success=True, records_processed=len(appointments), duration_ms=duration_ms)
            logger.info("fetch_citas_ok",
                        mensaje=f"Obtenidas {len(appointments)} citas desde MySQL",
                        total=len(appointments))
            return appointments
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_appointments", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_citas_error",
                         mensaje="Error al obtener citas",
                         error=str(e))
            return []

    # ── PACIENTES ───────────────────────────────────────────────────────

    def fetch_patients(self, updated_since: Optional[datetime] = None) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT
                        numeropaciente AS id,
                        tipoid AS document_type,
                        idpaciente AS document_number,
                        nombre1 AS first_name,
                        nombre2 AS second_name,
                        apellido1 AS last_name1,
                        apellido2 AS last_name2,
                        fechanacimiento AS birth_date,
                        sexopaciente AS sex,
                        telefono AS phone,
                        '' AS cellphone,
                        '' AS email,
                        direccion AS address,
                        municipio AS city,
                        zona AS zone,
                        'ACTIVO' AS status,
                        entidadpaciente AS eps_id
                    FROM pacientes
                """
                if updated_since:
                    since_str = updated_since.strftime("%Y-%m-%d %H:%M:%S")
                    query += " WHERE fechamodificado > %s OR fechacreado > %s"
                    cursor.execute(query, (since_str, since_str))
                else:
                    cursor.execute(query)
                rows = _rows_to_dicts(cursor)
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_patients", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_pacientes_ok",
                        mensaje=f"Obtenidos {len(rows)} pacientes desde MySQL",
                        total=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_patients", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_pacientes_error",
                         mensaje="Error al obtener pacientes",
                         error=str(e))
            return []

    # ── NO DISPONIBILIDAD ──────────────────────────────────────────────

    def fetch_unavailability(self) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # tblexepciondias: jornadam/jornadat usan la misma convención que
                # trabaja (Antares): -1 = trabaja ese turno, 0 = exceptuado.
                # Solo se sincroniza excepción REAL (al menos un turno en 0) de la
                # agenda de consulta (idagenda=0). Las filas (-1,-1) significan
                # "trabaja normal" y NO deben bloquear el día.
                cursor.execute("""
                    SELECT DISTINCT
                        e.idtercero AS doctor_id,
                        e.fecha AS start_date,
                        e.fecha AS end_date,
                        '' AS reason_code,
                        COALESCE(e.observaciones, 'Día exceptuado') AS reason_description,
                        'EXCEPCION' AS source,
                        e.jornadam AS jornada_manana,
                        e.jornadat AS jornada_tarde,
                        e.idagenda AS idagenda
                    FROM tblexepciondias e
                    INNER JOIN citas_conf c ON e.idtercero = c.idmedico
                    WHERE c.activo = '-1'
                      AND e.idagenda = 0
                      AND (e.jornadam = 0 OR e.jornadat = 0)
                    ORDER BY e.fecha DESC
                """)
                rows = _rows_to_dicts(cursor)
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_unavailability", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_no_disponibilidad_ok",
                        mensaje=f"Obtenidos {len(rows)} días no disponibles",
                        total=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_unavailability", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_no_disponibilidad_error",
                         mensaje="Error al obtener días no disponibles",
                         error=str(e))
            return []

    # ── LÍMITES DE PLAN ────────────────────────────────────────────────

    def fetch_plan_limits(self) -> list[dict]:
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        nivel AS tercero_id,
                        '' AS plan_id,
                        0 AS max_citas_mes,
                        0 AS max_citas_inc_mes,
                        CASE WHEN porccmod > '0' THEN 1 ELSE 0 END AS cobra_copago,
                        1 AS permite_cita_web
                    FROM copagos
                    LIMIT 20
                """)
                rows = _rows_to_dicts(cursor)
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_plan_limits", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_limites_plan_ok",
                        mensaje=f"Obtenidos {len(rows)} límites de plan",
                        total=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_plan_limits", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_limites_plan_error",
                         mensaje="Error al obtener límites de plan",
                         error=str(e))
            return []

    # ── PUSH: INSERTAR/ACTUALIZAR CITA DESDE AGENDA → MySQL ──────────

    def _resolve_numeropaciente(self, cursor, data: dict) -> str:
        """Resuelve el numeropaciente (int) de Antares a partir del documento
        o del patient_id numérico. Crea el paciente si no existe."""
        document_number = _str_val(data.get("patient_document_number", data.get("document_number", "")))
        document_type = _str_val(data.get("patient_document_type", data.get("document_type", "CC")), "CC")
        patient_id = _str_val(data.get("patient_id", ""))

        # 1. Si ya viene un id numérico de Antares, usarlo.
        if patient_id.isdigit():
            return patient_id

        # 2. Buscar por número de documento.
        if document_number:
            cursor.execute(
                "SELECT numeropaciente FROM pacientes WHERE idpaciente = %s LIMIT 1",
                (document_number,),
            )
            row = _row_to_dict(cursor)
            if row and row.get("numeropaciente") is not None:
                return str(int(row["numeropaciente"]))

        # 3. Sin documento no hay forma de resolver.
        if not document_number:
            raise ValueError("No se pudo resolver el paciente: sin id numérico ni documento")

        # 4. Crear paciente nuevo (numeropaciente es auto_increment).
        cursor.execute("""
            INSERT INTO pacientes (
                tipoid, idpaciente, nombre1, nombre2, apellido1, apellido2,
                telefono, entidadpaciente, creadopor, fechacreado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, NOW())
        """, (
            document_type[:2],
            document_number[:20],
            _str_val(data.get("patient_first_name", data.get("first_name", "")))[:20],
            _str_val(data.get("patient_second_name", data.get("second_name", "")))[:20],
            _str_val(data.get("patient_last_name1", data.get("last_name1", "")))[:30],
            _str_val(data.get("patient_last_name2", data.get("last_name2", "")))[:30],
            _str_val(data.get("patient_phone", data.get("phone", "")))[:30],
            _str_val(data.get("patient_eps_id", data.get("eps_id", "")))[:14],
        ))
        return str(cursor.lastrowid)

    def insert_cit(self, data: dict) -> bool:
        """Inserta o actualiza una cita en MySQL (cita creada desde la agenda)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            scheduled_dt = data.get("scheduled_date", "")
            fechacita = _to_fechacita(scheduled_dt)
            doctor_id = _str_val(data.get("doctor_id", ""))
            service_code = _str_val(data.get("service_code", ""))
            cups_code = service_code or _str_val(data.get("appointment_type_desc", ""))
            obs = _str_val(data.get("observations", ""))
            entidad = _str_val(data.get("patient_eps_id", data.get("eps_id", "")))

            # Resolver paciente → numeropaciente numérico (INT).
            patient_id = self._resolve_numeropaciente(cursor, data)

            # Si el id es un idcita numérico existente → actualizar el slot (booking real).
            raw_id = _str_val(data.get("id", ""))
            existing_idcita = None
            if raw_id.isdigit():
                cursor.execute("SELECT idcita FROM citas WHERE idcita = %s", (int(raw_id),))
                r = _row_to_dict(cursor)
                if r and r.get("idcita") is not None:
                    existing_idcita = str(int(r["idcita"]))

            if existing_idcita:
                cursor.execute("""
                    UPDATE citas SET estado = '0', numeropaciente = %s, idmedico = %s,
                        IdServicio = '1', entidad = %s, observaciones = %s,
                        fechamodificado = NOW()
                    WHERE idcita = %s
                """, (patient_id, doctor_id, entidad, obs, existing_idcita))
                new_id = existing_idcita
            else:
                cursor.execute("""
                    INSERT INTO citas (
                        fechacita, idmedico, numeropaciente, estado, cumplida,
                        IdServicio, entidad, observaciones, creadopor, fechamodificado,
                        cancelada, bloqueado, prioritaria, agenda, tasignada, pteatendido
                    ) VALUES (
                        %s, %s, %s, '0', '0',
                        '1', %s, %s, 0, NOW(),
                        '0', '0', '0', '0', '0', '0'
                    )
                """, (fechacita, doctor_id, patient_id, entidad, obs))
                new_id = str(cursor.lastrowid)

            if cups_code:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM pxcita WHERE idcita = %s AND cups = %s",
                    (new_id, cups_code),
                )
                pr = _row_to_dict(cursor)
                if not pr or int(pr.get("cnt", 0)) == 0:
                    cursor.execute("""
                        INSERT INTO pxcita (idcita, idservicio, cups, cantidad, vrunitario)
                        VALUES (%s, %s, %s, '1', '0')
                    """, (new_id, cups_code, cups_code))

            conn.commit()
            logger.info("insertar_cita_ok",
                        mensaje="Cita guardada en MySQL",
                        id_cita=new_id,
                        fecha=fechacita)
            return True

    # ── CANCELAR ───────────────────────────────────────────────────────

    def cancel_appointment(self, appointment_id: str, reason: str) -> bool:
        # idcita en Antares es INT. Los ids UUID de la agenda (reserva directa)
        # no existen en Antares, así que no hay nada que cancelar.
        if not _str_val(appointment_id, "").isdigit():
            logger.info("cancelar_cita_omitir",
                        mensaje="id de cita no numérico (reserva directa), no hay nada que cancelar en MySQL",
                        id_cita=appointment_id)
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE citas SET estado = '4', cancelada = '-1',
                   MotivoCancela = 0, fechacancelacion = NOW(), canceladapor = 0,
                   observaciones = CONCAT(IFNULL(observaciones, ''), ' CANCELADO: ', %s)
                   WHERE idcita = %s""",
                (reason, appointment_id),
            )
            conn.commit()
            logger.info("cancelar_cita_ok",
                        mensaje="Cita cancelada en MySQL",
                        id_cita=appointment_id)
            return cursor.rowcount > 0

    def update_appointment_status(self, appointment_id: str, status: str) -> bool:
        status_map = {"agendada": "0", "atendida": "1", "cancelada": "4", "disponible": "-1"}
        sql_status = status_map.get(status, status)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE citas SET estado = %s WHERE idcita = %s",
                (sql_status, appointment_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ── CREAR AFILIADO ─────────────────────────────────────────────────

    def create_afiliado(self, data: dict) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            paciente_id = _str_val(data.get("patient_id", data.get("document_number", "")))

            cursor.execute("SELECT COUNT(*) AS cnt FROM pacientes WHERE numeropaciente = %s", (paciente_id,))
            row = _row_to_dict(cursor)
            if row and row.get("cnt", 0) > 0:
                logger.info("crear_afiliado_omitir",
                            mensaje="Afiliado ya existe en MySQL, omitiendo",
                            id_paciente=paciente_id)
                return paciente_id

            extra_notes = []
            regimen = _str_val(data.get("regimen", ""))
            if regimen:
                extra_notes.append(f"Regimen: {regimen}")
            affiliation = _str_val(data.get("affiliation_type", ""))
            if affiliation:
                extra_notes.append(f"Afiliacion: {affiliation}")
            acudiente = _str_val(data.get("acudiente_name", ""))
            if acudiente:
                extra_notes.append(f"Acudiente: {acudiente}")
            diagnostico_val = "; ".join(extra_notes) if extra_notes else ""

            cursor.execute("""
                INSERT INTO pacientes (
                    numeropaciente, tipoid, idpaciente,
                    nombre1, nombre2, apellido1, apellido2,
                    fechanacimiento, sexopaciente, telefono,
                    direccion, municipio, zona, tipoafiliacion,
                    entidadpaciente, diagnostico,
                    fechacreado, creadopor
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """, (
                paciente_id,
                _str_val(data.get("document_type", "CC")),
                _str_val(data.get("document_number", "")),
                _str_val(data.get("first_name", "")),
                _str_val(data.get("second_name", "")),
                _str_val(data.get("last_name1", "")),
                _str_val(data.get("last_name2", "")),
                _str_val(data.get("birth_date", "")),
                _str_val(data.get("sex", "")),
                _str_val(data.get("phone", "")),
                _str_val(data.get("address", "")),
                _str_val(data.get("city", "")),
                _str_val(data.get("zone", "")),
                _str_val(data.get("affiliation_type", "")),
                _str_val(data.get("eps_id", "")),
                diagnostico_val,
                "WHATSAPP",
            ))
            conn.commit()
            logger.info("crear_afiliado_ok",
                        mensaje="Afiliado creado en MySQL",
                        id_paciente=paciente_id,
                        datos_extra=str(extra_notes))
            return paciente_id


# ── singleton ───────────────────────────────────────────────────────────

antares_db = AntaresDB()


# ── helper interno ──────────────────────────────────────────────────────

def _extract_time(raw) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "0":
        return None
    parts = s.split(" ")
    if len(parts) >= 2:
        time_part = parts[1]
        if ":" in time_part:
            return time_part
    return None
