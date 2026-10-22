import logging
import os
from datetime import date, datetime
from typing import Optional

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# Read DATABASE_URL from backend/.env during local development.
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

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


def database_connection():
    """Open one short-lived PostgreSQL connection for a request."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not configured")
        raise HTTPException(status_code=503, detail="Database is not configured. Set DATABASE_URL in backend/.env.")
    try:
        return psycopg.connect(DATABASE_URL)
    except psycopg.Error:
        # Log technical details on the server, but do not expose credentials to clients.
        logger.exception("Could not connect to PostgreSQL")
        raise HTTPException(status_code=503, detail="Database is unavailable. Check the backend database configuration.")


def row_to_expense(row) -> Expense:
    """Convert a SQL result tuple into the response model."""
    return Expense(id=row[0], amount=float(row[1]), category=row[2], date=row[3], note=row[4], created_at=row[5])


@app.get("/api/health")
def health_check():
    """Preserve the Phase 1 API health response."""
    return {"status": "ok", "message": "Expense Tracker API is running"}


@app.post("/api/expenses", response_model=Expense, status_code=status.HTTP_201_CREATED)
def create_expense(expense_input: ExpenseInput):
    """Insert a validated expense and return the database-generated record."""
    query = """
        INSERT INTO expenses (amount, category, date, note)
        VALUES (%s, %s, %s, %s)
        RETURNING id, amount, category, date, note, created_at
    """
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (expense_input.amount, expense_input.category, expense_input.date, expense_input.note))
                return row_to_expense(cursor.fetchone())
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not create expense")
        raise HTTPException(status_code=503, detail="Could not save the expense because the database is unavailable.")


@app.get("/api/expenses", response_model=list[Expense])
def list_expenses():
    """Read all expenses from PostgreSQL, newest first."""
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, amount, category, date, note, created_at FROM expenses ORDER BY created_at DESC, id DESC")
                return [row_to_expense(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not list expenses")
        raise HTTPException(status_code=503, detail="Could not load expenses because the database is unavailable.")


@app.get("/api/expenses/{expense_id}", response_model=Expense)
def read_expense(expense_id: int):
    """Read one expense by its integer primary key."""
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, amount, category, date, note, created_at FROM expenses WHERE id = %s", (expense_id,))
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
def update_expense(expense_id: int, expense_input: ExpenseInput):
    """Update editable fields and preserve the database ID and creation time."""
    query = """
        UPDATE expenses
        SET amount = %s, category = %s, date = %s, note = %s
        WHERE id = %s
        RETURNING id, amount, category, date, note, created_at
    """
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (expense_input.amount, expense_input.category, expense_input.date, expense_input.note, expense_id))
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
def delete_expense(expense_id: int):
    """Delete one expense and keep the existing response shape."""
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM expenses WHERE id = %s RETURNING id", (expense_id,))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail=f"Expense with id {expense_id} was not found")
                return {"message": f"Expense {expense_id} deleted successfully"}
    except HTTPException:
        raise
    except psycopg.Error:
        logger.exception("Could not delete expense %s", expense_id)
        raise HTTPException(status_code=503, detail="Could not delete the expense because the database is unavailable.")
