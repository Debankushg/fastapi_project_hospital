# Hospital Management – Backend (Python)

Python · FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Pydantic · JWT · TOTP (MFA) · Stripe

A drop-in port of the Node/Express backend in [`../backend`](../backend): same REST API (`/api/...`), same JSON
shapes and error format, same roles and permissions, same database schema. The existing frontend works against either
server, and both can share one database (tables, enum types, bcrypt hashes and AES‑GCM‑encrypted MFA secrets are
byte-compatible).

This document explains the backend end to end: how to run it, how the folders connect, the database,
the security model, every API endpoint (in tables), the main workflows and the Stripe payment architecture.

**Contents**
1. [Quick start and all commands](#1-quick-start-and-all-commands)
2. [Big picture (block diagram)](#2-big-picture)
3. [Folder structure and how folders connect](#3-folder-structure-and-how-folders-connect)
4. [Life of a request](#4-life-of-a-request)
5. [Roles, admin areas and capabilities](#5-roles-admin-areas-and-capabilities)
6. [Authentication and MFA](#6-authentication-and-mfa)
7. [API reference (all endpoints)](#7-api-reference)
8. [Workflows](#8-workflows)
9. [Database](#9-database)
10. [Configuration (.env)](#10-configuration-env)
11. [Commands cheat sheet](#11-commands-cheat-sheet)
12. [Swagger and how to add a feature](#12-swagger-and-how-to-add-a-feature)
13. [Operations: MFA key rotation, dev helper, uploads](#13-operations)
14. [Error format and status codes](#14-error-format-and-status-codes)
15. [Stripe payments (architecture)](#15-stripe-payments)

---

## 1. Quick start and all commands

Requirements: Python 3.11+ (tested on 3.14), PostgreSQL 13+.

```bash
cd backend_Python

# 1. Python environment
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Database (skip if it already exists, e.g. shared with the Node backend)
createdb hospital                    # or: psql -U postgres -c "create database hospital"

# 3. Settings
cp .env.example .env                 # then edit: DATABASE_URL, JWT_SECRET, MFA_ENCRYPTION_KEY, SUPER_ADMIN_*
openssl rand -hex 32                 # use for JWT_SECRET and again for MFA_ENCRYPTION_KEY

# 4. Tables + first super admin
python -m app.db.migrate             # creates enum types + missing tables (never alters existing ones)
python -m app.db.seed                # creates the super admin from SUPER_ADMIN_* in .env

# 5. Start the server
python -m app.server                 # http://localhost:4000, auto-reload when NODE_ENV=development
```

| URL | What |
|---|---|
| `http://localhost:4000/health` | Health check (`{"status":"ok"}`) |
| `http://localhost:4000/api/docs` | Swagger UI (try every endpoint) |
| `http://localhost:4000/api/docs.json` | Raw OpenAPI spec |

The Node backend also defaults to port `4000`: stop it first, or set `PORT` in `.env`.
The database named in `DATABASE_URL` must already exist. A full list of commands is in [section 11](#11-commands-cheat-sheet).

**Run in production**

```bash
NODE_ENV=production python -m app.server                       # no auto-reload
# or, with several worker processes:
uvicorn app.app:app --host 0.0.0.0 --port 4000 --workers 4
```
In production `MFA_ENCRYPTION_KEY` must not be the all-zeros placeholder (the server refuses to start). The auth rate
limit is kept in each worker's memory, so with several workers the effective limit is per worker.

---

## 2. Big picture

```
                         ┌───────────────────────────────┐
                         │   Frontend (Next.js :3000)    │
                         │   or Swagger UI / curl        │
                         └──────────────┬────────────────┘
                                        │  HTTP + JSON   (Authorization: Bearer <JWT>)
                                        ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  FASTAPI APP  (app/app.py)                                                    │
│  CORS → security headers → /health → /api routes → error handlers             │
│                                                                               │
│   ┌────────┐   ┌────────────┐   ┌────────────┐   ┌─────────┐   ┌───────────┐  │
│   │ ROUTES │──▶│ MIDDLEWARE │──▶│  SCHEMAS   │──▶│CONTROLLR│──▶│ SERVICES  │  │
│   │ URL map│   │ JWT, roles │   │ Pydantic   │   │ HTTP in/│   │ business  │  │
│   │        │   │ rate limit │   │ (400 error)│   │ out only│   │ rules     │  │
│   └────────┘   └────────────┘   └────────────┘   └─────────┘   └─────┬─────┘  │
│                                                                       │       │
│                                                       ┌───────────────┴─────┐ │
│                                                       ▼                     ▼ │
│                                               ┌──────────────┐     ┌─────────┐│
│                                               │ REPOSITORIES │     │  UTILS  ││
│                                               │ SQL via      │     │ jwt,    ││
│                                               │ SQLAlchemy   │     │ crypto, ││
│                                               └──────┬───────┘     │ files,  ││
│                                                      ▼             │ stripe  ││
│                                               ┌──────────────┐     └────┬────┘│
│                                               │   MODELS     │          │     │
│                                               │ table shapes │          │     │
│                                               └──────┬───────┘          │     │
└──────────────────────────────────────────────────────┼──────────────────┼─────┘
                                                       ▼                  ▼
                                              ┌────────────────┐  ┌───────────────┐
                                              │  PostgreSQL    │  │ uploads/ (PDF │
                                              │  (asyncpg)     │  │ prescriptions)│
                                              └────────────────┘  └───────────────┘
                                                                          ▲
                                              ┌────────────────┐          │ (separate)
                                              │ Stripe         │◀── Checkout + webhook (section 15)
                                              └────────────────┘
```

**One rule keeps it simple:** each layer only talks to the layer directly below it.
Controllers never touch the database; repositories never contain business rules and never commit
(only services commit, so a service call is one transaction).

---

## 3. Folder structure and how folders connect

```
backend_Python/
├── app/
│   ├── app.py              Builds the FastAPI app (CORS, security headers, error handlers, mounts /api)
│   ├── server.py           Starts uvicorn (reads PORT):  python -m app.server
│   ├── config/             env.py (validated .env), constants.py (limits, TTLs), permissions_config.py (role → area map)
│   ├── db/                 __init__.py (engine + per-request session), migrate.py, seed.py
│   ├── models/             SQLAlchemy tables, one file per table + enums.py (the database shape)
│   ├── schemas/            Pydantic models for request bodies / queries (one *_schema.py per domain)
│   ├── typings/            Shared type aliases: Role, Specialty, TokenStage, Paginated …
│   ├── repositories/       Database access only. One file per table/aggregate. Never commit
│   ├── services/           Business rules, permission decisions, transactions (commit)
│   ├── controllers/        Thin HTTP handlers: take parsed input → call service → build response
│   ├── routes/             URL → middleware → schema → controller. routes/__init__.py mounts all under /api
│   ├── middleware/         auth (JWT stages), rbac (role/capability gates), rate limit, errors, security headers
│   ├── utils/              jwt, password (bcrypt), crypto (AES-GCM, recovery codes), http_error, mappers,
│   │                       file_storage, date, pagination, response, stripe
│   └── scripts/            mfa_code.py (dev helper), rotate_mfa_key.py
├── tests/                  test_flow.py – end-to-end smoke test
├── uploads/                Prescription PDFs (git-ignored; created at runtime)
├── .env / .env.example     Settings (see section 10)
├── requirements.txt        Python dependencies
└── pytest.ini
```

Files are named `<thing>_<layer>.py` (`appointment_service.py`, `user_repository.py`, `patient_routes.py` …).
Repositories and services are plain modules used as `appointment_service.approve(...)`.

### 3.1 Layer connection map

```
 routes/*_routes.py
     │ use
     ├──▶ middleware/auth_middleware.py       CurrentUser (stage "full") · SetupOrFullUser · MfaPendingUser
     ├──▶ middleware/rbac_middleware.py       require_role, require_reception, require_doctor, …
     ├──▶ middleware/rate_limit_middleware.py login/MFA brute-force protection
     ├──▶ schemas/*_schema.py                 Pydantic body / query / path validation (400 on failure)
     └──▶ controllers/*_controller.py
                │ call
                ▼
          services/*_service.py ──▶ repositories/*_repository.py ──▶ models/*_model.py ──▶ PostgreSQL
                │                                                                  
                └──▶ utils/*  (jwt, password, crypto, file_storage, stripe, mappers)
```

### 3.2 Which files belong to which feature

| Feature | Route | Controller | Service(s) | Repository(ies) | Tables (models) |
|---|---|---|---|---|---|
| Register / login / me | `auth_routes` | `auth_controller` | `auth`, `account_lock`, `permission` | `user`, `patient_profile` | users, patient_profiles |
| MFA (TOTP) | `auth_routes` | `mfa_controller` | `mfa`, `account_lock` | `user`, `mfa_recovery_code` | users, mfa_recovery_codes |
| Users (create, list, deactivate, delete, doctor directory) | `user_routes` | `user_controller` | `user`, `permission` | `user`, `doctor_profile`, `prescription` | users, doctor_profiles, patient_profiles |
| Admins (promote, demote, areas) | `admin_routes` | `admin_controller` | `admin`, `permission` | `user`, `admin_assignment` | users, admin_assignments |
| Departments | `department_routes` | `department_controller` | `department`, `permission` | `user`, `admin_assignment`, `duty_schedule` | users, admin_assignments, duty_schedules |
| Duty time | `duty_routes` | `duty_controller` | `duty`, `permission` | `duty_schedule` | duty_schedules |
| Attendance | `attendance_routes` | `attendance_controller` | `attendance`, `department` | `attendance` | attendance_records |
| Leaves | `leave_routes` | `leave_controller` | `leave`, `department` | `leave`, `attendance` | leave_records, attendance_records |
| Patients (reception) | `patient_routes` | `patient_controller` | `patient` | `patient`, `patient_profile`, `user`, `appointment`, `prescription` | users, patient_profiles |
| Appointments | `appointment_routes` | `appointment_controller` | `appointment`, `doctor_availability`, `permission` | `appointment`, `patient`, `prescription` | appointments |
| Doctor consultation | `doctor_routes` | `consultation_controller` | `consultation`, `prescription` | `appointment`, `doctor_profile`, `patient`, `prescription` | appointments, prescriptions |
| Prescriptions | `prescription_routes` | `consultation_controller` | `consultation`, `prescription` | `prescription`, `appointment` | prescriptions |
| Checked visits | `visit_routes` | `consultation_controller` | `consultation` | `appointment` | appointments |
| Payments (Stripe) | `payment_routes` (incl. webhook) | `payment_controller` | `payment`, `permission` | `payment`, `appointment`, `doctor_profile`, `user` | payments, appointments |
| Analytics + calendar | `analytics_routes` | `analytics_controller` | `analytics`, `attendance_calendar` | `analytics` (raw SQL), `attendance`, `leave`, `duty_schedule` | many (read only) |

### 3.3 Service dependencies

Services may call other services for shared rules; repositories never call services.

```
 auth ───────▶ mfa ───────▶ account_lock
   │            │               │
   └───────────▶└──────────────▶└──▶ user_repository
   └──▶ permission (capabilities for /auth/me)

 appointment ──▶ doctor_availability ──▶ attendance + leave + duty_schedule + appointment repos
 attendance / leave ──▶ department (which staff does this admin manage?) ──▶ permission
 attendance_calendar ──▶ permission, attendance, leave, duty_schedule
 consultation ──▶ permission, appointment, prescription, doctor_profile
```

---

## 4. Life of a request

Example: `PATCH /api/doctor/appointments/{id}/check` (a doctor marks a patient as checked).

```
 Client ──▶ app.py: CORS · security headers
        ──▶ routes/__init__.py         "/doctor" → doctor_routes.py
        ──▶ CurrentUser                verifies JWT, stage must be "full", loads user
        ──▶ require_doctor             role is doctor, or an admin whose base_role is doctor     (else 403)
        ──▶ path param `id: Uuid`      Pydantic: must be a UUID                                  (else 400)
        ──▶ consultation_controller    thin: calls the service, builds the response
        ──▶ consultation_service       rules: appointment must be assigned to ME and "approved";
        │                              snapshot consultation fee → checked_fee; set status "checked"; commit
        ──▶ appointment_repository     flush UPDATE appointments …
        ──▶ PostgreSQL
 Client ◀── 200 JSON      (any raised HttpError is turned into JSON by error_middleware)
```

Where each kind of rule lives:

| Question | Where it is decided |
|---|---|
| Is the body/query/param shaped correctly? | `schemas/` (400) |
| Is there a valid token? Is it the right stage? | `middleware/auth_middleware.py` (401) |
| Is the role / capability allowed for this route? | `middleware/rbac_middleware.py` (403) |
| Is this user allowed to touch **this specific record** (e.g. their own appointment, staff in their area)? | `services/` using `permission_service.py` (403/404) |
| How is it stored? | `repositories/` + `models/` |

---

## 5. Roles, admin areas and capabilities

### 5.1 Roles

| Role | Created by | MFA | Notes |
|---|---|---|---|
| `super_admin` | `python -m app.db.seed` | mandatory | Full control; sees every department and every member (admins included) |
| `admin` | super admin only | mandatory | Has a **profession** (`baseRole`) plus **work areas**; manages only those areas |
| `doctor` | super admin / admin (doctor area) | mandatory | Has a specialty, license number, consultation fee |
| `receptionist` | super admin / admin (reception area) | mandatory | Patients tab, appointments, edit patients |
| `pathologist` | super admin / admin (pathology area) | mandatory | |
| `accounts` | super admin / admin (accounts area) | mandatory | Sees checked visits + revenue, takes payments |
| `patient` | public `/auth/register` | optional | Books appointments, sees own records |

Doctor specialties: `opd`, `gynecologist`, `cardiologist`, `ent`, `dermatologist`, `pediatrician`.

### 5.2 Admin work areas

An admin is a staff member (their **profession**, `baseRole`) who was given management powers over one or more areas.
The profession decides where they are *listed*; the areas decide what they can *manage*.

| Area | Members the admin can manage |
|---|---|
| `doctor_management` | doctors |
| `reception_management` | receptionists (and may delete patients) |
| `pathology_management` | pathologists |
| `accounts_management` | accounts staff (and may take payments) |
| `patient_management` | patients |

**Each department has exactly one admin.** If Admin A manages four areas and Admin B three, giving Accounts to Admin B
takes Accounts away from Admin A (A keeps the other three).

Example: *John Jou* is a receptionist promoted to admin with areas Reception + Accounts.
* The super admin sees John **only** in the Reception department, tagged "Receptionist, Admin".
* John sees the Reception and Accounts departments, can mark attendance, approve leave and change duty times there.
* If the super admin removes the Accounts area, John no longer sees that department. If John is demoted, all admin powers go.

### 5.3 Capabilities (returned by `/auth/me` and login)

| Capability | True for |
|---|---|
| `reception` | receptionist; admin with `baseRole=receptionist` or area Reception; super admin |
| `editPatients` | same as `reception` |
| `deletePatients` | admin with area Reception; super admin. **Plain receptionists cannot delete** |
| `doctor` | doctor; admin with `baseRole=doctor` |
| `accounts` | accounts staff; admin with `baseRole=accounts` or area Accounts; super admin |
| `viewChecked` | reception, accounts, super admin (checked-patients list and revenue) |
| `payments` | accounts staff; admin assigned the **Accounts management** area; super admin. (An admin who only *works as* accounts, without the area, cannot take payments) |

The frontend uses these flags to show/hide menu items; the backend enforces them again on every request.

---

## 6. Authentication and MFA

### 6.1 Token stages

| Stage | TTL | Meaning | Accepted by |
|---|---|---|---|
| `mfa_pending` | 5 min | Password OK, must submit a TOTP/recovery code | `POST /auth/mfa/verify-login` |
| `mfa_setup` | 15 min | Password OK, staff must enrol MFA first | `POST /auth/mfa/setup`, `/auth/mfa/enable` |
| `full` | 1 h | Fully signed in | every other endpoint |

### 6.2 Login flow

```
 POST /auth/login {email, password}
        │
        ├── patient without MFA ───────────────▶ { status:"authenticated", token, user }
        │
        ├── MFA already enabled ───────────────▶ { status:"mfa_required", mfaToken }
        │       └─ POST /auth/mfa/verify-login  (Bearer mfaToken, {code} or {recoveryCode}) ─▶ { token, user }
        │
        └── staff, MFA not set up yet ─────────▶ { status:"mfa_setup_required", setupToken }
                ├─ POST /auth/mfa/setup   (Bearer setupToken) ─▶ { secret, otpauthUrl, qrCodeDataUrl }   scan in authenticator app
                └─ POST /auth/mfa/enable  (Bearer setupToken, {code}) ─▶ { token, recoveryCodes[8] }  (shown once)
```

### 6.3 Security measures

| Measure | Detail |
|---|---|
| Passwords | bcrypt (12 rounds, run in a worker thread). Min 10 chars with lower, upper, digit and symbol |
| MFA secrets | Encrypted at rest with AES-256-GCM using `MFA_ENCRYPTION_KEY` |
| Recovery codes | 8 random codes, stored as SHA-256 hashes, single use |
| Lockout | 5 failed password/code attempts → account locked 15 min (HTTP 423) |
| Rate limit | Auth endpoints: 30 requests / 15 min per IP |
| Reveal MFA key later | `POST /auth/mfa/secret` needs password **and** a current code; the key is never shown at plain login |
| Headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CORP; PDF upload limited to 5 MB |
| Errors | Login errors are generic ("Invalid credentials") so accounts cannot be enumerated |

---

## 7. API reference

Base URL: `http://localhost:4000/api`. Send `Content-Type: application/json` and
`Authorization: Bearer <token>` unless the *Auth* column says **Public**.
Interactive version: **Swagger UI at `/api/docs`**.

**Legend – Auth column**

| Label | Meaning |
|---|---|
| Public | No token needed |
| mfa token / setup token | Temporary stage token from login |
| Any | Any fully signed-in user |
| Staff | Any non-patient role |
| SA | `super_admin` |
| Admin | `super_admin` or `admin`, **limited to their assigned areas** (checked in the service) |
| Reception* | receptionist, admin working as receptionist / with Reception area, super admin |
| Reception admin | admin with Reception area / receptionist-admin, super admin |
| Doctor | doctor, or admin whose `baseRole` is doctor |
| Checked access | reception, accounts, super admin |
| Payments | accounts staff, admin with the Accounts management area, super admin |

### 7.1 Auth and MFA – `/api/auth`

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| POST | `/auth/register` | Public | `email, password, fullName, phone?, dateOfBirth?, gender?, bloodGroup?, address?` | 201 `{ user }` | Always creates a **patient**. Rate limited |
| POST | `/auth/login` | Public | `email, password` | 200, one of: `{status:"authenticated", token, user}` (patient without MFA) · `{status:"mfa_required", mfaToken}` · `{status:"mfa_setup_required", setupToken}` | 401 generic "Invalid credentials", 403 deactivated, 423 locked. Rate limited |
| POST | `/auth/mfa/verify-login` | mfa token | `code` **or** `recoveryCode` | 200 `{ token, user }` | Exactly one of the two fields. Failures count toward lockout |
| POST | `/auth/mfa/setup` | setup or full token | – | 200 `{ secret, otpauthUrl, qrCodeDataUrl }` | Scan the QR (or type `secret`) in an authenticator app. 409 if MFA already on |
| POST | `/auth/mfa/enable` | setup or full token | `code` (6 digits) | 200 `{ token, recoveryCodes[8] }` | Recovery codes are shown only once |
| POST | `/auth/mfa/secret` | Any (MFA on) | `password, code` | 200 `{ secret, otpauthUrl, qrCodeDataUrl }` | Re-show the key to add another device. 400 if MFA is off |
| POST | `/auth/mfa/disable` | Any (patient) | `password, code` | 204 | 403 for staff (MFA is mandatory) |
| GET | `/auth/me` | Any | – | 200 `{ user }` – `user.capabilities` holds `reception, editPatients, deletePatients, doctor, accounts, payments, viewChecked` | The frontend uses `capabilities` for menus |

### 7.2 Users – `/api/users`

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| GET | `/users/doctors` | Any | `?specialty=` | 200 `{ doctors: [{id, fullName, specialty, consultationFee}] }` | Active doctors; patients use it to pick a specialist |
| POST | `/users` | Admin | `email, password, fullName, phone?, role, specialty?, licenseNo?, consultationFee?` | 201 `{ user }` | `role` ∈ doctor, receptionist, pathologist, accounts, patient. Doctor needs `specialty` + `licenseNo`. Admins only for roles in their areas (403 otherwise) |
| GET | `/users` | Admin | `?role=` | 200 `{ users }` | Admins only see users in their areas |
| PATCH | `/users/{id}/active` | Admin | `isActive: boolean` | 200 `{ user }` | Activate / deactivate (area-checked) |
| DELETE | `/users/{id}` | SA | – | 204 | Permanent. Any user incl. admins; not yourself, not other super admins. Deleting a patient also removes their prescription files |

### 7.3 Admins – `/api/admins` (super admin only)

| Method | Path | Body | Success response | Notes |
|---|---|---|---|---|
| GET | `/admins` | – | 200 `{ admins: [admin + baseRole + assignments] }` | |
| POST | `/admins` | `email, password, fullName, phone?, baseRole, assignments[{area, notes?}]` | 201 `{ user, assignments, reassigned }` | Creates a new admin. `baseRole` required: doctor / receptionist / pathologist / accounts. Areas held by another admin move to this one |
| POST | `/admins/{userId}/promote` | `assignments[], baseRole?` | 200 `{ user, assignments, reassigned }` | Promotes existing **staff**; `baseRole` is taken from their current role. **Patients are rejected (400)**. Super admins cannot be changed. Areas held by another admin move to this one |
| GET | `/admins/{userId}/assignments` | – | 200 `{ assignments }` | |
| PUT | `/admins/{userId}/assignments` | `assignments[], baseRole?` | 200 `{ assignments, reassigned }` | Replaces areas (a removed area makes that department disappear for the admin) |
| POST | `/admins/{userId}/demote` | `role` ∈ receptionist, pathologist, accounts, patient | 200 `{ user }` | Removes all admin powers and assignments |

**One admin per department.** Each work area has at most one admin (enforced by a unique database constraint).
Giving an area to an admin removes it from whoever had it. `reassigned` lists what moved,
e.g. `[{ "area": "accounts_management", "fromAdminId": "…", "fromAdminName": "Admin A" }]`. The other admin keeps
their remaining areas (and stays an admin, even with none left). Demoting or deleting an admin frees their areas.

`assignments[].area` ∈ `doctor_management, reception_management, pathology_management, accounts_management, patient_management`.

### 7.4 Departments, duty time, attendance – staff management

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| GET | `/department/overview` | Admin | – | 200 `{ departments, unplacedAdmins }` | Departments with members, duty times and tags like "Doctor, Admin". Super admin sees all; admins only theirs. An admin is listed only under their own profession |
| GET | `/department/staff` | Admin | – | 200 `{ staff }` | Flat list of staff the caller manages |
| GET | `/staff/{userId}/duty` | Admin | – | 200 `{ duty }` (`startTime, endTime, workDays`) | Area-checked |
| PUT | `/staff/{userId}/duty` | Admin | `startTime "HH:MM", endTime "HH:MM", workDays[0-6]` | 200 `{ duty }` | 0 = Sunday. Start ≠ end |
| GET | `/attendance` | Admin | `?date=YYYY-MM-DD` | 200 `{ date, entries }` | Daily sheet of staff the caller manages |
| POST | `/attendance` | Admin | `userId, date, status, notes?` | 201 `{ attendance }` | `status` ∈ present, absent, late, half_day, on_leave. One row per user per day (re-posting updates it). Future dates rejected |

### 7.5 Leaves – `/api/leaves`

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| POST | `/leaves/request` | Staff | `leaveType, startDate, endDate, reason?` | 201 `{ leave }` | Starts as `pending`. Max 90 days. Types: sick, casual, annual, unpaid, other |
| GET | `/leaves/mine` | Staff | – | 200 `{ leaves }` | Own requests with status |
| GET | `/leaves` | Admin | `?userId&status&from&to` | 200 `{ leaves }` | Only leaves of staff the caller manages. Admin leaves are approved by the super admin |
| POST | `/leaves` | Admin | `userId, leaveType, startDate, endDate, reason?` | 201 `{ leave }` | Admin records leave → approved immediately |
| PATCH | `/leaves/{id}/review` | Admin | `status: approved \| rejected, note?` | 200 `{ leave }` | Approval marks each day `on_leave` in attendance |
| DELETE | `/leaves/{id}` | Staff / Admin | – | 204 | Staff cancel their **own pending** request; admins delete leaves they manage |

### 7.6 Patients (reception) – `/api/patients`

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| GET | `/patients` | Reception* | `?search&sortBy=name\|joined&order=asc\|desc&page&pageSize(≤100)` | 200 `{ items, page, pageSize, total, totalPages }` | Server-side pagination, search and sort |
| GET | `/patients/{id}` | Reception* | – | 200 `{ patient, appointments }` | Details + appointment history |
| PATCH | `/patients/{id}` | Reception* | any of `fullName, phone, dateOfBirth, gender, bloodGroup, address` | 200 `{ patient }` | At least one field. Every receptionist can edit |
| DELETE | `/patients/{id}` | Reception admin | – | 204 | Plain receptionists get 403. Also deletes the patient's prescription files |

### 7.7 Appointments – `/api/appointments`

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| POST | `/appointments` | Patient / Reception* | `specialty, date, preferredDoctorId?, reason?, patientId?` | 201 `{ appointment }` | Patient books for self; reception must pass `patientId`. Status `requested` |
| GET | `/appointments/mine` | Patient | – | 200 `{ appointments }` | Own appointments with their prescriptions |
| GET | `/appointments` | Reception* | `?status&date&search&page&pageSize` | 200 `{ items, page, pageSize, total, totalPages }` | The reception queue |
| GET | `/appointments/availability` | Reception* | `?specialty&date` (both required) | 200 `{ doctors }` | Each doctor flagged available / unavailable (absent, on approved leave, not on duty) with that day's workload |
| PATCH | `/appointments/{id}/approve` | Reception* | `doctorId, note?` | 200 `{ appointment }` | Assigns an **available** doctor of the right specialty → `approved` |
| PATCH | `/appointments/{id}/reject` | Reception* | `note?` | 200 `{ appointment }` | → `rejected` |
| PATCH | `/appointments/{id}/cancel` | Patient (own) / Reception* | – | 200 `{ appointment }` | → `cancelled` |

### 7.8 Doctor consultation – `/api/doctor`, `/api/prescriptions`, `/api/visits`

| Method | Path | Auth | Body / query | Success response | Notes |
|---|---|---|---|---|---|
| GET | `/doctor/patients` | Doctor | `?status=approved\|checked&date&search&page&pageSize` | 200 `{ items, page, pageSize, total, totalPages }` | Only patients assigned to the signed-in doctor |
| GET | `/doctor/appointments/{id}` | Doctor | – | 200 `{ appointment, patient, history }` | Appointment with its prescriptions, patient details, earlier visits. Own assignments only (404 otherwise) |
| POST | `/doctor/appointments/{id}/prescriptions` | Doctor | **Raw body = PDF**; headers `Content-Type: application/pdf`, `X-File-Name: name.pdf` | 201 `{ prescription }` | ≤ 5 MB (413), PDF magic bytes checked (400), no body/other type (415), max 5 per visit (409) |
| PATCH | `/doctor/appointments/{id}/check` | Doctor | – | 200 `{ checked: true }` | Marks `checked`, stores `checked_at`, `checked_by` and the `checked_fee` snapshot. Visible to reception & accounts |
| GET | `/prescriptions/{id}/file` | Any (access checked) | – | 200 `application/pdf` (inline) | Allowed: the patient, treating doctor(s), reception, super admin |
| DELETE | `/prescriptions/{id}` | Doctor | – | 204 | Only the doctor who attached it |
| GET | `/visits/checked` | Checked access | `?date&search&page&pageSize` | 200 `{ items, page, pageSize, total, totalPages }` | Checked patients shared with reception and accounts. Reception also gets prescription files; accounts only the count |

Example PDF upload:
```bash
curl -X POST http://localhost:4000/api/doctor/appointments/<id>/prescriptions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/pdf" -H "X-File-Name: rx.pdf" \
  --data-binary @rx.pdf
```

### 7.9 Analytics and attendance calendar – `/api/analytics`

| Method | Path | Auth | Query | Success response | Notes |
|---|---|---|---|---|---|
| GET | `/analytics/patients` | Any | `from, to (YYYY-MM-DD), groupBy=day\|month` | 200 `{ groupBy, series[{bucket, requested, approved, checked, cancelled, newPatients}], totals{totalPatients, newPatients, appointments, checked, pending} }` | Aggregate counts only (no personal data). Range ≤ 400 days. Empty buckets filled with zeros |
| GET | `/analytics/revenue` | Checked access | `from, to, groupBy` | 200 `{ groupBy, series[{bucket, collected, pending, revenue, visits}], bySpecialty, totals{collected, pending, revenue, visits, averagePerVisit, collectionRate} }` | `collected` = checked visits paid via Stripe, `pending` = checked but unpaid, `revenue` = both (fee snapshot). 403 for others |
| GET | `/analytics/doctors` | Doctor / SA | `from, to` | 200 `{ doctors[{doctorId, doctorName, specialty, checked, unchecked}], totals }` | 403 for accounts, patients, receptionists |
| GET | `/analytics/attendance-calendar` | Staff (own) / managers | `month=YYYY-MM, userId?, today?` | 200 one month: per-day status, note, approved leave, duty-day flag, plus a summary | Staff see their own. `userId` only for staff the caller manages (403 otherwise). Patients get 400 |

### 7.10 Payments (Stripe) – `/api/payments`

Only the **Payments** audience (accounts staff, admins assigned the Accounts department, super admin) may call these.
Architecture and setup are in [section 15](#15-stripe-payments).

| Method | Path | Auth | Body / query | Success | Notes |
|---|---|---|---|---|---|
| GET | `/payments/receivables` | Payments | `?status=unpaid\|paid\|all&search&page&pageSize` | 200 paginated checked visits + `paymentStatus` (`unpaid`/`pending`/`paid`) | Default `unpaid` = money still to collect |
| GET | `/payments/summary` | Payments | – | 200 `{collected, paidCount, outstanding, unpaidCount, currency}` | |
| POST | `/payments/checkout` | Payments | `appointmentId` | 201 `{url, payment}` | Open `url` (Stripe-hosted page) so the client pays. Reuses an open page. 409 already paid, 400 no fee, 404 not a checked visit, 503 Stripe not configured |
| POST | `/payments/sync` | Payments | `sessionId` | 200 `{payment}` | Re-reads the session from Stripe (after redirect / Refresh). Safe to repeat |
| POST | `/payments/webhook` | Stripe signature | raw Stripe event | 200 `{received:true}` | No bearer token. Body is read unparsed so the signature can be verified |

### 7.11 Endpoint count and quick access matrix

| Area | Endpoints | SA | Admin | Doctor | Reception | Accounts | Pathologist | Patient |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Register / login / MFA / me | 8 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Users | 5 | ✔ | ✔ (areas) | doctor list | doctor list | doctor list | doctor list | doctor list |
| Admins | 6 | ✔ | – | – | – | – | – | – |
| Department / duty / attendance | 6 | ✔ | ✔ (areas) | – | – | – | – | – |
| Leaves | 6 | ✔ | ✔ | request/own | request/own | request/own | request/own | – |
| Patients | 4 | ✔ | ✔ if reception | – | ✔ (no delete) | – | – | – |
| Appointments | 7 | ✔ | ✔ if reception | – | ✔ | – | – | book/own |
| Consultation | 7 | file only | if doctor | ✔ | file / checked list | checked list | – | own file |
| Analytics | 4 | ✔ | partial | doctor chart | revenue | revenue | patient chart | patient chart |
| Payments (Stripe) | 5 | ✔ | ✔ if Accounts area | – | – | ✔ | – | – |

Total: **58 endpoints** (+ `/health`, `/api/docs`, `/api/docs.json`).

---

## 8. Workflows

### 8.1 Appointment, consultation and revenue

```
 Patient/Receptionist          Receptionist                    Doctor                     Accounts / Reception
 ───────────────────           ───────────                     ──────                     ────────────────────
 POST /appointments
   status = requested ───────▶ GET /appointments/availability
                               (absent / on leave / off duty
                                doctors are flagged)
                               PATCH /{id}/approve {doctorId}
                                 status = approved ──────────▶ GET /doctor/patients
                                                               POST …/prescriptions (PDF)
                                                               PATCH …/check
                                                                 status = checked
                                                                 checked_fee = doctor fee ─▶ GET /visits/checked
                                                                                            GET /analytics/revenue
                                                                                            POST /payments/checkout
 (reject → rejected, patient/reception cancel → cancelled)
```

Appointment statuses: `requested → approved → checked`, or `rejected` / `cancelled`.

### 8.2 Leave and attendance

```
 Staff: POST /leaves/request  ──▶  pending
 Admin (own areas) / Super admin (admins):  PATCH /leaves/{id}/review
        ├─ approved ─▶ each day in range set to attendance "on_leave"  ─▶ shows in calendar + doctor availability
        └─ rejected
 Admin: POST /attendance   mark present / late / half_day / absent per day
 Anyone: GET /analytics/attendance-calendar?month=YYYY-MM   (own)
```

### 8.3 Promoting an admin

```
 Super admin ──▶ POST /admins/{userId}/promote {baseRole, assignments:[reception, accounts]}
        user.role = admin, user.base_role = receptionist, admin_assignments rows created
 Admin now: sees Reception + Accounts departments, can use reception tools (profession),
            can delete patients (Reception area), manages attendance / leave / duty of those staff.
 Super admin ──▶ PUT …/assignments  (remove an area)  or  POST …/demote  (back to staff)
```

---

## 9. Database

PostgreSQL through SQLAlchemy 2 (async, asyncpg). The table, column and enum names are identical to the Node/Drizzle
schema, so both backends can use the same database.

`python -m app.db.migrate` runs `create_all`: it creates the enum types and any **missing** tables, and never alters
existing ones. When you change a model later, write the `ALTER TABLE` yourself (or adopt Alembic).

### 9.1 Table relationships

```
                         ┌──────────────────┐
                         │      users       │◀────────────────────────────┐
                         │ role, base_role, │                             │
                         │ mfa, lockout     │                             │
                         └─┬──┬──┬──┬──┬──┬─┘                             │
        ┌──────────────────┘  │  │  │  │  └──────────────┐                │
        ▼                     ▼  │  │  ▼                 ▼                │
 ┌───────────────┐  ┌─────────────┴┐ │ ┌──────────────┐ ┌───────────────┐  │
 │doctor_profiles│  │patient_      │ │ │mfa_recovery_ │ │admin_         │  │
 │ specialty,    │  │profiles      │ │ │codes         │ │assignments    │  │
 │ license, fee  │  │ dob, blood…  │ │ │ code_hash    │ │ area is unique│  │
 └───────────────┘  └──────────────┘ │ └──────────────┘ │ across admins │  │
                                     │                  └───────────────┘  │
        ┌────────────────────────────┼───────────────────────┐             │
        ▼                            ▼                       ▼             │
 ┌───────────────┐          ┌────────────────┐      ┌────────────────┐     │
 │duty_schedules │          │attendance_     │      │ leave_records  │     │
 │ times, days   │          │records (unique │      │ type, dates,   │     │
 └───────────────┘          │ user+date)     │      │ status, review │     │
                            └────────────────┘      └────────────────┘     │
                                                                           │
 ┌────────────────────────────┐   1 ──── *   ┌──────────────────────┐      │
 │        appointments        │──────────────▶│    prescriptions     │      │
 │ patient_id, doctor_id,     │               │ file_name, stored_   │      │
 │ specialty, date, status,   │               │ name, size           │──────┘
 │ checked_at/by, checked_fee │               └──────────────────────┘
 └──────────────┬─────────────┘
                │ 1 ──── *     ┌──────────────────────────────┐
                └─────────────▶│          payments            │  one row per Stripe Checkout attempt
                               │ amount, status, stripe_      │
                               │ session_id (unique), paid_at │
                               └──────────────────────────────┘
   (patient_id, doctor_id, handled_by, checked_by, created_by → users)
```

### 9.2 Tables

| Table | Key columns | Notes |
|---|---|---|
| `users` | `id, email (unique), full_name, phone, password_hash, role, base_role, is_active, mfa_enabled, mfa_secret_enc, failed_attempts, locked_until, created_by` | All people. `base_role` only for admins |
| `doctor_profiles` | `user_id, specialty, license_no (unique), consultation_fee` | 1 : 1 with doctor users |
| `patient_profiles` | `user_id, date_of_birth, gender, blood_group, address` | 1 : 1 with patient users |
| `mfa_recovery_codes` | `user_id, code_hash, used_at` | 8 per user |
| `admin_assignments` | `admin_id, area, notes, assigned_by` | Unique (admin, area) **and unique area**: one admin per department |
| `duty_schedules` | `user_id, start_time, end_time, work_days[], updated_by` | One per staff member |
| `attendance_records` | `user_id, date, status, notes, marked_by` | Unique (user, date) |
| `leave_records` | `user_id, leave_type, start_date, end_date, reason, status, reviewed_by/at, review_note, recorded_by` | |
| `appointments` | `patient_id, specialty, requested_doctor_id, doctor_id, appointment_date, reason, status, note, handled_by/at, checked_at, checked_by, checked_fee, created_by` | Index on (status, date) |
| `payments` | `appointment_id, patient_id, amount, currency, status, stripe_session_id (unique), stripe_payment_intent_id, created_by, paid_at` | One row per Stripe Checkout attempt for a checked visit |
| `prescriptions` | `appointment_id, patient_id, doctor_id, file_name, stored_name (unique), size_bytes` | File lives in `UPLOAD_DIR` |

### 9.3 Enums

| Enum | Values |
|---|---|
| `role` | super_admin, admin, doctor, receptionist, pathologist, accounts, patient |
| `specialty` | opd, gynecologist, cardiologist, ent, dermatologist, pediatrician |
| `admin_area` | doctor_management, reception_management, pathology_management, accounts_management, patient_management |
| `attendance_status` | present, absent, late, half_day, on_leave |
| `leave_type` | sick, casual, annual, unpaid, other |
| `leave_status` | pending, approved, rejected |
| `appointment_status` | requested, approved, checked, rejected, cancelled |
| `payment_status` | pending, paid, expired |

---

## 10. Configuration (.env)

| Variable | Required | Example / default | Purpose |
|---|:-:|---|---|
| `PORT` | no | `4000` | HTTP port |
| `NODE_ENV` | no | `development` | `production` enforces a real MFA key, disables auto-reload and the dev helper |
| `DATABASE_URL` | yes | `postgresql://postgres:postgres@localhost:5432/hospital` | PostgreSQL connection (`postgres://`, `postgresql://` or `postgresql+asyncpg://`; query params such as `?schema=public` are ignored) |
| `JWT_SECRET` | yes | ≥ 32 random chars | Signs all tokens |
| `MFA_ENCRYPTION_KEY` | yes | 64 hex chars (`openssl rand -hex 32`) | Encrypts users' MFA secrets. All-zeros is a dev placeholder; refused in production |
| `MFA_ISSUER` | no | `HospitalManagement` | Name shown in authenticator apps |
| `SUPER_ADMIN_EMAIL` / `_PASSWORD` / `_NAME` | seed | `superadmin@hospital.local` | First super admin made by `app.db.seed` (password ≥ 10 chars) |
| `UPLOAD_DIR` | no | `uploads` | Folder for prescription PDFs |
| `STRIPE_SECRET_KEY` | for payments | `sk_test_…` | Stripe API key. Without it the payment endpoints answer 503 |
| `STRIPE_WEBHOOK_SECRET` | for webhook | `whsec_…` | Verifies Stripe webhook signatures |
| `STRIPE_CURRENCY` | no | `inr` | 3-letter currency used for all payments |
| `FRONTEND_URL` | no | `http://localhost:3000` | Where Stripe returns the browser after checkout |

Fixed limits live in `app/config/constants.py`: bcrypt rounds 12, 5 failed attempts → 15 min lock,
8 recovery codes, TOTP window ±1, token TTLs (5 m / 15 m / 1 h), auth rate limit 30 per 15 min.

---

## 11. Commands cheat sheet

Run everything from `backend_Python/` with the virtual environment active (`source .venv/bin/activate`).

| Command | What it does |
|---|---|
| `python3 -m venv .venv && source .venv/bin/activate` | Create and enter the virtual environment |
| `pip install -r requirements.txt` | Install dependencies |
| `createdb hospital` | Create the database (once) |
| `cp .env.example .env` | Create your settings file |
| `python -m app.db.migrate` | Create enum types and missing tables (safe to re-run) |
| `python -m app.db.seed` | Create the first super admin |
| `python -m app.server` | Start the server with auto-reload (development) |
| `NODE_ENV=production python -m app.server` | Start without auto-reload |
| `uvicorn app.app:app --host 0.0.0.0 --port 4000 --workers 4` | Production-style start with several workers |
| `python -m app.scripts.mfa_code <email> [--key]` | Dev only: print a user's current MFA code (and key) |
| `NEW_MFA_ENCRYPTION_KEY=<hex> python -m app.scripts.rotate_mfa_key [--apply]` | Re-encrypt MFA secrets with a new server key (dry run without `--apply`) |
| `pytest -q` | Run the end-to-end smoke test (needs a `*_test` database, see below) |
| `stripe listen --forward-to localhost:4000/api/payments/webhook` | Forward Stripe test webhooks to your machine |

**Running the tests.** The smoke test drives the whole API in-process against a real Postgres and **wipes it first**,
so it refuses to run unless the database name ends in `_test`:
```bash
createdb hospital_test
export DATABASE_URL=postgresql://user:pass@localhost:5432/hospital_test
python -m app.db.migrate && pytest -q
```

**Sharing a database with the Node backend.** Point both `.env` files at the same `DATABASE_URL`. `app.db.migrate` only
adds what is missing, so it is safe against a database the Node backend already migrated. Use one backend at a time on
port 4000.

**First login (smoke check).**
```bash
curl -s localhost:4000/health
curl -s -X POST localhost:4000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"superadmin@hospital.local","password":"ChangeMe@12345"}'
# → {"status":"mfa_setup_required","setupToken":"…"}   then /auth/mfa/setup and /auth/mfa/enable (section 6.2)
```

---

## 12. Swagger and how to add a feature

Open **http://localhost:4000/api/docs**. Log in with `POST /api/auth/login`, finish MFA, click **Authorize**
and paste the final `token`. Unlike the Node backend there is no hand-written spec: FastAPI builds the OpenAPI
document from the routes and Pydantic schemas, so new endpoints show up automatically. Request bodies and queries are
documented; response bodies are not typed.

**Adding a new endpoint, step by step**

| # | Step | Folder |
|---|---|---|
| 1 | Add/adjust the table (and write the `ALTER TABLE`, or create the new table with `app.db.migrate`) | `models/` |
| 2 | Describe input with a Pydantic model | `schemas/` |
| 3 | Add DB queries (flush only, never commit) | `repositories/` |
| 4 | Add business rules, permission checks and the `commit()` | `services/` |
| 5 | Add the thin HTTP handler | `controllers/` |
| 6 | Add the URL + guards (`CurrentUser`, `require_*`, rate limiter); mount a new file in `routes/__init__.py` | `routes/` |
| 7 | Add a row to the tables in this README | `README.md` |

---

## 13. Operations

**Prescription files.** PDFs are stored on disk in `UPLOAD_DIR` (default `uploads/`, git-ignored).
Back this folder up together with the database. Files are removed only when a *patient* is deleted;
deleting a doctor keeps the patient's prescriptions.

**Dev helper (no authenticator app).** `python -m app.scripts.mfa_code user@example.com` prints the account's current
MFA code (add `--key` to print the setup key). It needs server access and refuses to run when `NODE_ENV=production`.

**Rotating `MFA_ENCRYPTION_KEY`.** This is the **server's** key that encrypts all users' MFA secrets (not a user's
authenticator key). Never use the all-zeros placeholder with real data. To switch keys without breaking anyone's MFA:
```bash
openssl rand -hex 32                                                         # new key
NEW_MFA_ENCRYPTION_KEY=<new> python -m app.scripts.rotate_mfa_key            # dry run
NEW_MFA_ENCRYPTION_KEY=<new> python -m app.scripts.rotate_mfa_key --apply    # re-encrypt (back up the DB first)
# then set MFA_ENCRYPTION_KEY=<new> in .env and restart
```

**Locked account.** After 5 failed attempts a user is locked for 15 minutes. To unlock immediately:
```sql
UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE email = 'user@example.com';
```

---

## 14. Error format and status codes

Every error is JSON (`details` appears only when there is something to add):
```json
{ "error": "Validation failed", "details": { "email": ["Invalid email"] } }
```

| Code | Meaning | Typical cause |
|---|---|---|
| 400 | Validation failed | Body/query/param does not match the schema; business rule such as "MFA not enabled" |
| 401 | Unauthorized | Missing/expired token, wrong stage, wrong password/code |
| 403 | Forbidden | Role or capability not allowed, or record outside your area/assignment |
| 404 | Not found | Unknown URL, unknown id, or a record you are not allowed to see |
| 409 | Conflict | Duplicate email / license, doctor unavailable, MFA already enabled, invalid status change |
| 413 | Payload too large | PDF over 5 MB |
| 415 | Unsupported media type | Prescription upload without `Content-Type: application/pdf` |
| 423 | Locked | Account temporarily locked after failed attempts |
| 429 | Too many requests | Auth rate limit hit |
| 500 | Server error | Unexpected; logged on the server, message hidden in production |
| 502 | Bad gateway | Stripe did not return a payment page |
| 503 | Not configured | `STRIPE_SECRET_KEY` / webhook secret missing |

---

## 15. Stripe payments

The accounts department collects the consultation fee of a **checked** visit through **Stripe Checkout** (Stripe's
hosted payment page). Card numbers are typed on Stripe's page; this server never sees or stores them, which keeps the
backend out of PCI card-data scope.

**Who may take payments:** accounts staff, admins assigned the **Accounts management** area, and the super admin
(`capabilities.payments`, enforced by `require_payments` on every route). Receptionists, doctors, other admins and
patients get 403.

### 15.1 Architecture

```
┌──────────────────┐   ① checkout {appointmentId}   ┌───────────────────────────────────────┐
│ Accounts staff   │───────────────────────────────▶│  Hospital API (FastAPI)               │
│ (browser, :3000) │◀───────────────────────────────│                                       │
└────────┬─────────┘   ② { url, payment }           │  payment_routes ─▶ payment_controller │
         │                                           │        └─▶ payment_service            │
         │ ③ open url                                │              ├─▶ utils/stripe_util    │
         ▼                                           │              ├─▶ payment_repository   │
┌──────────────────┐   ④ card details                │              └─▶ appointment_repo     │
│  Stripe Checkout │◀── typed here, never reaches ───│                                       │
│  (hosted page)   │    the hospital server          └───────┬──────────────────▲────────────┘
└────────┬─────────┘                                         │ ⑤ create /       │ ⑧ webhook
         │ ⑥ redirect to FRONTEND_URL/payments               │   retrieve       │   (signed)
         │   ?checkout=success&session_id=…                  │   session        │
         ▼                                                   ▼                  │
┌──────────────────┐   ⑦ sync {sessionId}            ┌──────────────┐   ┌───────┴──────┐
│ Frontend /payments│───────────────────────────────▶│  PostgreSQL  │   │ Stripe API   │
└──────────────────┘   (updates the same row)        │  payments    │   │ + webhooks   │
                                                     └──────────────┘   └──────────────┘
```

| Part | Responsibility |
|---|---|
| `payment_routes.py` | URLs and guards (`CurrentUser` + `require_payments`; the webhook has no bearer token) |
| `payment_controller.py` | Builds the HTTP response; passes the **raw** webhook bytes through |
| `payment_service.py` | Fee rules, reuse of open sessions, "already paid" check, applying Stripe's state |
| `payment_repository.py` | `payments` table: create, find by session, mark paid / expired (idempotent), summary |
| `utils/stripe_util.py` | Creates the Stripe client (503 when no key), converts amounts to minor units |
| `payments` table | One row per Checkout attempt: `status` = `pending` → `paid` / `expired`, `stripe_session_id` unique |

### 15.2 Payment sequence

```
 Accounts / Admin(Accounts) / Super admin            Backend                           Stripe
 ────────────────────────────────────────            ───────                           ──────
 GET  /payments/receivables?status=unpaid ─────────▶ checked visits + payment state
 POST /payments/checkout {appointmentId} ──────────▶ fee = checked_fee snapshot
                                                      create Checkout Session ───────▶ session (url)
                                                      INSERT payments (pending) ◀────
 ◀──────── { url } ── browser opens Stripe page ───────────────────────────────────▶ client enters card
                                                                                      │ pays
 browser returns to  FRONTEND_URL/payments?checkout=success&session_id=…  ◀───────────┤
 POST /payments/sync {sessionId} ──────────────────▶ retrieve session ───────────────▶
                                                      payment_status=paid → status "paid"
                                         POST /payments/webhook ◀──── checkout.session.completed
                                         (signature checked, same update, idempotent)
```

`/payments/sync` and the webhook do the same idempotent update, so payments are recorded even if the browser closes
early (webhook) or the webhook is not set up yet (sync on return / Refresh button).

### 15.3 Payment states

```
              POST /payments/checkout
 (no row) ───────────────────────────────▶ pending ──── customer pays ───────────▶ paid     (final; visit shows as paid)
                                              │
                                              └──── session expires (24 h) ───────▶ expired  (a new checkout creates a new row)
```

| Visit state shown in the UI | Meaning |
|---|---|
| `unpaid` | Checked visit with no open or paid payment |
| `pending` | A Checkout page was created and is still open (it is reused if you click Pay again) |
| `paid` | Stripe confirmed payment; counted as `collected` in revenue analytics |

### 15.4 Setup

1. Create a Stripe account and copy the **test** secret key (`sk_test_…`) into `STRIPE_SECRET_KEY`.
2. Local webhook: `stripe listen --forward-to localhost:4000/api/payments/webhook` and copy the printed `whsec_…`
   into `STRIPE_WEBHOOK_SECRET`. In production add an endpoint in the Stripe dashboard for
   `https://<api-host>/api/payments/webhook` with events `checkout.session.completed`,
   `checkout.session.async_payment_succeeded`, `checkout.session.expired`.
3. Set `STRIPE_CURRENCY` (default `inr`) and `FRONTEND_URL`, restart the server.
4. Test card: `4242 4242 4242 4242`, any future expiry, any CVC.

### 15.5 Rules

* Amount = the fee snapshot stored when the doctor checked the patient (`appointments.checked_fee`); visits checked before
  snapshots existed fall back to the doctor's current fee. No fee → 400.
* One paid payment per visit (409 after that). An unfinished Checkout page is reused instead of creating duplicates.
* Amounts are sent in the currency's minor unit (×100); zero-decimal currencies such as JPY are not supported yet.
* Without `STRIPE_SECRET_KEY` the list and summary still work; starting a payment answers 503.
* The webhook verifies Stripe's signature over the raw request bytes (`Stripe-Signature` header); invalid or missing
  signatures get 400, a missing `STRIPE_WEBHOOK_SECRET` gets 503.
* Stripe calls are blocking HTTP requests, so they run in a worker thread and do not stall other requests.
