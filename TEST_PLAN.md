# Plan de Pruebas — AntaresBridge + AgendaSystem

> Cobertura punta a punta del flujo `Antares MySQL → Bridge (pymysql/httpx) → Agenda Postgres/Redis → Agent Groq → WhatsApp Kapso`. Plan ejecutado en build, sin tocar prod.

## 1. Inventario y brechas encontradas
- **AntaresBridge `src/` 2.505L (8 archivos .py):** 0 tests previos, sin `tests/`, sin `pytest`. Riesgo alto en `src/db/antares.py:834` (helpers + 25 DOCTOR_NAMES, `SATURDAY_OFF`, `last_activity`).
- **AgendaSystem `src/` 31 archivos:** 1 test `tests/test_agent_conversation.py` 18 casos solo `agent/state` puro. 0% en `api/routes/sync|appointments|webhooks|dashboard`, `agent/orchestrator|extractor|tool_handlers`, `workers/*`, `services/kapso`.

## 2. Pirámide aplicada

### Unit puro (<1s, sin I/O)
- **Bridge:** `_parse_fechacita`, `_to_fechacita`, `_str_val`, `_str_int`, `_datetime_iso`, `_rows_to_dicts`, `_extract_time`, `serialize_row`, `Settings._empty_env_to_default`, `SyncStatus` (`record_operation`, `record_mysql_ping`, `to_dict`, `cycle_history` clipping 20).
- **Agenda:** `_normalize_specialty`, `_extract_service_specialty`, `_doctor_matches_service` (alias ortopedia/neuropsic), `_blocked_shifts`, `_parse_date_flexible`, `classify_appointment_kind`, `normalize_identity` (2/3/4 palabras), `_is_placeholder`, `_extracted_to_fields`, `_clean_llm_response`, `STATE_KEY_MAPPING`.

### Integración con mocks (sin testcontainers, rápido)
- **Bridge:** `AntaresDB.get_connection/ping/fetch_*` con `MagicMock pymysql`, `SyncEngine.sync_cycle` con `httpx.MockTransport/respx` para 8 endpoints (`/sync/services` batch vs `/appointments` 1-a-1), `wait_for_mysql_with_backoff` backoff `5,10,20,40,60` capping, `push_to_antares` filtrado `whatsapp/system` + `cancelada`.
- **Agenda sync:** `POST /sync/appointments` antifantasma `pending_push+disponible`, `POST /doctors` upsert + `INACTIVO` stale, `POST /schedules` full-replace `delete(Schedule)` por `doctor_id`, `POST /unavailability` purga `jornada_manana/tarde`, `POST /patients` normalización, `GET /pending-updates|push-result`.
- **Appointments:** `GET /availability/{code}?date` deriva `_derive_schedule_slots` (Schedule `day_of_week`, `occupied_set` con `disponible/agendada/Activo/atendida`, `jornada -1/0`, `GHOST_MAX_DAYS 120`, `Colombia UTC-5`, `slot_duration`).
- **Webhooks:** `POST /kapso` HMAC SHA256 dual-secret `prod`+`test` → `200`, firma mala `401`, JSON malo `400`, `enqueue_incoming_message` `lpush`.
- **Workers:** `whatsapp_worker._extract_destination_id` 5 candidatos, deduplicación `wa_message_id`, retry `400/422/429` vs `401/403/404`, `reminder_worker` ventana `±5m`, `waitlist_worker` snapshot `has_news` + `FAIL_BACKOFF_CYCLES`, `kapso` sanitización `\\n→espacio, 500→497...`.

### E2E + Funcional (flujos reales del paciente, con DB mockeada)
- **Gherkin:** `agendar pediatría` (search not found → register 2011-08-22 → find_availability 890283 → create 08:00 → pending_push → bridge insert_cit), `sin cupos → waitlist (3 días)`, `cancelar`, `que especialidades tienes?` sin tool (lista `SERVICE_CODES`), `chitchat hola mi amor` sin re-preguntar.
- **E2E:** `MySQL datosipspymr` semilla `citas/citas_conf/tblexepciondias` → `Bridge sync_cycle` → `Postgres` → `GET /availability` → webhook Kapso firmado → `agent.process_message` → `kapso_client.send_text` → `Message assistant` + `Appointment pending_push`.

## 3. Datos de prueba y oráculos
- Fixture `2026-10-14` con `17953649 Jorge Pérez` `08:00-12:00` para reproducir tu caso testigo; `tblexepciondias` con `jornadam 0`.
- `faker` para `Patient/Doctor/Appointment` (realista `document_type` RC/TI, `sex` masculino/femenino).
- Oráculos: `available_dates[doctor].slots` agrupado, `total_booked` vs `occupied_set`, `waitlist deadline +3d`.

## 4. Ejecución
```bash
# Bridge unit (20 tests)
pytest tests/ -q
# Agenda unit+mock (51 tests)
pytest AgendaSystem/tests/ -q
# CI con testcontainers para integración real (postgres:16, redis:7, mysql:8)
pytest --cov --cov-fail-under=70
```
Actual: **71 tests, 0 fallos** (`tests 22 + AgendaSystem 51` con el fix `src/workers/base.py:49 Optional[dict]` para Python 3.9).

## 5. Criterios de éxito
- Unit: branches `if trabaja -1 / jornadam 0 / SATURDAY_OFF / GHOST 120` cubiertos, sin `pytest` warnings.
- Integración: `X-API-Key` y batch vs per-cita verificados, `SystemLog` metadata.
- E2E: `containment rate` booking `80-92%`, `first-response <2s` simulado, `pending_push`→`synced` idempotente.

## 6. Próximos pasos
- Subir cobertura a `>80` con `testcontainers` mysql/postgres reales y Groq live 5% sample.
- Añadir `deepeval` semanal sobre 65 casos + `Langfuse` per-property tracing (top 5% conversaciones quema 35-45% tokens).
