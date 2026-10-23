import logging
import os
from datetime import date, datetime
from typing import Optional
from uuid import UUID

import jwt
import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError
from pydantic import BaseModel, Field, field_validator

# Load local settings from backend/.env. Never put this file in source control.
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
JWT_ISSUER = os.getenv("SUPABASE_JWT_ISSUER", f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else "")
JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
JWKS_URL = os.getenv("SUPABASE_JWKS_URL", f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else "")
jwks_client = PyJWKClient(JWKS_URL) if JWKS_URL else None
bearer_scheme = HTTPBearer(auto_error=False)

app = FastAPI(title="Smart Expense Tracker API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CATEGORIES = {"Food", "Petrol", "Snacks", "Recharge", "Groceries", "Clothes", "Transport", "Bills", "Health", "Entertainment", "Other"}


class ExpenseInput(BaseModel):
    amount: float = Field(..., gt=0, description="Must be greater than zero")
    category: str = Field(..., min_length=1)
    date: date
    note: Optional[str] = None

    @field_validator("category")
    @classmethod
    def category_must_be_supported(cls, value: str) -> str:
        if value not in CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(sorted(CATEGORIES))}")
        return value


class Expense(ExpenseInput):
    id: int
    created_at: datetime


def get_current_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    """Verify the Supabase access token and return its UUID subject."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("Authentication failed: missing bearer token")
        raise HTTPException(status_code=401, detail="Authentication is required")
    if not JWT_ISSUER or not JWT_AUDIENCE or jwks_client is None:
        logger.error("Supabase JWT verification is not configured")
        raise HTTPException(status_code=503, detail="Authentication is not configured on the backend")

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(credentials.credentials).key
        payload = jwt.decode(
            credentials.credentials,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["sub", "exp", "aud", "iss"]},
        )
        return str(UUID(payload["sub"]))
    except (jwt.PyJWTError, PyJWKClientError, ValueError, KeyError):
        # Do not log the token or other sensitive request data.
        logger.warning("Authentication failed: invalid or expired bearer token")
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")


def database_connection():
    """Open one short-lived PostgreSQL connection for a request."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not configured")
        raise HTTPException(status_code=503, detail="Database is not configured. Set DATABASE_URL in backend/.env.")
    try:
        return psycopg.connect(DATABASE_URL)
    except psycopg.Error:
        logger.exception("Could not connect to PostgreSQL")
        raise HTTPException(status_code=503, detail="Database is unavailable. Check the backend database configuration.")


def row_to_expense(row) -> Expense:
    """Convert a SQL result tuple into the public response model."""
    return Expense(id=row[0], amount=float(row[1]), category=row[2], date=row[3], note=row[4], created_at=row[5])


@app.get("/api/health")
def health_check():
    """Preserve the existing public Phase 1 health response."""
    return {"status": "ok", "message": "Expense Tracker API is running"}


@app.post("/api/expenses", response_model=Expense, status_code=status.HTTP_201_CREATED)
def create_expense(expense_input: ExpenseInput, user_id: str = Depends(get_current_user_id)):
    """Create an expense owned by the verified token subject."""
    query = """
        INSERT INTO expenses (amount, category, date, note, user_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, amount, category, date, note, created_at
    """
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (expense_input.amount, expense_input.category, expense_input.date, expense_input.note, user_id))
                return row_to_expense(cursor.fetchone())
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not create expense for authenticated user")
        raise HTTPException(status_code=503, detail="Could not save the expense because the database is unavailable.")


@app.get("/api/expenses", response_model=list[Expense])
def list_expenses(user_id: str = Depends(get_current_user_id)):
    """Return only expenses owned by the verified token subject."""
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, amount, category, date, note, created_at FROM expenses WHERE user_id = %s ORDER BY created_at DESC, id DESC", (user_id,))
                return [row_to_expense(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not list expenses for authenticated user")
        raise HTTPException(status_code=503, detail="Could not load expenses because the database is unavailable.")


@app.get("/api/expenses/{expense_id}", response_model=Expense)
def read_expense(expense_id: int, user_id: str = Depends(get_current_user_id)):
    """Return one expense only when it belongs to the authenticated user."""
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, amount, category, date, note, created_at FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail=f"Expense with id {expense_id} was not found")
                return row_to_expense(row)
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not retrieve expense %s", expense_id)
        raise HTTPException(status_code=503, detail="Could not retrieve the expense because the database is unavailable.")


@app.put("/api/expenses/{expense_id}", response_model=Expense)
def update_expense(expense_id: int, expense_input: ExpenseInput, user_id: str = Depends(get_current_user_id)):
    """Update editable fields only on an expense owned by the user."""
    query = """
        UPDATE expenses
        SET amount = %s, category = %s, date = %s, note = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, amount, category, date, note, created_at
    """
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (expense_input.amount, expense_input.category, expense_input.date, expense_input.note, expense_id, user_id))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail=f"Expense with id {expense_id} was not found")
                return row_to_expense(row)
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not update expense %s", expense_id)
        raise HTTPException(status_code=503, detail="Could not update the expense because the database is unavailable.")


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, user_id: str = Depends(get_current_user_id)):
    """Delete an expense only when it belongs to the authenticated user."""
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s RETURNING id", (expense_id, user_id))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail=f"Expense with id {expense_id} was not found")
                return {"message": f"Expense {expense_id} deleted successfully"}
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not delete expense %s", expense_id)
        raise HTTPException(status_code=503, detail="Could not delete the expense because the database is unavailable.")


