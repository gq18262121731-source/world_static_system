param(
    [string]$CondaEnv = 'helth',
    [int]$BackendPort = 8000,
    [string]$FrontendHost = '127.0.0.1',
    [int]$FrontendPort = 5173,
    [int]$BackendTimeoutSeconds = 120,
    [int]$FrontendTimeoutSeconds = 90,
    [switch]$Reload,
    [switch]$SkipFrontend,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

function Test-PortListening {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-HttpReady {
    param([string]$Url, [int]$TimeoutSeconds, [string]$Label)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return $true
            }
        } catch {
            Write-Host "[$Label] waiting for $Url ..."
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

# ---------- backend ----------
if (Test-PortListening -Port $BackendPort) {
    Write-Host "[backend] port $BackendPort already listening, reusing the running instance"
} else {
    $backendArgs = @(
        '-NoExit', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $PSScriptRoot 'start_server.ps1'),
        '-CondaEnv', $CondaEnv,
        '-Port', "$BackendPort"
    )
    if ($Reload) {
        $backendArgs += '-Reload'
    }
    Start-Process powershell -ArgumentList $backendArgs | Out-Null
    Write-Host "[backend] starting on port $BackendPort (conda env: $CondaEnv)"
}

if (-not (Wait-HttpReady -Url "http://127.0.0.1:$BackendPort/healthz" -TimeoutSeconds $BackendTimeoutSeconds -Label 'backend')) {
    Write-Host "[backend] FAILED: /healthz not ready within $BackendTimeoutSeconds seconds." -ForegroundColor Red
    Write-Host "[backend] Check the backend PowerShell window for the actual error." -ForegroundColor Red
    exit 1
}
Write-Host "[backend] ready: http://127.0.0.1:$BackendPort/healthz" -ForegroundColor Green

# ---------- frontend ----------
if (-not $SkipFrontend) {
    if (Test-PortListening -Port $FrontendPort) {
        Write-Host "[frontend] port $FrontendPort already listening, reusing the running instance"
    } else {
        Start-Process powershell -ArgumentList @(
            '-NoExit', '-ExecutionPolicy', 'Bypass',
            '-File', (Join-Path $PSScriptRoot 'start_frontend.ps1'),
            '-ListenHost', $FrontendHost,
            '-Port', "$FrontendPort"
        ) | Out-Null
        Write-Host "[frontend] starting on ${FrontendHost}:$FrontendPort"
    }

    if (-not (Wait-HttpReady -Url "http://${FrontendHost}:$FrontendPort/" -TimeoutSeconds $FrontendTimeoutSeconds -Label 'frontend')) {
        Write-Host "[frontend] FAILED: not ready within $FrontendTimeoutSeconds seconds." -ForegroundColor Red
        Write-Host "[frontend] Check the frontend PowerShell window for the actual error." -ForegroundColor Red
        exit 1
    }
    Write-Host "[frontend] ready: http://${FrontendHost}:$FrontendPort" -ForegroundColor Green

    if (-not $NoBrowser) {
        Start-Process "http://${FrontendHost}:$FrontendPort"
    }
}

# ---------- summary ----------
Write-Host ''
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ' All services are up' -ForegroundColor Cyan
Write-Host "   Backend : http://127.0.0.1:$BackendPort  (docs: /docs, health: /healthz)"
if (-not $SkipFrontend) {
    Write-Host "   Frontend: http://${FrontendHost}:$FrontendPort"
}
Write-Host '   Login   : community_admin / 123456'
Write-Host ' Stop: close the spawned PowerShell windows (Ctrl+C first to exit uvicorn/vite).'
Write-Host '=============================================' -ForegroundColor Cyan
exit 0
