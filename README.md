# AttendX

AttendX is a full-stack smart teacher attendance system with separate Teacher and Student workspaces. Teachers create classes, manage rosters, open short-lived attendance QR sessions, correct records, review analytics, and export CSV/PDF reports. Students scan a QR from an enrolled class and receive server-side validation, duplicate protection, history, and below-75% alerts.

## Project structure

```text
attendex/
├─ backend/
│  ├─ app/                 # FastAPI application, models, auth, routers
│  ├─ migrations/          # Alembic migration environment and revisions
│  ├─ tests/               # API integration tests
│  ├─ requirements.txt
│  └─ seed.py
└─ frontend/
   ├─ src/                 # React + TypeScript UI and API client
   ├─ package.json
   └─ vite.config.ts
```

## Requirements

- Windows PowerShell
- Python 3.12+
- Node.js 20+ and npm
- PostgreSQL 14+ for a shared/production database

The backend also runs against SQLite for a quick local evaluation. PostgreSQL is the documented deployment database.

## PostgreSQL setup (PowerShell)

Open PowerShell and run the following commands. Adjust the password if your local PostgreSQL policy requires it.

```powershell
Set-Location "C:\Users\Krishna rathor\Documents\attendex"
psql -U postgres -c "CREATE USER attendx WITH PASSWORD 'attendx';"
psql -U postgres -c "CREATE DATABASE attendx OWNER attendx;"
```

If the role/database already exists, PostgreSQL will report that and you can continue.

## Backend setup and startup

```powershell
Set-Location "C:\Users\Krishna rathor\Documents\attendex\backend"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python seed.py
python -m uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive documentation is at `http://localhost:8000/docs` and the health check is `http://localhost:8000/health`.

### SQLite-only local evaluation

Use this instead of the PostgreSQL `.env` value when PostgreSQL is not available:

```powershell
Set-Location "C:\Users\Krishna rathor\Documents\attendex\backend"
Copy-Item .env.example .env
(Get-Content .env) -replace '^DATABASE_URL=.*', 'DATABASE_URL=sqlite:///./attendx.db' | Set-Content .env
python -m alembic upgrade head
python seed.py
python -m uvicorn app.main:app --reload --port 8000
```

## Frontend setup and startup

Open a second PowerShell window:

```powershell
Set-Location "C:\Users\Krishna rathor\Documents\attendex\frontend"
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. `VITE_API_URL` defaults to `http://localhost:8000/api` and can be changed in `frontend/.env`.

## Sample accounts

After `python seed.py`:

- Teacher: `teacher@attendx.local` / `Teacher@123`
- Student: `student@attendx.local` / `Student@123`

Change or remove these accounts before deploying to a shared environment.

## Tests and verification

Backend API tests use an isolated SQLite database and cover registration/login, teacher setup, enrollment, QR scanning, and duplicate prevention:

```powershell
Set-Location "C:\Users\Krishna rathor\Documents\attendex\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Build the production frontend bundle with:

```powershell
Set-Location "C:\Users\Krishna rathor\Documents\attendex\frontend"
npm run build
```

## Security notes

- Passwords are stored as bcrypt hashes; passwords are never returned by the API.
- JWTs carry user identity and role, and every protected route re-checks the current user from the database.
- QR tokens are random, time-limited, server-verified, and invalidated when a new session is opened or a teacher closes a session.
- The unique `(session_id, student_id)` constraint and an explicit server check prevent duplicate attendance.
- CORS, JWT secret, database URL, frontend origin, and QR lifetime are environment-configurable.
- Manual corrections and attendance scans are written to the audit log.
