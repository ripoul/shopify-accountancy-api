# Shopify Accountancy API

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)
![Django REST Framework](https://img.shields.io/badge/DRF-3.17-red?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-psycopg3-4169E1?logo=postgresql&logoColor=white)
![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?logo=astral&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

A REST API for Shopify-connected accountancy. It automatically syncs orders from your store, computes margins, and keeps a cash and bank ledger up to date via auto-generated transactions.

> The frontend application lives at [ripoul/shopify-accountancy](https://github.com/ripoul/shopify-accountancy).

## Features

- **Shopify sync** — import orders and products via the Shopify GraphQL API
- **Margin calculation** — purchase cost, net margin, after-tax result (30%), Shopify payment fees
- **Auto transactions** — every paid order automatically creates a `CashTransaction` and a `BankTransaction`
- **Taxes** — VAT rate management per product
- **Suppliers & purchases** — supplier tracking, product variants with distributor price
- **JWT auth** — access/refresh token authentication with refresh token rotation
- **Object-level permissions** — store-scoped access via `django-guardian`
- **OpenAPI docs** — Swagger UI and ReDoc

## Getting started

### Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL (optional — SQLite is used by default)

### Installation

```bash
git clone https://github.com/<you>/shopify-accountancy-api.git
cd shopify-accountancy-api

uv sync
```

### Configuration

Create a `.env` file at the project root:

```env
SECRET_KEY=your-secret-key

# Optional — SQLite is used if omitted
DATABASE_URL=postgres://user:password@localhost:5432/shopify_accountancy

CORS_ALLOWED_ORIGINS=http://localhost:3000

SHOPIFY_API_KEY=your-api-key
SHOPIFY_API_SECRET=your-api-secret
SHOPIFY_REDIRECT_URI=http://localhost:8000/auth/callback
SHOPIFY_SCOPES=read_all_orders,read_orders,read_products,read_returns
```

### Running the project

```bash
uv run manage.py migrate
uv run manage.py runserver
```

The API is available at `http://localhost:8000`.
Browse the full API reference at [http://localhost:8000/docs/](http://localhost:8000/docs/).

## Pre-commit hooks

The project uses [pre-commit](https://pre-commit.com/) to enforce linting and formatting before every commit. Install the hooks once after cloning:

```bash
uv run pre-commit install
```

From that point on, `ruff check` and `ruff format` run automatically on every `git commit`. You can also trigger them manually:

```bash
uv run pre-commit run --all-files
```

## Tests

```bash
# Run all tests
pytest

# Run a single file
pytest core/tests/views/test_order.py

# Run a single test
pytest core/tests/views/test_order.py::TestOrderViewSet::test_list

# With coverage
coverage run -m pytest && coverage report
```

## Lint & format

```bash
ruff check .
ruff format .
```
