[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8001"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($env:MAINTCONTROL_API_TOKEN)) {
    throw "Set MAINTCONTROL_API_TOKEN in the current shell before testing MaintControl."
}

$base = $BaseUrl.TrimEnd("/")
$headers = @{ Authorization = "Bearer $($env:MAINTCONTROL_API_TOKEN)" }
$results = foreach ($endpoint in @("work-orders", "maintenance-events")) {
    $uri = "$base/api/v1/${endpoint}?page_size=2"
    $response = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
    [pscustomobject]@{
        Endpoint = $endpoint
        Status = 200
        ReturnedRows = @($response.data).Count
        HasPagination = $null -ne $response.pagination
    }
}

foreach ($case in @(
    @{ Name = "missing token"; Headers = @{} },
    @{ Name = "invalid token"; Headers = @{ Authorization = "Bearer invalid" } }
)) {
    $response = Invoke-WebRequest -Method Get -Uri "$base/api/v1/work-orders?page_size=1" `
        -Headers $case.Headers -SkipHttpErrorCheck
    if ($response.StatusCode -ne 401) {
        throw "Expected 401 for $($case.Name), received $($response.StatusCode)."
    }
}

$results | Format-Table -AutoSize
Write-Host "Authentication checks passed: missing and invalid tokens returned HTTP 401."
