param(
    [Parameter(Mandatory = $false)]
    [string]$BaseUrl = "http://localhost:8000",

    [Parameter(Mandatory = $false)]
    [switch]$IncludeWrites,

    [Parameter(Mandatory = $false)]
    [switch]$NoAuth
)

$ErrorActionPreference = "Stop"

function Get-PlainTextPassword {
    $secure = Read-Host "Password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [string]$ContentType = "application/json"
    )

    try {
        if ($null -eq $Body) {
            $result = Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers
        }
        elseif ($ContentType -eq "application/x-www-form-urlencoded") {
            $result = Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -Body $Body -ContentType $ContentType
        }
        else {
            $json = $Body | ConvertTo-Json -Depth 10
            $result = Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -Body $json -ContentType $ContentType
        }

        return [pscustomobject]@{ ok = $true; result = $result; status = 200 }
    }
    catch {
        $status = $null
        try { $status = [int]$_.Exception.Response.StatusCode } catch { }
        return [pscustomobject]@{ ok = $false; error = $_.Exception.Message; status = $status }
    }
}

Write-Host "== Smoke test: $BaseUrl ==" -ForegroundColor Cyan

# 1) Health (no auth)
$health = Invoke-Json -Method "GET" -Url "$BaseUrl/"
if (-not $health.ok) {
    Write-Host "Health check failed. Is the API running? ($($health.error))" -ForegroundColor Red
    exit 1
}
Write-Host "Health: OK" -ForegroundColor Green

$headers = @{}
if (-not $NoAuth) {
    # 2) Login (admin recommended)
    $email = Read-Host "Admin email"
    $password = Get-PlainTextPassword

    $login = Invoke-Json -Method "POST" -Url "$BaseUrl/payroll/auth/login" -Body @{ username = $email; password = $password } -ContentType "application/x-www-form-urlencoded"
    if (-not $login.ok) {
        Write-Host "Login failed ($($login.status)): $($login.error)" -ForegroundColor Red
        Write-Host "If this is first-time setup, see docs/BACKEND_ARCHITECTURE.md (bootstrap credentials)." -ForegroundColor Yellow
        Write-Host "If you want to test without auth, set DISABLE_AUTH=true and run this script with -NoAuth." -ForegroundColor Yellow
        exit 1
    }

    $token = $login.result.access_token
    $role = $login.result.role
    Write-Host "Login: OK (role=$role)" -ForegroundColor Green

    $headers = @{ Authorization = "Bearer $token" }
}
else {
    Write-Host "Auth disabled for this smoke run (-NoAuth). Ensure DISABLE_AUTH=true in .env." -ForegroundColor Yellow
}

function Show-Result {
    param([string]$Name, [pscustomobject]$Response)

    if (-not $Response.ok) {
        $code = if ($null -ne $Response.status) { $Response.status } else { "ERR" }
        Write-Host ("{0}: FAIL ({1})" -f $Name, $code) -ForegroundColor Red
        return
    }

    $r = $Response.result
    if ($r -is [System.Array]) {
        Write-Host ("{0}: OK (count={1})" -f $Name, $r.Count) -ForegroundColor Green
    }
    else {
        Write-Host ("{0}: OK" -f $Name) -ForegroundColor Green
    }
}

# 3) Read-only endpoint suite
Show-Result "GET /payroll/overview/" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/overview/" -Headers $headers)
Show-Result "GET /payroll/employees/list" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/employees/list" -Headers $headers)
Show-Result "GET /payroll/departments/summary" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/departments/summary" -Headers $headers)
Show-Result "GET /payroll/holidays/list" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/holidays/list" -Headers $headers)
Show-Result "GET /payroll/holidays/upcoming" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/holidays/upcoming" -Headers $headers)
Show-Result "GET /payroll/leaves/stats" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/leaves/stats" -Headers $headers)
Show-Result "GET /payroll/leaves/logs" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/leaves/logs" -Headers $headers)
Show-Result "GET /payroll/attendance/logs" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/attendance/logs" -Headers $headers)
Show-Result "GET /payroll/attendance/penalties" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/attendance/penalties" -Headers $headers)
Show-Result "GET /payroll/attendance/overtime" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/attendance/overtime" -Headers $headers)
Show-Result "GET /payroll/processing/history" (Invoke-Json -Method "GET" -Url "$BaseUrl/payroll/processing/history" -Headers $headers)

# CSV export (use Invoke-WebRequest to avoid JSON parsing)
try {
    $csv = Invoke-WebRequest -Method "GET" -Uri "$BaseUrl/payroll/processing/export/csv" -Headers $headers -UseBasicParsing
    Write-Host ("GET /payroll/processing/export/csv: OK (bytes={0})" -f $csv.RawContentLength) -ForegroundColor Green
}
catch {
    $status = $null
    try { $status = [int]$_.Exception.Response.StatusCode } catch { }
    $code = if ($null -ne $status) { $status } else { "ERR" }
    Write-Host ("GET /payroll/processing/export/csv: FAIL ({0})" -f $code) -ForegroundColor Red
}

if ($IncludeWrites) {
    Write-Host "== Write tests enabled (will insert data) ==" -ForegroundColor Yellow

    $payload = @{
        start_date = "2026-03-01T00:00:00"
        end_date   = "2026-03-15T23:59:59"
    }
    Show-Result "POST /payroll/processing/run" (Invoke-Json -Method "POST" -Url "$BaseUrl/payroll/processing/run" -Headers $headers -Body $payload)
}

Write-Host "== Done ==" -ForegroundColor Cyan
