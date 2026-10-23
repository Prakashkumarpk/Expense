# Smart Expense Tracker

React + Vite frontend and FastAPI backend for a step-by-step expense tracker.

## Phase 4: Authentication and user data security

Phase 4 adds Supabase Auth, protected React dashboard access, verified FastAPI JWT authentication, and user-owned expenses. The existing expense paths and payloads remain:

- `POST /api/expenses`
- `GET /api/expenses`
- `GET /api/expenses/{id}`
- `PUT /api/expenses/{id}`
- `DELETE /api/expenses/{id}`

The frontend uses the official `@supabase/supabase-js` client. Supabase persists the session in the browser and broadcasts auth changes across tabs. The FastAPI backend does not trust a `user_id` request field: it verifies the bearer token and takes the user UUID from the token subject.

## Complete the Supabase database setup

The existing Phase 3 schema has a nullable `user_id` because old rows may have been created before authentication. Run the complete [database/schema.sql](database/schema.sql) in the Supabase SQL Editor. It is additive: it creates the table if needed, adds the ownership column if needed, creates indexes, enables RLS, and creates owner policies. It does not delete data or assign ownerless records.

To inspect existing ownerless rows in SQL Editor:

```sql
select id, amount, date, created_at from public.expenses where user_id is null;
```

Do not assign those rows to an arbitrary user. Options are: archive/delete them only after confirmation, or manually map each row to the correct Supabase Auth user. After every row has a verified owner, run [database/phase4_require_ownership.sql](database/phase4_require_ownership.sql) to enforce `user_id not null`. That migration deliberately stops with an error if ownerless rows remain.

Enable email/password authentication in Supabase Dashboard ? Authentication ? Providers ? Email. Decide whether **Confirm email** is enabled. When enabled, registration creates the account but returns no active session until the user clicks the confirmation link; the app displays that instruction. When disabled for local learning, registration can sign in immediately.

## Environment configuration

Backend-only `backend/.env`:

```powershell
cd D:\Projects\Expense
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Set `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_JWT_AUDIENCE=authenticated`. The backend derives the issuer and JWKS URL from `SUPABASE_URL`; optional overrides are documented in the example. Never expose `DATABASE_URL`, database passwords, signing secrets, or service-role keys to the browser.

Frontend-only `frontend/.env`:

```powershell
Copy-Item frontend\.env.example frontend\.env
notepad frontend\.env
```

Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (or the public anon key), and `VITE_API_URL=http://127.0.0.1:8001/api`. A publishable/anon key is intended for browser use but is not a substitute for backend authorization. `.env` files are ignored by Git; the example files contain placeholders only.

## Run the applications on the existing ports

Backend, port 8001:

```powershell
cd D:\Projects\Expense\backend
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Frontend:

```powershell
cd D:\Projects\Expense\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API docs are at `http://127.0.0.1:8001/docs`.

## Authentication and data flow

1. React calls Supabase `signUp` or `signInWithPassword`.
2. Supabase returns a session containing an access token. The client persists it and listens for cross-tab `onAuthStateChange` events.
3. The protected dashboard calls FastAPI with `Authorization: Bearer <access-token>`.
4. FastAPI's `get_current_user_id` obtains the signing key from Supabase's JWKS endpoint and verifies the JWT signature, issuer, audience, expiry, and UUID subject. It returns `401` for missing/invalid/expired tokens and logs no token contents.
5. Each SQL query includes `user_id = %s`. POST writes the verified subject; the request body cannot choose an owner. GET, PUT, and DELETE can only see or change that user's rows, returning `404` for another user's ID.
6. The response returns to React and the dashboard reloads the user's list.

The RLS policies use `auth.uid()` for Supabase client access. The FastAPI backend uses a direct PostgreSQL/pooler connection and its database role does not automatically receive Supabase's `auth.uid()` request context; a privileged database role may bypass RLS. Therefore RLS alone is not claimed as protection for backend requests. The verified JWT dependency and explicit owner filters are the backend protection. Never place a service-role key in frontend code.

## Testing

Use two test accounts with passwords of at least six characters. Do not paste credentials into chat.

1. Register and sign in as User A.
2. Create an expense, refresh, and confirm it remains.
3. Open a second tab and confirm it sees the same session/dashboard.
4. Sign out in one tab and confirm the second tab becomes signed out. Copying/opening a dashboard URL after logout should show login.
5. Sign in as User B and create a separate expense.
6. Try User B's expense ID while authenticated as User A. GET, PUT, and DELETE should return `404`.
7. Call an expense endpoint without `Authorization`; it should return `401`.
8. Try amount `0` or a negative amount; validation should return `422`.
9. Restart FastAPI, sign in again, and verify saved expenses remain in PostgreSQL.
10. Inspect the backend logs to confirm authentication failures are recorded without passwords or tokens.

Credential-free checks completed locally: backend syntax check passed, frontend production build passed, public health endpoint returned `200`, missing bearer authentication returned `401`, and invalid amount validation returned `422`. Supabase registration, cross-tab behavior, and two-user isolation are not claimed as tested until real Supabase configuration and test accounts are supplied locally.

Phase 5 has not been started.
