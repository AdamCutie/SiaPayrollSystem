# Backend Testing Guide

This repo supports **three levels** of backend testing:

1) **Quick manual tests** (Swagger UI)
2) **Smoke script** (PowerShell, hits many endpoints)
3) **Automated tests** (`pytest`)

## 0) Start the API

From the repo root:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Then open:

- `http://localhost:8000/docs`

## 1) Manual testing with Swagger UI

1. Go to `http://localhost:8000/docs`
2. Expand `Security & Authentication` → `POST /payroll/auth/login`
3. Click **Try it out** and log in.
4. Click **Authorize** (top-right) and paste the token as `Bearer <token>` if Swagger doesn’t auto-apply it.
5. Test endpoints by module:
   - Admin-only: `/payroll/overview/*`, `/payroll/processing/*`, `/payroll/attendance/*`, `/payroll/employees/list`, `/payroll/leaves/logs`, `/payroll/leaves/stats`
   - Any authenticated user: `/payroll/holidays/*`, `/payroll/departments/*`, `/payroll/employees/profile/{id}`, `/payroll/leaves/apply`

## 2) PowerShell smoke test (recommended)

Run the script (API must be running):

```powershell
.\scripts\smoke_backend.ps1 -BaseUrl http://localhost:8000
```

Notes:

- If this is your first time, you may need to bootstrap credentials (see `docs/BACKEND_ARCHITECTURE.md`).
- The smoke test is **read-only by default**. You can opt-in to “write” tests (payroll run / leave apply) with flags.

## 2.0) Seed data (for end-to-end testing)

If your database is empty (or you want predictable test data), seed the **payroll DB** with tagged dev data.

Seed:

```powershell
.\venv\Scripts\python.exe .\scripts\dev_seed.py seed --tag dev-seed --employees-limit 5
```

The seed script also inserts **payroll-side config overrides** into `PayrollConfigOverrides` (payroll DB) so `/payroll/processing/run` can calculate pay even if HR has no `PayrollConfigurations` yet.

If you want `/payroll/processing/run` to generate snapshots itself (instead of seeding snapshots up-front), run:

```powershell
.\venv\Scripts\python.exe .\scripts\dev_seed.py seed --tag dev-seed --employees-limit 5 --no-snapshots
```

Cleanup (delete everything inserted by the seed command):

```powershell
.\venv\Scripts\python.exe .\scripts\dev_seed.py clear --tag dev-seed
```

Notes:

- This script does **not** write to the HR database (HR is treated as read-only integration data).
- All inserted documents include `seed_tag` so cleanup is safe.

## 2.1) Full endpoint checklist (PowerShell)

This is the most explicit way to hit **every endpoint**.

1) Login and capture token:

```powershell
$base = "http://localhost:8000"
$email = Read-Host "Email"
$pw = Read-Host "Password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$login = Invoke-RestMethod -Method Post -Uri "$base/payroll/auth/login" `
  -Body @{ username = $email; password = $plain } `
  -ContentType "application/x-www-form-urlencoded"

$h = @{ Authorization = "Bearer $($login.access_token)" }
```

2) Call all endpoints:

```powershell
# Health (no auth)
Invoke-RestMethod -Method Get -Uri "$base/"

# Admin overview
Invoke-RestMethod -Method Get -Uri "$base/payroll/overview/" -Headers $h

# Employees
$emps = Invoke-RestMethod -Method Get -Uri "$base/payroll/employees/list" -Headers $h
$empId = $emps[0].id
Invoke-RestMethod -Method Get -Uri "$base/payroll/employees/profile/$empId" -Headers $h

# Departments / Holidays
Invoke-RestMethod -Method Get -Uri "$base/payroll/departments/summary" -Headers $h
Invoke-RestMethod -Method Get -Uri "$base/payroll/holidays/list" -Headers $h
Invoke-RestMethod -Method Get -Uri "$base/payroll/holidays/upcoming" -Headers $h

# Leaves
Invoke-RestMethod -Method Get -Uri "$base/payroll/leaves/stats" -Headers $h
Invoke-RestMethod -Method Get -Uri "$base/payroll/leaves/logs" -Headers $h
Invoke-RestMethod -Method Post -Uri "$base/payroll/leaves/apply" -Headers $h -ContentType "application/json" -Body (@{
  employee_id = $empId
  full_name = "$($emps[0].lastName), $($emps[0].firstName)"
  employee_number = $emps[0].employeeId
  leave_type = "Sick"
  start_date = "2026-03-20T00:00:00"
  end_date = "2026-03-21T00:00:00"
} | ConvertTo-Json)

# Attendance
$logs = Invoke-RestMethod -Method Get -Uri "$base/payroll/attendance/logs" -Headers $h
Invoke-RestMethod -Method Get -Uri "$base/payroll/attendance/penalties" -Headers $h
Invoke-RestMethod -Method Get -Uri "$base/payroll/attendance/overtime" -Headers $h

# PATCH requires an existing log
if ($logs.Count -gt 0) {
  $logId = $logs[0].id
  Invoke-RestMethod -Method Patch -Uri "$base/payroll/attendance/status/$logId?status=Approved" -Headers $h
}

# Payroll processing
Invoke-RestMethod -Method Get -Uri "$base/payroll/processing/history" -Headers $h
Invoke-RestMethod -Method Post -Uri "$base/payroll/processing/run" -Headers $h -ContentType "application/json" -Body (@{
  start_date = "2026-03-01T00:00:00"
  end_date = "2026-03-15T23:59:59"
} | ConvertTo-Json)

Invoke-RestMethod -Method Post -Uri "$base/payroll/processing/run-selective" -Headers $h -ContentType "application/json" -Body (@{
  start_date = "2026-03-01T00:00:00"
  end_date = "2026-03-15T23:59:59"
  employee_ids = @($empId)
} | ConvertTo-Json)

# CSV export
Invoke-WebRequest -Method Get -Uri "$base/payroll/processing/export/csv" -Headers $h -OutFile ".\\payroll_export.csv"
```

Notes:

- If some collections are empty (no attendance logs, no holidays, etc.), “list” endpoints can return `[]` and that is still a valid result.
- `POST /payroll/auth/set-password` is admin-only and intentionally not automated here because it changes credentials.
- Dashboard metrics (`/payroll/overview/`) are computed from real collections; if your DB is empty they may show `0`.

## 3) Automated tests (pytest)

Run:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Current tests use **dependency overrides/mocks** so they don’t require a real MongoDB connection.

## Troubleshooting

- `401 Unauthorized`: you’re missing the `Authorization: Bearer <token>` header or the token expired.
- `403 Forbidden`: you are authenticated but don’t have the right role (admin vs employee).
- To confirm what the backend thinks you are, call `GET /payroll/auth/me` with your token.
- Dev-only: set `DISABLE_AUTH=true` in `.env` to bypass all JWT/RBAC checks for local testing.
- MongoDB connection fails on startup: check `.env` values and network access to your Mongo cluster.
- `POST /payroll/processing/run` returns `processed_count: 0`: either (a) those employees already have snapshots for that pay period, or (b) they are missing a payroll config in both `HR.PayrollConfigurations` and `PayrollConfigOverrides` so the run skips them.
