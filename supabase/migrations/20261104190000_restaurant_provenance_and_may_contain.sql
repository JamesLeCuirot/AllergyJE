-- Where each restaurant's data came from, so it can be checked and refreshed.
alter table public.restaurants
  add column if not exists import_slug text unique,          -- key used by Tools/importers to re-import
  add column if not exists menu_url text,                    -- the restaurant's own menu page
  add column if not exists allergen_info_url text,           -- the restaurant's own allergen information
  add column if not exists allergen_info_date date;          -- the version date printed on it

comment on column public.restaurants.allergen_info_url is
  'Restaurants without allergen information stay inactive (hidden from the app) until it is added.';

-- Allergen menus distinguish "contains" from "may contain" (labelled ingredients, or
-- cross-contamination). Existing rows are all "contains". Versions of the app that ignore
-- this column treat every link as "contains", which errs on the safe side.
alter table public.menu_item_allergens
  add column if not exists level text not null default 'contains';

alter table public.menu_item_allergens
  drop constraint if exists menu_item_allergens_level_check;
alter table public.menu_item_allergens
  add constraint menu_item_allergens_level_check check (level in ('contains', 'may_contain'));

create unique index if not exists menu_item_allergens_item_allergen_key
  on public.menu_item_allergens (menu_item_id, allergen_id);
