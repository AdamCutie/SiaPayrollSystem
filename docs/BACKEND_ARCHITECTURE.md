# SiaPayrollSystem Backend Architecture (Flow + Security)

This document explains how the **FastAPI backend** is structured, how requests flow through the system, and what changed in the recent hardening pass (auth/RBAC, safer HR lookups, snapshot consistency).

## 1) Big Picture

### Components

- `main.py`: FastAPI app bootstrap, CORS, router registration, startup/shutdown lifecycle.
- `core/`
  - `core/config.py`: environment-driven settings (`.env`).
  - `core/database.py`: Motor (async MongoDB) client and DB handles.
  - `core/security.py`: password hashing + JWT creation.
  - `core/auth.py`: JWT decode + FastAPI dependencies for RBAC.
- `integrations/hr/`
  - `integrations/hr/adapter.py`: **read-only** access helpers to the legacy HR DB.
  - `integrations/hr/schemas.py`: Pydantic schemas that safely serialize HR data (ObjectId/Decimal128 → JSON).
- `modules/`: feature routers + services (processing, attendance, leaves, etc.).
- `db/models.py`: Pydantic document models for the payroll DB (snapshots, attendance logs, etc.).

### Two Logical Databases (Same Mongo Cluster)

The system uses one MongoDB cluster but treats it as **two logical databases**:

- **Legacy HR DB** (`hr_db`) — integration source (**read-only**):
  - `Employees`
  - `PayrollConfigurations`
- **Payroll DB** (`db`) — the new system (**read/write**):
  - `PayrollSnapshots`, `AttendanceLogs`, `LeaveRequests`, `Holidays`
  - `PenaltyRecords`, `OvertimeRecords`
  - `PayrollConfigOverrides` (optional) → payroll-side payroll config overrides
  - `AuthUsers` (new) → payroll system credentials store

## 2) Request → Response Flow

### HTTP routing

All routers are mounted under the shared prefix:

- `/payroll/*` (registered in `main.py`)

Example:

- `POST /payroll/processing/run` hits `modules/processing/router.py`

### Typical flow per request

1. **FastAPI router** receives the request.
2. **Auth/RBAC dependency** runs (if the route is protected).
3. Router calls a **service** or **integration adapter**.
4. Service reads from:
   - `hr_db` for legacy employee/config data
   - `db` for payroll operational data
5. Router returns JSON (Pydantic handles serialization).

## 3) Authentication + RBAC (What Changed)

### JWT content

On successful login, the backend issues a JWT containing:

- `sub`: user email
- `role`: `"admin"` or `"employee"`
- `employee_id`: HR `Employees._id` (stringified ObjectId)
- `exp`: expiry timestamp (automatic)

### Login endpoint

- `POST /payroll/auth/login` (OAuth2 form: `username`, `password`)

Flow:

1. Look up the user in **HR**: `hr_db.Employees` by email.
2. Determine role:
   - HR role in `HR_ADMIN_ROLES` → payroll role `"admin"` (case/whitespace-insensitive)
   - otherwise → `"employee"`
3. Verify password from **payroll DB**: `db.AuthUsers` (bcrypt hash).
4. Return JWT.

### Why passwords live in the payroll DB

The HR database is treated as integration data (read-only). Storing passwords in `db.AuthUsers` avoids mutating legacy HR records and keeps responsibility clear:

- HR DB = identity/profile data
- Payroll DB = payroll app credentials + payroll operations data

### RBAC rules (current)

- **Admin-only**
  - `/payroll/overview/*`
  - `/payroll/processing/*`
  - `/payroll/attendance/*`
  - `/payroll/employees/list`
  - `/payroll/leaves/logs`, `/payroll/leaves/stats`
- **Authenticated (admin or employee)**
  - `/payroll/holidays/*`
  - `/payroll/departments/*`
  - `/payroll/employees/profile/{employee_id}` *(employees are restricted to self)*
  - `/payroll/leaves/apply` *(employees are restricted to self)*

### Using the token

Send the token in requests:

- `Authorization: Bearer <access_token>`

### Dev bypass (temporary)

For local development/testing only, you can disable auth checks entirely:

- Set `.env` → `DISABLE_AUTH=true`

When enabled, the backend treats every request as an admin user so you can hit endpoints without a token.

## 4) Bootstrapping Passwords (First-Time Setup)

If no `AuthUsers` records exist yet, you have two options:

### Option A (recommended for local dev): temporary passwordless bootstrap

1. Set this in `.env`:

   - `ALLOW_PASSWORDLESS_LOGIN=true`

2. Log in as an HR Admin (email must exist in HR `Employees`).
3. Call:

   - `POST /payroll/auth/set-password` (admin-only)

4. After setting passwords, turn bootstrap off:

   - `ALLOW_PASSWORDLESS_LOGIN=false`

### Option B: create an AuthUsers record directly

Use `core/security.py:get_password_hash()` to generate a bcrypt hash, then insert a document into `db.AuthUsers`:

- `email`
- `employee_id` (stringified HR `_id`)
- `password_hash`

## 5) Payroll Processing Flow (What Gets Written)

### Full payroll run

- `POST /payroll/processing/run`

`PayrollProcessingService.run_full_payroll()` does:

1. Read all active HR employees (`hr_db.Employees`).
2. For each employee:
   - Prevent duplicates for the same period (`db.PayrollSnapshots` query + a unique DB index on `(employee_id, pay_period_start, pay_period_end)`).
   - Fetch latest HR salary config (`hr_db.PayrollConfigurations`, sorted by `updatedAt`).
     - If HR has no config, the backend also checks `db.PayrollConfigOverrides`; if still missing, the run skips them and `processed_count` will not increase.
   - Validate config values (e.g., `basicSalary > 0`, no negative amounts). Invalid configs are skipped.
   - Compute gross/deductions/net:
     - Deductions are calculated using `AgencyCalculator`.
     - Net pay also adds approved overtime and subtracts approved penalties from payroll DB.
   - Count approved attendance logs in the period.
   - Compute expected weekdays in the period (Mon–Fri, inclusive).
   - Insert a `PayrollSnapshot` into `db.PayrollSnapshots` including:
     - `department` (from HR)
     - `days_worked`, `days_present`, `days_absent`

### Selective payroll run

- `POST /payroll/processing/run-selective`

Same logic, but only for the selected employee `_id` list.

## 6) Fixes Applied (Summary)

- Safer HR payroll-config lookup: no more “empty name → regex `^` matches everyone” risk (`integrations/hr/adapter.py`).
- Employee endpoints now return Pydantic-serialized data (prevents ObjectId/Decimal128 JSON issues).
- Payroll snapshots now store `department` so `/processing/history?department=...` can work going forward.
- Replaced hard-coded `13` absent-days logic with computed weekday count.
- Dashboard overview no longer uses hardcoded approvals/departments/delayed payout; these are now computed from MongoDB (definitions live in `modules/dashboard/router.py`).
- Leave stats no longer use placeholder leave totals; `total_leave/paid_leave/unpaid_leave` are now approved leave-days year-to-date (definitions live in `modules/leaves/router.py`).
- Net-pay penalty/overtime lookup now keys by the explicit `employee_id` passed from HR identity (reduces ID mismatch risk).
- Attendance status update validates `log_id` before `ObjectId(...)` conversion (returns 400 instead of 500).
- App shutdown closes the Mongo client (`main.py` + `core/database.py`).
- CORS origins are now configurable (`CORS_ORIGINS` in settings).
