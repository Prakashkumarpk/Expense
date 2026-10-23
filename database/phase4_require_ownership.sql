-- Run this only after reviewing existing ownerless rows.
-- It intentionally fails instead of assigning those rows to an arbitrary user.
do $$
begin
    if exists (select 1 from public.expenses where user_id is null) then
        raise exception 'Migration stopped: expenses without user_id still exist. Review, archive, or remove them explicitly first.';
    end if;
end
$$;

alter table public.expenses alter column user_id set not null;
