[CmdletBinding()]
param(
    [string]$Origin = "http://127.0.0.1:8001",
    [string]$CloudflaredPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($CloudflaredPath)) {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    $CloudflaredPath = if ($command) {
        $command.Source
    }
    else {
        Join-Path $repositoryRoot "tmp\tools\cloudflared.exe"
    }
}

if (-not (Test-Path -LiteralPath $CloudflaredPath -PathType Leaf)) {
    throw "cloudflared was not found. Install it from the official Cloudflare distribution."
}

Write-Host "Starting a demo-only Quick Tunnel to $Origin"
Write-Host "Copy the ephemeral https://*.trycloudflare.com URL into Fabric at runtime only."
& $CloudflaredPath --no-autoupdate tunnel --url $Origin
