# POS Flask Backend Starter

## Requirements
Python 3.10+ and PostgreSQL.

## Install (Windows PowerShell)
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Install (Linux/macOS/WSL)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create a PostgreSQL role and database (run as a database administrator):
```sql
CREATE USER pos_user WITH PASSWORD 'replace_with_a_strong_password';
CREATE DATABASE pos_db OWNER pos_user;
```
Update `DATABASE_URL` in `.env` with the real credentials.

## Create and apply migrations
```bash
flask --app app db init
flask --app app db migrate -m "Create initial POS tables"
flask --app app db upgrade
```
Commit `migrations/` to version control after creating it. For a quick fresh local database, `python seed.py` creates tables and idempotently adds demo records.

## Run
```bash
flask --app app run --debug
```
Test `http://127.0.0.1:5000/api/health`.

Demo-only credentials: `manager` / `cashier`, password `ChangeMe123!`. Change/remove before shared use. Never commit `.env`.

Prices use PostgreSQL NUMERIC; sale item unit prices are historical snapshots. API routes and authentication are intentionally left for the relevant team members.
