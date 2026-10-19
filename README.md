# TechPoint POS: Backend

REST API for the TechPoint point-of-sale system (Phase 2). It handles login and
roles, products and categories, stock and restocks, sales, and reports. The
React frontend lives in a separate repository (`pos-system`) and talks to this
API over HTTP.

## Tech stack

| Layer | Technology |
|-------|------------|
| Web framework | Flask |
| Database | PostgreSQL |
| ORM / migrations | Flask-SQLAlchemy, Flask-Migrate (Alembic) |
| Authentication | Flask-JWT-Extended (JWT bearer tokens) |
| Cross-origin requests | Flask-CORS (allows the frontend origin only) |
| Config | python-dotenv (`.env` file) |

## Project structure

    techpoint-backend/
    ├── app.py              # app factory, registers all blueprints
    ├── config.py           # reads settings from .env
    ├── extensions.py       # db, migrate, cors, jwt objects
    ├── models/             # User, Category, Product, Sale, SaleItem,
    │                       # StockMovement, Restock
    ├── routes/             # HTTP layer: auth, categories, products, sales,
    │                       # stock, restocks, reports
    ├── services/           # business logic: sales_service, stock_service
    ├── utils/auth.py       # login_required, manager_required
    ├── migrations/         # database migrations
    ├── tests/              # automated tests
    └── seed.py             # sample data (see warning below)

## Setup

These steps are for Ubuntu / WSL. Run them once, in order.

### 1. Python environment

The project pins its Python version in `.python-version` (used by pyenv).

    cd techpoint-backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

### 2. PostgreSQL

Install it if needed, and make sure the server is running:

    sudo apt update
    sudo apt install postgresql
    sudo service postgresql start
    pg_isready -h localhost -p 5432

Create your own database user and database (choose your own password):

    sudo -u postgres psql -c "CREATE USER techpoint WITH PASSWORD 'choose-a-password';" \
                          -c "CREATE DATABASE techpoint_pos OWNER techpoint;"

Useful commands inside `psql -h localhost -U techpoint -d techpoint_pos`:

    \dt     -- list tables
    \du     -- list users
    \q      -- quit

### 3. Environment file

Create a file named `.env` in the project root. It is private to your machine.
**Never commit it** (it is listed in `.gitignore`).

    DATABASE_URL=postgresql+psycopg://techpoint:choose-a-password@localhost:5432/techpoint_pos
    SECRET_KEY=any-long-random-string
    JWT_SECRET_KEY=another-long-random-string
    FRONTEND_ORIGIN=http://localhost:5173
    FLASK_DEBUG=True
    PORT=5000

| Setting | Meaning |
|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string. `requirements.txt` installs the psycopg 3 driver, hence `postgresql+psycopg://`. |
| `SECRET_KEY`, `JWT_SECRET_KEY` | Random secrets. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `FRONTEND_ORIGIN` | The one address the browser app is allowed to call from. It must match the address the frontend runs on exactly. |
| `FLASK_DEBUG` | `True` for development. |
| `PORT` | Port the API listens on (default 5000). |

There is no default database: if `DATABASE_URL` is missing, the app will not start.

### 4. Create the tables

    flask db upgrade

### 5. (Optional) Sample data

    python seed.py

> **Warning:** `seed.py` first **deletes all rows** in users, categories,
> products, sales, sale items, stock movements, restocks, shifts, suppliers,
> purchase orders, returns, and audit history, then inserts demo
> data. Run it only on a development database. The demo usernames and
> passwords are at the top of `seed.py`.

You can also create users through the API: log in as a manager and call
`POST /api/auth/register`.

### 6. Run the API

    python app.py

Check it: <http://127.0.0.1:5000/api/health> should return
`"database": "connected"`.

## Authentication and roles

1. `POST /api/auth/login` with a username and password returns an
   `access_token`.
2. Send it on every protected request: `Authorization: Bearer <token>`.
3. Two roles exist: `manager` and `cashier`.
   - `login_required`: any logged-in user (manager or cashier)
   - `manager_required`: managers only

| Result | Meaning |
|--------|---------|
| 401 | No token, invalid token, or expired token |
| 403 | Logged in, but the role is not allowed |

Errors use the shape `{"status": "error", "message": "..."}`.

## API reference

### Auth: `/api/auth`

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| POST | `/login` | public | `{username, password}` returns `access_token` and `user` |
| GET | `/me` | login | the current user |
| POST | `/register` | manager | `{username (3+ chars), name, password (8+ chars), role}` |
| POST | `/change-password` | login | `{old_password, new_password}` |
| GET | `/users` | manager | list all users (no password hashes) |

### Products and categories

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/api/products` | public | list products |
| GET | `/api/products/<id>` | public | one product |
| POST | `/api/products` | manager | create. Fields include `title`, `brand`, `barcode`, `unit_cost`, `description`, `price`, `stock_quantity`, `low_stock_threshold`, `thumbnail`, `category_id` |
| PUT | `/api/products/<id>` | manager | update the same fields |
| DELETE | `/api/products/<id>` | manager | archive from the active catalogue while preserving sales and stock history |
| GET / POST | `/api/categories` | see code | list / create |
| GET / PUT | `/api/categories/<id>` | see code | one / update |

### Stock and restocks

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/api/stock` | see code | stock levels |
| GET | `/api/stock/low`, `/api/stock/out` | see code | low and out-of-stock products |
| GET | `/api/stock/movements` | see code | all stock movements |
| GET | `/api/stock/movements/<product_id>` | see code | movements for one product |
| POST | `/api/stock/adjust` | manager | `{product_id, delta, user_id, note}`; stock cannot go below zero |
| POST | `/api/stock/restock` | manager | `{product_id, quantity, user_id, unit_cost, supplier, invoice_number, note}` |
| GET / POST | `/api/restocks` | see code | list / create restocks |
| GET / PUT / DELETE | `/api/restocks/<id>` | see code | one / update details / delete (reverses the stock) |
| GET / POST | `/api/suppliers` | manager | list / create suppliers |
| GET / POST | `/api/purchase-orders` | manager | list / create supplier orders |
| POST | `/api/purchase-orders/<id>/receive` | manager | receive all or selected quantities; updates stock, average cost, restocks, and ledger |
| GET | `/api/shifts/current` | login | current user's open till shift |
| GET | `/api/shifts` | manager | recent shifts and reconciliations |
| POST | `/api/shifts/open` | login | open a till with an opening float |
| POST | `/api/shifts/<id>/cash-movements` | login | record till cash in/out with a reason |
| POST | `/api/shifts/<id>/close` | login | close a shift and calculate expected cash / variance |

### Sales: `/api/sales`

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| POST | `/api/sales` | login | create a sale for the logged-in user |
| GET | `/api/sales` | manager | list all sales, newest first |
| GET | `/api/sales/<id>` | login | one sale |
| POST | `/api/sales/<id>/returns` | manager | partial/full return with refund method, reason, and optional stock return |

Create a sale. The client sends only product ids and quantities, never prices:

    POST /api/sales
    Authorization: Bearer <token>

    {
      "payment_method": "cash",
      "items": [
        {"product_id": 1, "quantity": 2},
        {"product_id": 3, "quantity": 1}
      ]
    }

Response `201`:

    {
      "id": 1,
      "user_id": 2,
      "payment_method": "cash",
      "total_amount": "31.00",
      "created_at": "2026-10-15T22:16:00+03:00",
      "items": [
        {
          "id": 1,
          "sale_id": 1,
          "product_id": 1,
          "product_title": "Test Mouse",
          "quantity": 2,
          "unit_price": "15.50",
          "subtotal": "31.00"
        }
      ]
    }

| Status | When |
|--------|------|
| 400 | no items, non-integer ids or quantities, quantity of zero or less |
| 401 | no or invalid token |
| 404 | a product in the sale does not exist |
| 409 | not enough stock (the message names each product that is short) |

### Reports: `/api/reports`

`/dashboard`, `/summary`, `/gross-margin`, `/sales-by-date`, `/sales-by-cashier`,
`/best-selling-products` (all GET). The role needed for each is defined in
`routes/reports.py`.

`GET /api/audit` returns the latest audited product, stock, sale, return,
purchase order, and till actions to managers. Gross margin is based on the
cost snapshot captured at sale time; sales without recorded costs are counted
as missing cost data.

### Health

`GET /api/health` checks that the API and database are up.

## How a sale is processed

`services/sales_service.py` does the following inside one database transaction:

1. Validates the items and merges duplicate products.
2. Locks the product rows (`SELECT ... FOR UPDATE`, in id order) so two
   cashiers cannot sell the last unit at the same time.
3. Checks stock for every product first, and refuses the whole sale if any
   product is short.
4. Reads each price from the database (the server never trusts a client price)
   and calculates every subtotal and the total with `Decimal`.
5. Creates the sale and its items, lowers stock, and writes a `sale` stock
   movement with before and after values (`deduct_stock` in
   `stock_service.py`).
6. Commits once. If anything fails, everything is rolled back and the stock is
   unchanged.

All amounts are stored in US dollars. The frontend converts to KSh for display
at a fixed rate of 130.

## Try it with curl

    # log in (use an account from seed.py or one you registered)
    TOKEN=$(curl -s -X POST http://127.0.0.1:5000/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username": "cashier1", "password": "YOUR-PASSWORD"}' \
      | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

    # make a sale
    curl -X POST http://127.0.0.1:5000/api/sales \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"payment_method": "cash", "items": [{"product_id": 1, "quantity": 2}]}'

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Address already in use` / port 5000 busy | An older copy of the API is still running. Stop it with `Ctrl+C` in its terminal, or find it with `ss -ltnp \| grep 5000`. |
| Frontend shows "Failed to fetch" | Either the API is not running (check `/api/health`), or the frontend runs on a different address than `FRONTEND_ORIGIN` (for example Vite moved from port 5173 to 5174). Make them match and restart the API. |
| `pyenv: version '...' is not installed` | `.python-version` names a Python that pyenv does not have. Install it with `pyenv install <version>`, or activate your `venv` first. |
| App will not start: missing database URL | Create `.env` as shown above. |
| `could not connect to server` | Start PostgreSQL: `sudo service postgresql start`. |

## Known limitations

- Products and users cannot be deleted through the API. Users who have made
  sales cannot simply be removed, so deactivating users would be needed.
- Prices are stored in USD only.
- Automated tests currently cover reports only.

## Working on the project

- Never commit `.env`, database files, or `__pycache__`.
- Work on a feature branch and merge through a pull request into `main`.
- Stage files by name (`git add path/to/file`), not `git add .`.
