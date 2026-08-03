"""Dashboard HTTP para antares-bridge — puerto 8001."""

import asyncio
import pyodbc
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from src.config import get_settings
from src.db.status import sync_status

# Estructura del JSON que devuelve /api/status:
# {
#   "service": { "started_at": str, "uptime_s": int },
#   "mysql": { "connected": bool, "last_ping": str, "ping_latency_ms": int, "last_error": str },
#   "agenda": { "last_sync": str, "last_status_code": int, "last_error": str },
#   "operations": {
#     "fetch_services": { "name", "last_attempt", "success", "records_processed", "error_message", "duration_ms" },
#     ... (7 operaciones + push_to_antares)
#   },
#   "cycle_history": [
#     { "timestamp": str, "duration_s": float, "operations_failed": int, "operations_success": int }, ...
#   ]
# }

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Antares Bridge — Monitor</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #0d1117;
    color: #e6edf3;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px;
    line-height: 1.5;
    min-height: 100vh;
  }

  /* ── Banner error ── */
  #error-banner {
    display: none;
    background: #3d1f1f;
    border-bottom: 1px solid #f85149;
    color: #f85149;
    padding: 10px 20px;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
  }
  #error-banner.visible { display: block; }

  /* ── Header ── */
  header {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 14px 20px;
  }

  .header-title {
    color: #58a6ff;
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 10px;
    font-family: system-ui, -apple-system, sans-serif;
  }

  .status-bar {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 11px;
    white-space: nowrap;
  }

  .badge-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .badge-dot.green { background: #3fb950; }
  .badge-dot.red { background: #f85149; }
  .badge-dot.yellow { background: #d29922; }
  .badge-dot.gray { background: #6e7681; }

  .badge-label {
    font-weight: 600;
    color: #e6edf3;
  }

  .badge-time {
    color: #6e7681;
    font-size: 10px;
    font-family: 'Courier New', monospace;
  }

  /* ── Main layout ── */
  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
  }

  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  @media (max-width: 900px) {
    .columns { grid-template-columns: 1fr; }
  }

  /* ── Sections ── */
  .section-title {
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid #21262d;
  }

  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    overflow: hidden;
  }

  /* ── Tables ── */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  thead tr {
    background: #0d1117;
  }

  th {
    color: #8b949e;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid #30363d;
    white-space: nowrap;
  }

  td {
    padding: 7px 12px;
    border-bottom: 1px solid #21262d;
    vertical-align: middle;
  }

  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover td { background: #1c2128; }

  .row-error { background: #2d1b1b !important; }
  .row-success { background: #1b2d1b !important; }

  /* ── Badges ── */
  .pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 700;
    white-space: nowrap;
  }

  .pill-ok { background: #1f3a1f; color: #3fb950; }
  .pill-error { background: #3d1f1f; color: #f85149; }
  .pill-warn { background: #3a331f; color: #d29922; }
  .pill-neutral { background: #21262d; color: #6e7681; }

  /* ── Mono values ── */
  .mono {
    font-family: 'Courier New', monospace;
    color: #79c0ff;
    font-size: 11px;
  }

  .dim { color: #6e7681; }
  .small { font-size: 10px; }
  .error-msg { color: #f85149; font-size: 10px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* ── Footer ── */
  .footer {
    text-align: center;
    color: #6e7681;
    font-size: 10px;
    padding: 16px 0;
    border-top: 1px solid #21262d;
    margin-top: 20px;
  }
</style>
</head>
<body>

<div id="error-banner">⚠ Error al conectar con el servidor — reintentando...</div>

<header>
  <div class="header-title">🔗 Antares Bridge — Monitor de Sincronización</div>
  <div class="status-bar">
    <!-- Servicio: siempre RUNNING si el JSON responde -->
    <div class="status-badge" id="badge-service">
      <span class="badge-dot green"></span>
      <span class="badge-label">RUNNING</span>
      <span class="badge-time" id="svc-uptime">—</span>
    </div>
    <!-- MySQL -->
    <div class="status-badge" id="badge-mysql">
      <span class="badge-dot gray" id="mysql-dot"></span>
      <span class="badge-label" id="mysql-label">CARGANDO...</span>
      <span class="badge-time" id="mysql-time">—</span>
    </div>
    <!-- Agenda-System -->
    <div class="status-badge" id="badge-agenda">
      <span class="badge-dot gray" id="agenda-dot"></span>
      <span class="badge-label" id="agenda-label">CARGANDO...</span>
      <span class="badge-time" id="agenda-time">—</span>
    </div>
  </div>
</header>

<div class="container">
  <div class="columns">
    <!-- ── Columna izquierda: operaciones de sync ── -->
    <div>
      <div class="section-title">Operaciones del Ciclo de Sync</div>
      <div class="card">
        <table>
          <thead>
            <tr>
              <th>Operación</th>
              <th>Último Intento</th>
              <th>Resultado</th>
              <th>Registros</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody id="ops-tbody">
            <tr><td colspan="5" class="dim" style="padding:20px;text-align:center">Cargando...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Columna derecha: historial de ciclos ── -->
    <div>
      <div class="section-title">Historial de Ciclos</div>
      <div class="card">
        <table>
          <thead>
            <tr>
              <th>Inicio</th>
              <th>Duración</th>
              <th>Exitosas</th>
              <th>Fallidas</th>
            </tr>
          </thead>
          <tbody id="cycle-tbody">
            <tr><td colspan="4" class="dim" style="padding:20px;text-align:center">Sin ciclos aún</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<div class="container">
  <div class="section-title">Push Inverso — Citas hacia MySQL</div>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Operación</th>
          <th>Último Intento</th>
          <th>Resultado</th>
          <th>Insertadas</th>
          <th>Duración</th>
          <th>Error</th>
        </tr>
      </thead>
      <tbody id="push-tbody">
        <tr><td colspan="6" class="dim" style="padding:20px;text-align:center">Cargando...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<div class="footer" id="footer">
  —
</div>

<script>
  /* ── Helpers ── */
  function toColombia(ts) {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleString('es-CO', { timeZone: 'America/Bogota' });
    } catch { return ts; }
  }

  function fmtDuration(ms) {
    if (ms == null) return '—';
    if (ms < 1000) return ms + 'ms';
    return (ms / 1000).toFixed(1) + 's';
  }

  /* ── Operational labels ── */
  var OP_LABELS = {
    fetch_services: 'Services (CUPS)',
    fetch_doctors: 'Doctores',
    fetch_schedules: 'Horarios',
    fetch_unavailability: 'No Disponibilidad',
    fetch_plan_limits: 'Límites de Plan',
    fetch_patients: 'Pacientes',
    fetch_appointments: 'Citas',
    push_to_antares: 'Push → MySQL',
  };

  var ALL_OPS = [
    'fetch_services', 'fetch_doctors', 'fetch_schedules',
    'fetch_unavailability', 'fetch_plan_limits',
    'fetch_patients', 'fetch_appointments', 'push_to_antares',
  ];

  /* ── Render ── */
  function render(data) {
    /* ── Header badges ── */
    var svc = data.service || {};
    document.getElementById('svc-uptime').textContent =
      'uptime ' + Math.floor((svc.uptime_s || 0) / 3600) + 'h ' +
      Math.floor(((svc.uptime_s || 0) % 3600) / 60) + 'm';

    var mysql = data.mysql || {};
    var mysqlDot = document.getElementById('mysql-dot');
    var mysqlLabel = document.getElementById('mysql-label');
    if (mysql.connected) {
      mysqlDot.className = 'badge-dot green';
      mysqlLabel.textContent = 'MySQL OK';
    } else {
      mysqlDot.className = 'badge-dot red';
      mysqlLabel.textContent = 'MySQL ERROR';
    }
    document.getElementById('mysql-time').textContent =
      mysql.last_ping ? toColombia(mysql.last_ping) : '—';

    var agenda = data.agenda || {};
    var agendaDot = document.getElementById('agenda-dot');
    var agendaLabel = document.getElementById('agenda-label');
    var code = agenda.last_status_code || 0;
    if (code >= 200 && code < 300) {
      agendaDot.className = 'badge-dot green';
      agendaLabel.textContent = 'Agenda OK ' + code;
    } else if (code > 0) {
      agendaDot.className = 'badge-dot red';
      agendaLabel.textContent = 'Agenda ERROR ' + code;
    } else {
      agendaDot.className = 'badge-dot gray';
      agendaLabel.textContent = 'Sin respuesta';
    }
    document.getElementById('agenda-time').textContent =
      agenda.last_sync ? toColombia(agenda.last_sync) : '—';

    /* ── Operations table ── */
    var ops = data.operations || {};
    var opsTbody = document.getElementById('ops-tbody');
    var rows = ALL_OPS.map(function(name) {
      if (name === 'push_to_antares') return null; // va en su propia tabla
      var o = ops[name] || {};
      var pill = o.success ? 'pill-ok' : (o.last_attempt ? 'pill-error' : 'pill-neutral');
      var pillTxt = o.success ? 'OK' : (o.last_attempt ? 'ERROR' : '—');
      var rowClass = o.success ? '' : (o.last_attempt ? 'row-error' : '');
      return '<tr class="' + rowClass + '">' +
        '<td>' + (OP_LABELS[name] || name) + '</td>' +
        '<td class="mono small">' + (o.last_attempt ? toColombia(o.last_attempt) : '—') + '</td>' +
        '<td><span class="pill ' + pill + '">' + pillTxt + '</span></td>' +
        '<td>' + (o.records_processed != null ? o.records_processed : '—') + '</td>' +
        '<td class="error-msg" title="' + (o.error_message || '') + '">' + (o.error_message || '—') + '</td>' +
        '</tr>';
    }).filter(Boolean);

    opsTbody.innerHTML = rows.length
      ? rows.join('')
      : '<tr><td colspan="5" class="dim" style="padding:20px">Sin datos</td></tr>';

    /* ── Push inverse table ── */
    var push = ops['push_to_antares'] || {};
    var pushTbody = document.getElementById('push-tbody');
    var pushRowClass = push.success ? 'row-success' : (push.last_attempt ? 'row-error' : '');
    var pushPill = push.success ? 'pill-ok' : (push.last_attempt ? 'pill-error' : 'pill-neutral');
    var pushPillTxt = push.success ? 'OK' : (push.last_attempt ? 'ERROR' : '—');
    pushTbody.innerHTML = push.last_attempt != null
      ? '<tr class="' + pushRowClass + '">' +
          '<td>Push → MySQL</td>' +
          '<td class="mono small">' + toColombia(push.last_attempt) + '</td>' +
          '<td><span class="pill ' + pushPill + '">' + pushPillTxt + '</span></td>' +
          '<td>' + (push.records_processed != null ? push.records_processed : '—') + '</td>' +
          '<td>' + fmtDuration(push.duration_ms) + '</td>' +
          '<td class="error-msg" title="' + (push.error_message || '') + '">' + (push.error_message || '—') + '</td>' +
        '</tr>'
      : '<tr><td colspan="6" class="dim" style="padding:20px">Sin intentos de push</td></tr>';

    /* ── Cycle history ── */
    var hist = data.cycle_history || [];
    var cycleTbody = document.getElementById('cycle-tbody');
    if (hist.length === 0) {
      cycleTbody.innerHTML = '<tr><td colspan="4" class="dim" style="padding:20px">Sin ciclos aún</td></tr>';
    } else {
      // Mostrar más reciente primero
      var cycleRows = hist.slice().reverse().map(function(c) {
        var rowClass = c.operations_failed > 0 ? 'row-error' : 'row-success';
        return '<tr class="' + rowClass + '">' +
          '<td class="mono small">' + toColombia(c.timestamp) + '</td>' +
          '<td>' + c.duration_s + 's</td>' +
          '<td><span class="pill pill-ok">' + c.operations_success + '</span></td>' +
          '<td>' + (c.operations_failed > 0
            ? '<span class="pill pill-error">' + c.operations_failed + ' fallidas</span>'
            : '<span class="pill pill-neutral">0</span>') + '</td>' +
          '</tr>';
      });
      cycleTbody.innerHTML = cycleRows.join('');
    }

    /* ── Footer ── */
    document.getElementById('footer').textContent =
      'Última actualización: ' + toColombia(new Date().toISOString()) + ' — Actualizando cada 10 segundos';

    /* ── Hide error banner ── */
    document.getElementById('error-banner').classList.remove('visible');
  }

  /* ── Fetch loop ── */
  var errorShown = false;
  async function load() {
    try {
      var res = await fetch('/api/status');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      render(data);
      errorShown = false;
    } catch(e) {
      if (!errorShown) {
        document.getElementById('error-banner').classList.add('visible');
        errorShown = true;
      }
      console.error('fetch error', e);
    }
  }

  // Primera carga inmediata
  load();
  // subsequent cada 10s
  setInterval(load, 10000);
</script>
</body>
</html>
"""


def create_dashboard_app() -> FastAPI:
    app = FastAPI(title="Antares Bridge Dashboard", docs=False, redoc=False)

    @app.get("/api/status")
    async def api_status():
        """Endpoint JSON con todo el estado del sync engine."""
        return sync_status.to_dict()

    @app.get("/api/availability")
    async def api_availability(
        service_code: str = Query(..., description="Código CUPS del servicio"),
        date_from: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
        date_to: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    ):
        """Consulta disponibilidad real desde SQL Server (citas estado='-1')."""
        settings = get_settings()

        conn_str = (
            f"DRIVER={{SQL Server}};"
            f"SERVER={settings.antares_server},{settings.antares_port};"
            f"DATABASE={settings.antares_database};"
            f"UID={settings.antares_user};"
            f"PWD={settings.antares_password};"
            f"TrustServerCertificate=yes;"
        )

        def _query_db():
            conn = pyodbc.connect(conn_str, timeout=30)
            try:
                cursor = conn.cursor()
                fechaini = date_from.replace("-", "") + "0000"
                fechafin = date_to.replace("-", "") + "2359"

                cursor.execute("""
                    SELECT TOP 200 c.idcita, c.fechacita, c.idmedico, c.entidad,
                           p.cups, c.estado
                    FROM citas c
                    LEFT JOIN pxcita p ON c.idcita = p.idcita
                    WHERE c.estado = '-1'
                      AND c.fechacita >= ?
                      AND c.fechacita <= ?
                      AND (p.cups = ? OR c.IdServicio = ?)
                    ORDER BY c.fechacita
                """, (fechaini, fechafin, service_code, service_code))
                columns = [col[0] for col in cursor.description] if cursor.description else []
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            finally:
                conn.close()

        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(executor, _query_db)
        executor.shutdown(wait=False)

        # Agrupar por fecha y por doctor
        available_dates = {}
        for row in rows:
            fechacita = row.get("fechacita", "")
            if not fechacita or len(str(fechacita)) < 12:
                continue
            s = str(fechacita)
            try:
                fecha = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
                hora = f"{s[8:10]}:{s[10:12]}"
            except (ValueError, IndexError):
                continue
            doctor_id = str(row.get("idmedico", ""))
            cups = str(row.get("cups", "") or row.get("IdServicio", ""))
            entidad = str(row.get("entidad", "") or "")

            if fecha not in available_dates:
                available_dates[fecha] = {}
            if doctor_id not in available_dates[fecha]:
                available_dates[fecha][doctor_id] = {
                    "doctor_id": doctor_id,
                    "slots": [],
                    "cups": cups,
                    "entidad": entidad,
                }
            available_dates[fecha][doctor_id]["slots"].append(hora)

        # Formatear respuesta igual que check_availability de appointments.py
        result_dates = []
        for fecha, doctors in sorted(available_dates.items()):
            for doc_id, doc_info in doctors.items():
                result_dates.append({
                    "date": fecha,
                    "doctor_id": doc_id,
                    "doctor_name": "",  # se llena del lado del agente con get_doctor_info
                    "slots": sorted(set(doc_info["slots"])),
                    "service_code": service_code,
                    "entidad": doc_info["entidad"],
                })

        return JSONResponse({
            "service_code": service_code,
            "date_from": date_from,
            "date_to": date_to,
            "available_dates": result_dates,
            "total_slots": sum(len(d["slots"]) for d in available_dates.values() for d in d.values()),
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Página principal del dashboard."""
        return DASHBOARD_HTML

    return app
