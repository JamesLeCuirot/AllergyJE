-- Show every imported restaurant in the app, including ones that publish no allergen
-- information, without exposing those to older builds.
--
-- is_active keeps its old meaning: the restaurant's allergen data comes from the
-- restaurant. Builds before 1.1 list only is_active restaurants and read a dish with no
-- allergens as allergen-free, so a menu-only restaurant must never be is_active.
--
-- is_listed is what 1.1 and later list. For a restaurant without its own allergen
-- information, those builds show allergens estimated from the dish names, never "safe".
alter table restaurants add column if not exists is_listed boolean not null default false;
comment on column restaurants.is_listed is
  'Listed in app 1.1+. If allergen_info_url is null the app shows estimated allergens only. is_active must stay false for such restaurants: older builds treat a dish with no allergens as allergen-free.';

create policy "Anyone can view listed restaurants" on restaurants
  for select using (is_listed = true);

-- Dishes in the order the restaurant prints them.
alter table menu_items add column if not exists display_order integer not null default 0;
