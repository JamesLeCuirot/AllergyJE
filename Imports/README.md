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
| The Moorings Hotel & Restaurant | [Allergen matrix PDF](https://www.themooringshotel.com/wp-content/uploads/2026/10/Allergen-Matrix-151026.pdf), linked from https://www.themooringshotel.com/restaurant/ | 15 October 2026 | `65832684c6b87eda638ab3fd7d8636f993dd925c5877559b8ee87b2257912be4` |
| Café Ubé (Jersey Airport, airside and landside) | [Allergen chart PDF](https://media-service.tpagency.com/media/jpr/2026/10/6b0df503-ac87-40fc-ae7d-0de2cefec20a.pdf), linked from https://jprestaurants.com/cafe-ube/ | 26 October 2026 | read by `Tools/importers/venues/cafe-ube.py` |
| PizzaExpress St Helier and St Brelade (one shared menu, `menus/pizzaexpress-jersey.csv`) | [Allergen guide PDF](https://content-cdn.pizzaexpress.com/files/lj3txstz/production/add3fef9032910e30e9952aa716a9d30f7c164ab.pdf), linked from https://www.pizzaexpress.com/jersey-st-helier | 1 November 2026 | read by `Tools/importers/venues/pizzaexpress.py` |
| Oyster Box, Jersey Crab Shack, and 24 more | None published. Menu only, hidden; see `menu_url` in `restaurants.csv` | | |

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
by eye before loading (`pdftoppm -png` renders the pages). `merge_menu_details.py` lists
dishes on the menu that have no allergen data, so you can ask the restaurant about them.

Then check the restaurant's data against the menu's own wording:

```bash
swift run allergy-tools review Imports/menus/<slug>.csv --write Imports/held/<slug>.csv
```

A dish whose name or description shows an allergen for certain that the restaurant's chart
doesn't list (e.g. "Tempura king prawns" with no crustaceans) is held back. It isn't loaded
until the restaurant confirms. `build_import_sql.py` leaves out everything in `held/`. To
release a dish, fix the chart data (or confirm it with the restaurant) and remove its line.

Released after review (the review flagged these, but the chart is right):
- Café Ubé: the oat-milk cappuccino, flat white and latte. They're flagged only because
  "latte" etc. normally mean dairy. The chart lists milk deliberately on the oat-milk
  mocha (its chocolate) and not on these, and the café notes "may contain" separately.
- PizzaExpress: the garlic breads made with vegan mozzarella. "Mozzarella" normally means
  milk, but these are the vegan versions and the chart is right to leave milk off.

Restaurants loaded hidden don't need coordinates yet. Fill them in, by hand or with
`python3 Tools/importers/geocode.py`, when a restaurant goes live.

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
