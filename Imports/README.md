# Restaurant imports

Restaurants and menus to load into the app's Supabase database, with where each came from.

| File | What it is |
| --- | --- |
| `restaurants.csv` | One row per restaurant: contact details, location, its own menu page, and (if it publishes one) its allergen information and that document's version date. |
| `menus/<slug>.csv` | The menu loaded into the app: `category, dish, description, price`, then one column per allergen (`Y` contains, `M` may contain, blank doesn't). |
| `details/<slug>*.csv` | Descriptions and prices read from the restaurant's menu pages. |
| `aliases/<slug>.csv` | Where a restaurant names a dish differently on its allergen menu and its menu page. |

**A restaurant goes live only with allergen data from the restaurant itself.** One without
`allergen_info_url` is loaded hidden (`is_active = false`), and its dish rows carry no
allergens. Otherwise the app, which reads "no allergens listed" as allergen-free, would show
those dishes as safe. Menu dishes that aren't on the allergen menu (specials, set menus,
different portion sizes) are left out for the same reason.

## Sources

| Restaurant | Allergen information | Version | SHA-256 of the file used |
| --- | --- | --- | --- |
| Beresford House | [Allergen menu PDF](https://media-service.tpagency.com/media/jpr/2026/08/07fd10a6-e7db-4ac2-b852-b76c05ea7727.pdf), linked from https://beresford-house.com/allergens | 12 August 2026 | `08f704dc0634f0b76e43edcc2030ac195334c3dec91ad7c095f332cc4441d9b7` |
| Oyster Box | None published (menu only) | | |
| Jersey Crab Shack | None published (menu only) | | |

Source PDFs and pages are downloaded into `sources/` (not committed). Re-download them to rebuild.

## Rebuilding a restaurant from its allergen PDF

Beresford House is the example:

```bash
curl -L -o Imports/sources/beresford-house-allergens.pdf "<allergen pdf url>"
python3 Tools/importers/allergen_matrix_pdf.py Imports/sources/beresford-house-allergens.pdf --out /tmp/bh-allergens.csv
python3 Tools/importers/jprestaurants_menu.py dining-room-menu.html --out Imports/details/beresford-house-dining-room.csv
python3 Tools/importers/merge_menu_details.py /tmp/bh-allergens.csv Imports/details/beresford-house-*.csv --aliases Imports/aliases/beresford-house.csv --out Imports/menus/beresford-house.csv
```

`allergen_matrix_pdf.py` prints every dish with its allergens. Check them against the PDF
by eye before loading. `merge_menu_details.py` lists dishes on the menu that have no
allergen data, so you can ask the restaurant about them.

## Loading into Supabase

```bash
python3 Tools/importers/build_import_sql.py [--only <slug> …] > import.sql
```

Run `import.sql` in the Supabase SQL editor. Each restaurant is replaced in one go, keyed on
its slug, so re-running after a menu change is safe. Then refresh the dataset the predictor
is scored on:

```bash
swift run allergy-tools fetch-supabase --url <project url> --key <anon key>
swift run allergy-tools score
```
