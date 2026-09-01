# Antares — Modelo de Agenda y Disponibilidad

> Fuente de verdad: base de datos MySQL `datosipspymr` en el host local de la IPS (Windows Server). Este documento es el resultado de la investigación limpia sobre cómo Antares genera y persiste la agenda. **No tocar Antares en producción**; solo se lee.

## 1. Tablas clave

| Tabla | Rol | Clave / Filtro relevante |
|---|---|---|
| `citas` | **Citas materializadas** (cada slot ocupado tiene una fila) | `idcita` PK int auto_increment, `fechacita` char(12) `YYYYMMDDHHMM`, `idmedico` char(15), `numeropaciente` int, `estado` tinyint |
| `citas_conf` | **Horario semanal por doctor** | `idmedico`, `activo=-1` (activo), `idagenda=0` (consulta) vs `≠0` (procedimientos), `trabaja0..6`, `hiniciom/hfinalm` (mañana), `hiniciot/hfinalt` (tarde), `duracioncita` (min) |
| `pacientes` | Pacientes | `numeropaciente` PK int auto_increment, `tipoid` char(2), `idpaciente` char(20) = documento |
| `pxcita` | Servicios por cita (cups) | `idcita` int, `cups` char(8) |
| `codigossoat` | Catálogo CUPS | `codigocups`, `descripcioncups` |
| `tblexepciondias` | Días exceptuados (no atiende) | `idtercero` (=idmedico), `fecha` |
| `especialidades` | Catálogo de especialidades | `idespecialidad` int, `nombreespecialidad` varchar |
| `tblagendas` | Agendas de procedimientos | `idtercero` (=idmedico), `nombreagenda` (ej. "Electrocardiogramas") |

## 2. Estados de `citas`

`citas` tiene 3 columnas de estado; la UI de Antares combina varias:

| Columna | Valores | Significado |
|---|---|---|
| `estado` | `-1` = disponible (hueco reservado), `0` = agendada, `1` = atendida, `4` = cancelada | Estado principal del slot |
| `cumplida` | `-1` = atendida/fulfilled, `0` = no | Sub-estado "Cumplida" (verde en UI) = `estado=0` + `cumplida=-1` |
| `horallegada` / `horaatencion` | datetime / NULL | `horallegada` set → "Paciente en Sala" (amarillo) |
| `pacienteensala`, `pteatendido`, `tasignada`, `prioritaria`, `bloqueado` | `0` / `-1` | Otros sub-estados (Comprometida, Prioritaria, etc.) |
| `cancelada` | `0` / `1` | No confundir con `estado=4` |

**Estados en septiembre 2026 (verificado):**
- `estado=0` agendada: 22.465 filas totales, 304 en septiembre
- `estado=-1` disponible: 13.422 totales, 21 en septiembre
- `estado=1` atendida: 3.815 totales

**Crucial:** Toda fila de `citas` tiene **paciente asignado** (`numeropaciente > 0`). No existen filas sin paciente. Un hueco realmente libre **no tiene fila en `citas`** — es un slot del horario que no tiene cita.

## 3. Cómo se genera la agenda en Antares (UI "Asignación de Citas")

1. **Horario** (`citas_conf`, `idagenda=0`): por doctor, por día de semana (`trabaja0..6`, donde **`0=domingo`**, `1=lunes`, ..., `6=sábado`), dos ventanas (mañana `hiniciom/hfinalm`, tarde `hiniciot/hfinalt`), y `duracioncita` (10/15/20/30 min).
2. **Agenda del día** = para el `idmedico` y la fecha, generar slots a intervalos `duracioncita` dentro de las ventanas del día correspondiente.
3. **Cada slot se materializa como fila en `citas`** con paciente (de la lista de espera o asignado manualmente). El slot nace con `estado=-1` ("disponible" = reservado tentativo) y pasa a `estado=0` ("agendada") al confirmar, o a `cumplida=-1` al atender.
4. **No hay "huecos" materializados sin paciente.** Un hueco libre real = **un slot del horario que NO tiene fila en `citas`**.

Ejemplo verificado (Belisario Herman 53815, 01-sep, turno mañana):
- Horario: `08:00-12:40` + `13:00-17:00`, `duracioncita=20` → ~26 slots
- Citas: 34 filas en `citas` para ese día (todas con paciente), de las cuales 6 son `estado=-1` (reservadas) y 28 son `estado=0` (confirmadas) — doctor **sobrecargado / sin huecos**.

## 4. Cómo se calcula la disponibilidad

```
disponibilidad = horario (citas_conf idagenda=0) − TODAS las citas con paciente
               = slots del horario que NO tienen fila en citas (para esa fecha/hora/doctor)
```

- **Ocupadas** = TODA fila de `citas` con paciente, sin importar `estado` (`-1`, `0`, `1`). Solo `estado=4` (cancelada) libera el slot.
- La disponibilidad se calcula **por fecha y por doctor**, y luego se filtra por especialidad (vía `DOCTOR_NAMES` → `specialty_name`).

## 5. Cómo lo extrae el Antares Bridge (fuente fiel)

- **`fetch_schedules`**: `SELECT ... FROM citas_conf WHERE activo='-1' AND idagenda=0` → por cada `trabaja{day}=-1`, extrae `hiniciom/hfinalm` y `hiniciot/hfinalt`, convierte `day_of_week = (day_idx + 6) % 7` para mapear `0=domingo` (Antares) → `0=lunes` (Python `weekday()`), y envía `{doctor_id, day_of_week, start_time, end_time, slot_duration}`.
- **`fetch_appointments`**: `SELECT c.fechacita, c.fechasolicitud, c.idmedico, c.numeropaciente, c.IdServicio, c.estado, ... , (SELECT cups FROM pxcita ...) AS cups FROM citas c WHERE c.fechacita > :since` → `created_at` desde `fechasolicitud` (no desde `fechacita`), `service_code` con fallback a `IdServicio` cuando `cups` es NULL, deduplicado por `pxcita` vía subquery.
- **`fetch_doctors`**: `SELECT DISTINCT idmedico FROM citas_conf WHERE activo='-1'` → `specialty_id` mapeado vía `SPECIALTY_CODES` (idespecialidad de `especialidades`).

## 6. Cómo lo consume AgendaSystem (verdad única)

- **Sincronización**: `POST /api/v1/sync/*` → `schedules`, `doctors`, `patients`, `appointments`, `unavailability` (de `tblexepciondias`), `plan-limits`. `sync_schedules` hace **full-replace por doctor** para no dejar días corridos.
- **Disponibilidad**: `GET /api/v1/appointments/availability/{service_code}?date=YYYY-MM-DD` deriva con `_derive_schedule_slots`: horario del doctor para `day_of_week == target_date.weekday()` **menos** ocupadas (`status in ("disponible","agendada","Activo","atendida")`) **menos** `DoctorUnavailability`. Devuelve `slot_duration_minutes` real por doctor.
- **`handle_find_availability` y `handle_find_all_availability`**: ambos derivan del horario (no de `status=="disponible"`).
- **Reserva**: `handle_create_appointment` valida contra el horario y bloquea con `pg_advisory_xact_lock`; crea `Appointment` con `source=whatsapp`, `antare_sync_status=pending_push`. El bridge hace `pending-updates` → resuelve paciente por documento (crea en `pacientes` si hace falta) → `INSERT/UPDATE citas` en Antares → `push-result` confirma.
- **Cancelación**: `appointment.status="cancelada"` → `pending_push` → bridge hace `UPDATE citas SET estado=4 ... WHERE idcita = ?` (solo si el id es numérico, las reservas directas UUID se omiten sin error).

## 7. Reglas de oro (para no volver a romper)

1. **Nunca ofrecer un slot que tiene fila en `citas`** (con paciente), sin importar `estado`. Libre = horario sin cita.
2. **Día**: Antares `trabaja0` = domingo; API `weekday()` lunes=0. Convertir con `(d+6)%7`.
3. **`idagenda=0` = consulta**; `≠0` = procedimientos (no mezclar para disponibilidad de consulta).
4. **`citas` sin paciente no existen** (verificado: 0 en 39k filas). No filtrar por `estado=-1` + sin persona.
5. `citas.fechacita` es `char(12)` `YYYYMMDDHHMM` local (sin zona); `target_date` es Colombia UTC-5.
