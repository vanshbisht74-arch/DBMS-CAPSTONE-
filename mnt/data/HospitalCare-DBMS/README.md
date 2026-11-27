# CareCore DB — Hospital Management DBMS Capstone

A Flask + SQLite hospital-management demo adapted from the supplied FinCore DB project. It demonstrates relational design, SQL querying, ACID transactions, optimistic version checks, triggers, RBAC, parameterized queries, indexing, and `EXPLAIN QUERY PLAN`.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The SQLite database is created and seeded automatically as `hospital.db`.

## Demo roles
- **Admin:** read, register patients, schedule appointments, record payments, run insurance and savepoint demos.
- **Receptionist:** read, register patients, schedule appointments, record payments.
- **Doctor:** read-only dashboard and SQL explorer.

## Demo data
Patient IDs 1–5, doctor IDs 1–4, and bill IDs 1–5 are seeded in `hospital_db.sql`. Use MRN1001 for the indexed patient search demo.

## Important scope note
This is an academic demonstration with synthetic data. It is not suitable for real patient records or clinical use. Authentication, production-grade authorization, privacy controls, encryption, backups, and regulatory compliance would be required before any real deployment.
