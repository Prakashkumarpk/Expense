-- Phase 4 schema/migration. This is additive and does not assign existing rows to a user.
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

-- Safe for the existing Phase 3 table if user_id is not present yet.
alter table public.expenses add column if not exists user_id uuid references auth.users(id) on delete set null;
create index if not exists expenses_date_idx on public.expenses (date desc);
create index if not exists expenses_user_id_idx on public.expenses (user_id);

-- RLS protects Supabase client access. The FastAPI direct database role also filters
-- every query by verified user_id; ordinary direct connections do not automatically
-- make auth.uid() available to PostgreSQL policies.
alter table public.expenses enable row level security;
drop policy if exists "Users can read their own expenses" on public.expenses;
drop policy if exists "Users can insert their own expenses" on public.expenses;
drop policy if exists "Users can update their own expenses" on public.expenses;
drop policy if exists "Users can delete their own expenses" on public.expenses;
create policy "Users can read their own expenses" on public.expenses for select using ((select auth.uid()) = user_id);
create policy "Users can insert their own expenses" on public.expenses for insert with check ((select auth.uid()) = user_id);
create policy "Users can update their own expenses" on public.expenses for update using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Users can delete their own expenses" on public.expenses for delete using ((select auth.uid()) = user_id);
