[CmdletBinding()]
param(
    [string]$Config = ".\config\simulator.default.toml",
    [string]$OutputRoot = ".\data\local\atlas-2025",
    [string]$BindHost = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($env:MAINTCONTROL_API_TOKEN)) {
    throw "Set MAINTCONTROL_API_TOKEN in the current shell before starting MaintControl."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @(
    (Join-Path $repositoryRoot ".venv\Scripts\python.exe"),
    (Join-Path $repositoryRoot ".venv313\Scripts\python.exe")
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

$previousPythonPath = $env:PYTHONPATH
try {
    $sourceRoot = Join-Path $repositoryRoot "src"
    $env:PYTHONPATH = if ($previousPythonPath) {
        "$sourceRoot$([IO.Path]::PathSeparator)$previousPythonPath"
    }
    else {
        $sourceRoot
    }
    & $python -m atlas_simulator --config $Config --output-root $OutputRoot `
        --host $BindHost --port $Port serve-api
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
