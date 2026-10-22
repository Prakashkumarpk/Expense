# Smart Expense Tracker

React + Vite frontend and FastAPI backend for a step-by-step expense tracker.

## Phase 3: Supabase PostgreSQL persistence

Phase 3 replaces the Phase 2 in-memory dictionary with a PostgreSQL `expenses` table hosted by Supabase. The existing React UI and API paths remain unchanged. Existing in-memory records are not migrated automatically; they disappeared when the old backend stopped and must be entered again if needed.

Authentication is intentionally not implemented yet. The schema includes a nullable `user_id` reference to `auth.users` as a transition point for Phase 4. It must become required and be populated from the authenticated user before production multi-user use.

## Supabase setup

1. Create or open a Supabase project.
2. Open the SQL Editor and run the complete contents of [database/schema.sql](database/schema.sql).
3. In Supabase, open **Connect** and copy a PostgreSQL connection URI. For a typical local IPv4 network, choose the **Session pooler** connection. It works with normal short-lived `psycopg` connections and is usually reachable when the direct database host requires IPv6.
4. A direct connection is simplest for a long-running server when your network supports Supabase's direct host (often IPv6). A transaction pooler is designed mainly for serverless/short-lived transactions and is not needed for this beginner-friendly local setup.
5. Copy `backend/.env.example` to `backend/.env` and replace the placeholder password and host details. Never commit `.env` or paste credentials into chat.

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

The application reads `DATABASE_URL` with `python-dotenv`. It never prints the connection string. If the variable is missing or PostgreSQL is unavailable, API requests return HTTP `503`; the server does not silently fall back to memory.

## Database design

`database/schema.sql` creates one table with an identity-generated integer ID, positive `numeric(12,2)` amount, required category/date, optional note, automatic timezone-aware `created_at`, and nullable `user_id`. A category check constraint protects the same supported category list used by the API. Indexes support date ordering and future user ownership queries.

## Run the backend on port 8001

From the project root, open PowerShell:

```powershell
cd D:\Projects\Expense\backend
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

If the virtual environment does not exist yet:

```powershell
cd D:\Projects\Expense\backend
py -m venv venv
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Health check: `http://127.0.0.1:8001/api/health`
Interactive API docs: `http://127.0.0.1:8001/docs`

## Run the frontend

In a second PowerShell window:

```powershell
cd D:\Projects\Expense\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The existing frontend already calls `http://127.0.0.1:8001/api/expenses`.

## Request flow

`React form -> fetch() -> FastAPI route -> Pydantic validation -> parameterized SQL -> PostgreSQL -> FastAPI response -> React refresh`.

POST uses `INSERT ... RETURNING` so PostgreSQL supplies the ID and `created_at`. GET uses `SELECT`, ordered newest first. PUT uses `UPDATE ... RETURNING` and preserves the original creation timestamp. DELETE uses `DELETE ... RETURNING` to distinguish a successful deletion from a missing ID. Every SQL value is passed separately as a parameter (`%s`), preventing user input from being treated as SQL.

Each request opens a short-lived connection with `psycopg`, uses context managers to close cursors/connections, and commits successful writes. Technical database errors are logged on the backend without exposing credentials to the browser.

## Testing plan

Use a harmless test record such as amount `12.34`, category `Food`, date `2026-10-22`, and note `Phase 3 test`; delete it when finished.

1. Set `DATABASE_URL`, run `database/schema.sql`, and start FastAPI on port 8001.
2. Open `/docs` and call GET `/api/expenses`. A successful response verifies the connection and returns an array.
3. POST a test expense and save its returned integer ID.
4. GET the collection and GET `/api/expenses/{id}`.
5. PUT the same ID with a changed amount or note.
6. Try amount `0` and a negative amount; both should return `422` before a database write.
7. Try GET, PUT, and DELETE with an ID that does not exist; each should return `404`.
8. DELETE the test expense.
9. Restart FastAPI and call GET again. A previously saved record should still exist because it is stored in Supabase, not process memory.
10. Repeat create/edit/delete from the React UI and confirm the table refreshes after each successful operation.

The backend syntax check and frontend build can run without credentials. Full CRUD/database verification requires your real Supabase `DATABASE_URL`, so it must not be claimed until that manual setup is complete.

Phase 1's `/api/health` endpoint and Phase 2's API paths, validation, response fields, and frontend behavior are preserved. Authentication, AI, file uploads, and Phase 4 are intentionally not included.
