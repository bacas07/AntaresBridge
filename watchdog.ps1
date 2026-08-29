$ErrorActionPreference = "Stop"
$bridgeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName  = "AntaresBridge"
$logDir    = Join-Path $bridgeDir "logs"
$logFile   = Join-Path $logDir "watchdog.log"
$healthUrl = "http://127.0.0.1:8001/api/status"

try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200 -and $resp.Content -match "started_at") {
        exit 0
    }
    throw "Respuesta inesperada del dashboard"
}
catch {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $msg = "{0} - Bridge sin respuesta ({1}); reiniciando tarea {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $_.Exception.Message, $taskName
    Add-Content -Path $logFile -Value $msg
    schtasks.exe /End /TN $taskName | Out-Null
    Start-Sleep -Seconds 5
    schtasks.exe /Run /TN $taskName | Out-Null
    exit 1
}
