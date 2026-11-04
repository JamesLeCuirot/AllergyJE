-- The app has no sign-in, so "Report an issue" sends reports with no user_id.
-- The old policy required auth.uid() = user_id, which is never true for a signed-out
-- user (NULL = NULL isn't true), so every report was rejected.
--
-- Reports may now come from anyone. Anonymous ones carry no user_id, and signed-in ones
-- only their own. New reports can't mark themselves as reviewed.
drop policy if exists "Users can insert reports" on public.menu_reports;

create policy "Anyone can report a menu problem"
  on public.menu_reports
  for insert
  to anon, authenticated
  with check (
    (user_id is null or user_id = auth.uid())
    and coalesce(status, 'pending') = 'pending'
    and reviewed_at is null
  );
