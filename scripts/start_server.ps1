param(
    [string]$CondaEnv = 'helth',
    [string]$ListenHost = '0.0.0.0',
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# Keep this file ASCII-only: PowerShell 5.1 reads BOM-less scripts as ANSI.
# Capture the requested env first: dot-sourcing conda_env.ps1 rebinds $CondaEnv
# to its own param default in this scope, silently discarding our argument.
$requestedCondaEnv = $CondaEnv
. (Join-Path $PSScriptRoot 'conda_env.ps1')

$uvicornArgs = @('-m', 'uvicorn', 'backend.main:app', '--host', $ListenHost, '--port', "$Port")
if ($Reload) {
    $uvicornArgs += '--reload'
}

$python = Resolve-EnvPython -CondaEnv $requestedCondaEnv
& $python @uvicornArgs
exit $LASTEXITCODE
