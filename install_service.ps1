param([switch]$Uninstall)

$ErrorActionPreference = "Stop"

$serviceTaskName  = "AntaresBridge"
$watchdogTaskName = "AntaresBridgeWatchdog"
$bridgeDir        = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe        = Join-Path $bridgeDir "venv\Scripts\python.exe"

function Test-Administrator {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($Uninstall) {
    schtasks.exe /Delete /TN $watchdogTaskName /F | Out-Null
    schtasks.exe /Delete /TN $serviceTaskName  /F | Out-Null
    Write-Host "Tareas eliminadas: $serviceTaskName, $watchdogTaskName"
    exit 0
}

if (-not (Test-Administrator)) {
    Write-Host "ERROR: ejecuta este script como Administrador." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: no se encontro el venv ($pythonExe)." -ForegroundColor Red
    Write-Host "Ejecuta run.bat una vez para crear el venv e instalar dependencias."
    exit 1
}

$serviceXml  = (Get-Content -Raw (Join-Path $bridgeDir "service_task.xml.template")).Replace("__BRIDGE_DIR__", $bridgeDir).Replace("__PYTHON_EXE__", $pythonExe)
$watchdogXml = (Get-Content -Raw (Join-Path $bridgeDir "watchdog_task.xml.template")).Replace("__BRIDGE_DIR__", $bridgeDir)

$serviceXmlPath  = Join-Path $bridgeDir "service_task.xml"
$watchdogXmlPath = Join-Path $bridgeDir "watchdog_task.xml"

[IO.File]::WriteAllText($serviceXmlPath,  $serviceXml,  [Text.Encoding]::Unicode)
[IO.File]::WriteAllText($watchdogXmlPath, $watchdogXml, [Text.Encoding]::Unicode)

schtasks.exe /Create /XML $serviceXmlPath /TN $serviceTaskName /F
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al crear la tarea $serviceTaskName" -ForegroundColor Red
    exit 1
}

schtasks.exe /Create /XML $watchdogXmlPath /TN $watchdogTaskName /F
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al crear la tarea $watchdogTaskName" -ForegroundColor Red
    exit 1
}

schtasks.exe /Run /TN $serviceTaskName | Out-Null

Write-Host ""
Write-Host "OK: tareas instaladas."
Write-Host "  $serviceTaskName  -> arranca al boot y se reinicia solo ante fallos (cada 1 min)"
Write-Host "  $watchdogTaskName -> watchdog cada 5 min (reinicia el bridge si no responde)"
Write-Host ""
Write-Host "Verifica en taskschd.msc y el dashboard http://localhost:8001"
