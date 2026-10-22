-- Phase 3: persistent expense storage for Supabase PostgreSQL.
create table if not exists public.expenses (
    id integer generated always as identity primary key,
    amount numeric(12, 2) not null check (amount > 0),
    category text not null check (category in (
        'Food', 'Petrol', 'Snacks', 'Recharge', 'Groceries', 'Clothes',
        'Transport', 'Bills', 'Health', 'Entertainment', 'Other'
    )),
    date date not null,
    note text,
    created_at timestamptz not null default now(),
    user_id uuid references auth.users(id) on delete set null
);

create index if not exists expenses_date_idx on public.expenses (date desc);
create index if not exists expenses_user_id_idx on public.expenses (user_id);
