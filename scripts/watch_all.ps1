# watch_all.ps1 - service watchdog.
# Checks backend / frontend / vision every 30s and restarts whichever is down.
# Cooldown prevents duplicate restarts while a service is still booting.
# NOTE: keep this file pure ASCII; PowerShell 5.1 misparses BOM-less UTF-8 Chinese text.

$ErrorActionPreference = 'SilentlyContinue'

$projectRoot = Split-Path $PSScriptRoot -Parent
$visionRoot = Join-Path (Split-Path $projectRoot -Parent) 'Vision-Module-main\Vision-Module-main'
$frontendRoot = Join-Path $projectRoot 'frontend\vue-dashboard'

$services = @(
    @{ Name = 'backend';  Url = 'http://127.0.0.1:8000/healthz'; CooldownSec = 300 },
    @{ Name = 'frontend'; Url = 'http://localhost:5173/';        CooldownSec = 90 },
    @{ Name = 'vision';   Url = 'http://127.0.0.1:8090/healthz'; CooldownSec = 150 }
)
$lastStart = @{}
foreach ($service in $services) { $lastStart[$service.Name] = [datetime]::MinValue }

function Test-ServiceUp([string]$url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 -Uri $url
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-ServiceByName([string]$name) {
    switch ($name) {
        'backend' {
            Start-Process powershell -WindowStyle Hidden -ArgumentList @(
                '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $projectRoot 'scripts\start_server.ps1')
            )
        }
        'frontend' {
            Start-Process cmd -WindowStyle Hidden -WorkingDirectory $frontendRoot -ArgumentList @(
                '/c', 'npm run dev'
            )
        }
        'vision' {
            $env:VISION_SERVICE_ENV_FILE = Join-Path $visionRoot 'configs\local_bridge_demo.env'
            Start-Process (Join-Path $visionRoot '.venv\Scripts\python.exe') -WindowStyle Hidden -WorkingDirectory $visionRoot -ArgumentList @(
                '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8090'
            )
        }
    }
}

Write-Host '===== Service watchdog started (30s interval, Ctrl+C to stop) ====='
Write-Host 'Watching: backend :8000 | frontend :5173 | vision :8090'

while ($true) {
    $now = Get-Date
    $stamp = $now.ToString('HH:mm:ss')
    $statusParts = @()

    foreach ($service in $services) {
        $name = $service.Name
        if (Test-ServiceUp $service.Url) {
            $statusParts += "$name OK"
            continue
        }

        $sinceStart = ($now - $lastStart[$name]).TotalSeconds
        if ($sinceStart -lt $service.CooldownSec) {
            $waited = [int]$sinceStart
            $statusParts += "$name BOOTING(${waited}s)"
            continue
        }

        Write-Host "[$stamp] $name is DOWN - restarting..." -ForegroundColor Yellow
        Start-ServiceByName $name
        $lastStart[$name] = $now
        $statusParts += "$name RESTARTED"
    }

    $line = $statusParts -join ' | '
    Write-Host "[$stamp] $line"
    Start-Sleep -Seconds 30
}
