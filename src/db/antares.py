"""Capa de acceso a datos MySQL (datosipspymr) — producción IPS Pastor y Maria.

Todas las columnas en esta BD son LONGTEXT. Los valores numéricos son strings ("-1", "0", "20").
Las fechas en citas.fechacita usan formato YYYYMMDDHHMM (ej: "202606140800").
"""

import pymysql
import time
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from typing import Generator

from src.config import get_settings
from src.logger import logger
from src.db.status import sync_status


# ── helpers de conversión ──────────────────────────────────────────────

def _parse_fechacita(fechacita_str: str) -> str | None:
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
    """Normaliza LONGTEXT: None → default, strip."""
    if v is None:
        return default
    return str(v).strip()


def _str_int(v, default=0) -> int:
    """Convierte LONGTEXT numérico a int."""
    try:
        return int(_str_val(v, str(default)))
    except (ValueError, TypeError):
        return default


# ── conexión ────────────────────────────────────────────────────────────


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
                charset="latin1",  # latin1 para recibir bytes UTF-8 crudos (datosipspymr usa latin1_swedish_ci)
                init_command="SET NAMES utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=30,
                read_timeout=120,
                write_timeout=60,
            )
            yield conn
        except pymysql.MySQLError as e:
            logger.error("mysql_connection_error", error=str(e))
            sync_status.record_mysql_ping(success=False, error=str(e))
            raise
        finally:
            if conn:
                conn.close()

    def ping(self) -> tuple[bool, int, str]:
        """Ejecuta un SELECT 1 para verificar que la conexión está viva.

        Retorna:
            (success, latency_ms, error_message)
        """
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
        """Catálogo CUPS desde codigossoat (solo consultas y procedimientos relevantes)."""
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
                rows = cursor.fetchall()
                duration_ms = int((time.monotonic() - start) * 1000)
                sync_status.record_operation("fetch_services", success=True, records_processed=len(rows), duration_ms=duration_ms)
                logger.info("fetch_services", count=len(rows))
                return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_services", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_services_error", error=str(e))
            return []

    # ── DOCTORES (virtuales, no hay tabla médicos) ─────────────────────

    # Mapeo de nombres obtenidos de BD_HealthNet + análisis de CUPS en pxcita
    DOCTOR_NAMES = {
        "10409903": ("Dra. Coromoto Villalobos Danielline", "Gastroenterología Pediátrica"),
        "1118814810": ("Dra. Cindy Arregoces Álvarez", "Endocrinología Pediátrica"),
        "1118839778": ("Dr. Pediatría (1118839778)", "Pediatría"),
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
        "6524194": ("Dr. Pediatría (6524194)", "Pediatría"),
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

    def fetch_doctors(self) -> list[dict]:
        """Construye doctores desde citas_conf con nombres del mapeo DOCTOR_NAMES."""
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT c.idmedico AS id
                    FROM citas_conf c
                    WHERE c.activo = '-1'
                      AND c.idmedico IS NOT NULL
                      AND c.idmedico != ''
                """)
                rows = cursor.fetchall()

            doctors = []
            for r in rows:
                doc_id = _str_val(r["id"])
                name, specialty = self.DOCTOR_NAMES.get(doc_id, (f"Dr. {doc_id}", ""))
                doctors.append({
                    "id": doc_id,
                    "name": name,
                    "specialty_id": "",
                    "specialty_name": specialty,
                    "phone": "",
                    "email": "",
                    "status": "ACTIVO",
                    "agenda_web": True,
                })

            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_doctors", success=True, records_processed=len(doctors), duration_ms=duration_ms)
            logger.info("fetch_doctors", count=len(doctors))
            return doctors
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_doctors", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_doctors_error", error=str(e))
            return []

    # ── HORARIOS (schedules desde citas_conf) ──────────────────────────

    def fetch_schedules(self) -> list[dict]:
        """Convierte citas_conf → schedules semanales.

        Cada config activa produce hasta 2 schedules por día (mañana y tarde).
        Solo se usan las columnas NUEVAS en minúscula (hiniciom*, hfinalm*, hiniciot*, hfinalt*).
        La fecha 1899-12-30 es dummy — solo importa la HORA.
        """
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
                      AND idmedico IS NOT NULL
                      AND idmedico != ''
                """)
                rows = cursor.fetchall()

            schedules = []
            for r in rows:
                doctor_id = _str_val(r["doctor_id"])
                slot_dur = _str_int(r["slot_duration"], 20)
                is_active = _str_val(r["activo"]) == "-1"

                for day_idx in range(7):
                    trabaja = _str_val(r.get(f"trabaja{day_idx}", "0"))
                    if trabaja != "-1":
                        continue

                    # Mañana
                    h_ini_m = _extract_time(r.get(f"hiniciom{day_idx}"))
                    h_fin_m = _extract_time(r.get(f"hfinalm{day_idx}"))
                    if h_ini_m and h_fin_m:
                        schedules.append({
                            "doctor_id": doctor_id,
                            "day_of_week": day_idx,
                            "start_time": h_ini_m,
                            "end_time": h_fin_m,
                            "slot_duration": slot_dur,
                            "is_active": is_active,
                        })

                    # Tarde
                    h_ini_t = _extract_time(r.get(f"hiniciot{day_idx}"))
                    h_fin_t = _extract_time(r.get(f"hfinalt{day_idx}"))
                    if h_ini_t and h_fin_t:
                        schedules.append({
                            "doctor_id": doctor_id,
                            "day_of_week": day_idx,
                            "start_time": h_ini_t,
                            "end_time": h_fin_t,
                            "slot_duration": slot_dur,
                            "is_active": is_active,
                        })

            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_schedules", success=True, records_processed=len(schedules), duration_ms=duration_ms)
            logger.info("fetch_schedules", configs=len(rows), schedules=len(schedules))
            return schedules
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_schedules", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_schedules_error", error=str(e))
            return []

    # ── CITAS ───────────────────────────────────────────────────────────

    def fetch_new_appointments(self, last_sync: datetime | None = None) -> list[dict]:
        """Lee citas desde MySQL (citas JOIN pxcita).

        Convierte fechacita YYYYMMDDHHMM → ISO datetime.
        Mapea estado -1/0/1/4 → texto.
        En la primera sincronización (last_sync=None), solo carga últimos 30 días.
        """
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT
                        c.idcita AS id,
                        c.fechacita,
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
                        pxc.cups,
                        pxc.idservicio AS pxc_servicio
                    FROM citas c
                    LEFT JOIN pxcita pxc ON c.idcita = pxc.idcita
                """
                params = []

                if last_sync:
                    since_str = last_sync.strftime("%Y%m%d%H%M")
                    query += " WHERE c.fechacita > %s"
                    params.append(since_str)
                else:
                    # Primera sincronización: solo últimos 30 días para no sobrecargar
                    from datetime import timedelta
                    since = datetime.now() - timedelta(days=30)
                    since_str = since.strftime("%Y%m%d%H%M")
                    query += " WHERE c.fechacita > %s"
                    params.append(since_str)

                query += " ORDER BY c.fechacita ASC LIMIT 5000"
                cursor.execute(query, params)
                rows = cursor.fetchall()

            appointments = []
            for r in rows:
                raw_estado = _str_val(r["estado"], "0")
                status_map = {"-1": "disponible", "0": "agendada", "1": "atendida", "4": "cancelada"}
                mapped_status = status_map.get(raw_estado, raw_estado)

                iso_date = _parse_fechacita(r.get("fechacita"))
                cups_code = _str_val(r.get("cups", ""))
                # Si no hay CUPS, dejar service_code como None (no forzar "1")
                svc_code = cups_code if cups_code else None

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
                    "created_at": iso_date,
                    "updated_at": _parse_fechacita(r.get("updated_at")) or iso_date,
                })

            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_appointments", success=True, records_processed=len(appointments), duration_ms=duration_ms)
            logger.info("fetch_appointments", count=len(appointments))
            return appointments
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_appointments", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_appointments_error", error=str(e))
            return []

    # ── PACIENTES ───────────────────────────────────────────────────────

    def fetch_patients(self, updated_since: datetime | None = None) -> list[dict]:
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
                rows = cursor.fetchall()
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_patients", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_patients", count=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_patients", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_patients_error", error=str(e))
            return []

    # ── NO DISPONIBILIDAD ──────────────────────────────────────────────

    def fetch_unavailability(self) -> list[dict]:
        """Días exceptuados desde tblexepciondias."""
        import time
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        e.idtercero AS doctor_id,
                        e.fecha AS start_date,
                        e.fecha AS end_date,
                        '' AS reason_code,
                        COALESCE(e.observaciones, 'Día exceptuado') AS reason_description,
                        'EXCEPCION' AS source
                    FROM tblexepciondias e
                    INNER JOIN citas_conf c ON e.idtercero = c.idmedico
                    WHERE c.activo = '-1'
                    ORDER BY e.fecha DESC
                """)
                rows = cursor.fetchall()
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_unavailability", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_unavailability", count=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_unavailability", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_unavailability_error", error=str(e))
            return []

    # ── LÍMITES DE PLAN ────────────────────────────────────────────────

    def fetch_plan_limits(self) -> list[dict]:
        """Límites desde copagos."""
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
                rows = cursor.fetchall()
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_plan_limits", success=True, records_processed=len(rows), duration_ms=duration_ms)
            logger.info("fetch_plan_limits", count=len(rows))
            return rows
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            sync_status.record_operation("fetch_plan_limits", success=False, records_processed=0, error_message=str(e), duration_ms=duration_ms)
            logger.error("fetch_plan_limits_error", error=str(e))
            return []

    # ── PUSH: INSERTAR CITA DESDE AGENDA → MYSQL ──────────────────────

    def insert_cit(self, data: dict) -> bool:
        """Inserta una cita creada por WhatsApp en la BD de producción.

        Escribe en 2 tablas: citas + pxcita.
        La admisión se asume ya creada o se crea aquí mismo.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Generar idcita único
            cursor.execute("SELECT MAX(CAST(idcita AS UNSIGNED)) FROM citas")
            max_id = cursor.fetchone()
            # MySQL dict cursor returns dict
            max_val = list(max_id.values())[0] if max_id else 0
            new_id = str((max_val or 0) + 1)

            scheduled_dt = data.get("scheduled_date", "")
            fechacita = _to_fechacita(scheduled_dt)
            doctor_id = _str_val(data.get("doctor_id", ""))
            patient_id = _str_val(data.get("patient_id", ""))
            service_code = _str_val(data.get("service_code", ""))
            # El CUPS real va en pxcita.cups. Si service_code no viene,
            # fallback a appointment_type_desc que en la práctica también es el CUPS.
            cups_code = service_code or _str_val(data.get("appointment_type_desc", ""))
            phone = _str_val(data.get("phone_contact", ""))
            obs = _str_val(data.get("observations", ""))
            created_by = _str_val(data.get("created_by", "WHATSAPP"))
            entidad = _str_val(data.get("eps_id", ""))

            # 2. INSERT INTO citas — IdServicio se deja como '1' (categoría general)
            # El CUPS específico del procedimiento vive en pxcita.cups, no aquí.
            cursor.execute("""
                INSERT INTO citas (
                    idcita, fechacita, idmedico, numeropaciente, estado, cumplida,
                    IdServicio, entidad, observaciones, creadopor, fechamodificado,
                    cancelada, bloqueado, prioritaria, agenda, tasignada, pteatendido
                ) VALUES (
                    %s, %s, %s, %s, '0', '0',
                    '1', %s, %s, %s, NOW(),
                    '0', '0', '0', '0', '0', '0'
                )
            """, (
                new_id, fechacita, doctor_id, patient_id,
                entidad, obs, created_by,
            ))

            # 3. INSERT INTO pxcita — el CUPS real del procedimiento
            if cups_code:
                cursor.execute("""
                    INSERT INTO pxcita (idcita, idservicio, cups, cantidad, vrunitario)
                    VALUES (%s, %s, %s, '1', '0')
                """, (new_id, cups_code, cups_code))

            conn.commit()
            logger.info("insert_cit", id=new_id, fechacita=fechacita)
            return True

    # ── CANCELAR ───────────────────────────────────────────────────────

    def cancel_appointment(self, appointment_id: str, reason: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE citas SET estado = '4', cancelada = '-1',
                   MotivoCancela = %s, fechacancelacion = DATE_FORMAT(NOW(), '%%Y%%m%%d'),
                   canceladapor = 'WHATSAPP'
                   WHERE idcita = %s""",
                (reason, appointment_id),
            )
            conn.commit()
            logger.info("cancel_appointment", id=appointment_id)
            return cursor.rowcount > 0

    def update_appointment_status(self, appointment_id: str, status: str) -> bool:
        status_map = {"agendada": "0", "atendida": "1", "cancelada": "4", "disponible": "-1"}
        mysql_status = status_map.get(status, status)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE citas SET estado = %s WHERE idcita = %s",
                (mysql_status, appointment_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ── CREAR AFILIADO ─────────────────────────────────────────────────

    def create_afiliado(self, data: dict) -> str | None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            paciente_id = _str_val(data.get("patient_id", data.get("document_number", "")))

            # Verificar duplicado
            cursor.execute("SELECT COUNT(*) AS cnt FROM pacientes WHERE numeropaciente = %s", (paciente_id,))
            row = cursor.fetchone()
            if row and list(row.values())[0] > 0:
                logger.info("create_afiliado_skip", id=paciente_id, reason="ya_existe")
                return paciente_id

            # Construir texto de observaciones para datos que no tienen columna en MySQL
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

            # zone y tipoafiliacion existen en MySQL pacientes (confirmado por SHOW COLUMNS)
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
                _str_val(data.get("zone", "")),            # zona existe en MySQL
                _str_val(data.get("affiliation_type", "")), # tipoafiliacion existe en MySQL
                _str_val(data.get("eps_id", "")),
                diagnostico_val,                             # regimen + affiliation + acudiente concatenados
                "WHATSAPP",
            ))
            conn.commit()
            logger.info("create_afiliado", id=paciente_id, extra=extra_notes)
            return paciente_id


# ── singleton ───────────────────────────────────────────────────────────

antares_db = AntaresDB()


# ── helper interno ──────────────────────────────────────────────────────

def _extract_time(raw) -> str | None:
    """Extrae solo la HORA de un datetime dummy de citas_conf.

    Las columnas hiniciomX/hfinalmX tienen valores como:
      "1899-12-30 08:00:00"  →  "08:00:00"
      "1899-12-30 14:30:00"  →  "14:30:00"
      "0"                    →  None (no configurado)
      "" / NULL              →  None
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "0":
        return None
    # Intentar extraer HH:MM:SS del datetime
    parts = s.split(" ")
    if len(parts) >= 2:
        time_part = parts[1]
        # Validar que tenga formato HH:MM:SS
        if ":" in time_part:
            return time_part
    return None
