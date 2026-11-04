# Restaurant imports

Restaurants and menus to load into the app's Supabase database, with where each came from.

| File | What it is |
| --- | --- |
| `restaurants.csv` | One row per restaurant: contact details, location, its own menu page, and (if it publishes one) its allergen information and that document's version date. |
| `menus/<slug>.csv` | The menu loaded into the app: `category, dish, description, price`, then one column per allergen (`Y` contains, `M` may contain, blank doesn't). |
| `details/<slug>*.csv` | Descriptions and prices read from the restaurant's menu pages. |
| `aliases/<slug>.csv` | Where a restaurant names a dish differently on its allergen menu and its menu page. |
| `charts-on-hold/<slug>.csv` | A restaurant's own allergen chart, read correctly but not used, because the chart contradicts itself too often (see below). |

**Allergens are only ever stored from the restaurant's own information.** Every imported
restaurant is listed in the app (`is_listed = true`), but only one with an
`allergen_info_url` gets allergen rows and `is_active = true`. For one without, the app
(1.1 and later) shows allergens it estimates from the dish names, labelled as estimates,
and never marks a dish as safe. `is_active` stays false for those because builds before 1.1
list `is_active` restaurants and read "no allergens listed" as allergen-free. Menu dishes
that aren't on the allergen menu (specials, set menus, different portion sizes) are left out
of a restaurant with allergen data for the same reason.

## Sources

| Restaurant | Allergen information | Version | SHA-256 of the file used |
| --- | --- | --- | --- |
| Beresford House | [Allergen menu PDF](https://media-service.tpagency.com/media/jpr/2026/08/07fd10a6-e7db-4ac2-b852-b76c05ea7727.pdf), linked from https://beresford-house.com/allergens | 12 August 2026 | `08f704dc0634f0b76e43edcc2030ac195334c3dec91ad7c095f332cc4441d9b7` |
| The Moorings Hotel & Restaurant | [Allergen matrix PDF](https://www.themooringshotel.com/wp-content/uploads/2026/10/Allergen-Matrix-151026.pdf), linked from https://www.themooringshotel.com/restaurant/ | 15 October 2026 | `65832684c6b87eda638ab3fd7d8636f993dd925c5877559b8ee87b2257912be4` |
| Café Ubé (Jersey Airport, airside and landside) | [Allergen chart PDF](https://media-service.tpagency.com/media/jpr/2026/10/6b0df503-ac87-40fc-ae7d-0de2cefec20a.pdf), linked from https://jprestaurants.com/cafe-ube/ | 26 October 2026 | read by `Tools/importers/venues/cafe-ube.py` |
| PizzaExpress St Helier and St Brelade (one shared menu, `menus/pizzaexpress-jersey.csv`) | [Allergen guide PDF](https://content-cdn.pizzaexpress.com/files/lj3txstz/production/add3fef9032910e30e9952aa716a9d30f7c164ab.pdf), linked from https://www.pizzaexpress.com/jersey-st-helier | 1 November 2026 | read by `Tools/importers/venues/pizzaexpress.py` |
| The Loft: Pizzeria & Coffeehouse, St Aubin | [Allergen chart PDF](https://www.theloft.je/_files/ugd/190ce0_6a159832614e4ed3a4890962ad5c7e26.pdf), linked from https://www.theloft.je/ | 11 May 2026 | read by `Tools/importers/venues/the-loft.py` |
| Blakes, St Helier | [Menu with allergen codes](https://irp.cdn-website.com/cd44ce23/files/uploaded/Blakes_Menu_08_26.pdf) (day and evening) | 21 August 2026 | read by `Tools/importers/venues/blakes.py` |
| Bar Levant, St Helier | [Menu with allergen codes](https://barlevant.je/wp-content/uploads/2026/08/UPDATED-Bar-Levant-Menu-2026.pdf) | 28 August 2026 | read by `Tools/importers/venues/bar-levant.py` |
| Oyster Box, Jersey Crab Shack, and 28 more | None we can use (see below). Menu only, shown with estimated allergens; see `menu_url` in `restaurants.csv` | | |

### Published a chart, but not used: Samphire

**Samphire** publishes an [allergen chart](https://www.samphire.je/build/img/slider/Autumn-2026.pdf)
(Autumn 2026). `Tools/importers/venues/samphire.py` reads it, and the reading matches the
rendered page, but the chart itself isn't safe to put live yet:
- It has no key, so nobody knows whether its "x" marks mean "contains" or "may contain".
- Its wording contradicts it on 7 of 33 dishes: Lemon Sole (no fish), crab croquettes (no
  crustaceans), Grilled Octopus (no molluscs), Oyster - Tempura (no gluten), celeriac
  (no celery), Bearnaise and Arancini (no milk).
- Hand cut chips have no marks at all. Vegan ice cream is marked with milk. Lupin is
  marked on 11 rows, including Bearnaise and the cheese course.

When a chart is this wrong where it can be checked, it can't be trusted on dishes whose
names give nothing away. Samphire stays menu-only (shown with estimates), with no
`allergen_info_url`, until the restaurant answers. Its reading of the chart is in `charts-on-hold/samphire.csv`.

### Also not used: Quayside, Sorrento, Salty Dog, Cheffins, Hotel de France, Poplars and Sands

**Quayside** publishes codes on its [à la carte](https://quaysidejersey.co.uk/uploads/2026_Quayside_ALa_Carte_Menu.pdf),
Express and Tennerfest menus. It uses its own key, printed out of line with its numbers.
- **Menus disagree:** 13 of the 14 dishes on both the Tennerfest and another menu have
  different codes. On 12 of them the Tennerfest version lists something the à la carte
  doesn't: peanuts on both duck dishes, celery on six dishes, mustard on three, sulphites on
  four, and gluten on two.
- **Contradicted by its own wording:** 6 dishes on the menus we read, e.g. Petit Fruit de
  Mer has smoked salmon and oyster but no fish or molluscs, and Tempura Prawns come with
  goma (sesame) sauce but no sesame.

Quayside is listed menu-only, with estimates.


**Sorrento** ([Summer 2026 menu with codes](http://www.sorrento.je/wp-content/uploads/2026/06/D1549-Sorrento-Summer-Menu-2026.pdf)).
The wording contradicts the codes on 6 of 52 dishes, two of them about nuts:
- Italian ice cream with *pistacchio* has no nuts, and the *torrone* semifreddo has no nuts.
- Carpaccio di Polpo has mayo but no egg.
- Capesante alla St Jacques has prawns but no crustaceans.
- Sartu' di riso has mozzarella but no milk.
- Spaghetti alla Nerano is coded sesame (12) instead of gluten (2).

Sorrento is listed menu-only, with estimates.

**Salty Dog** ([takeaway menu with codes, Jan 2026](https://saltydogbistro.com/wp-content/uploads/2026/01/Salty-Kitchen-Takeaway-ALLERGY-JAN-26-WEB.pdf)).
- **Contradictions:** 7 of 33 dishes. Some are vegan dishes, where the milk may be a dairy-free substitute; others aren't (the artichoke gnocchi, and the king prawn sauce with no crustaceans).
- **Out of date:** 14 of its dishes are no longer on the takeaway menu at food.je.

Salty Dog isn't listed until there's a current chart.

**Cheffins at the Beaumont Inn** publishes codes on five menus (à la carte, desserts,
Sunday, set and Christmas) with its own key: 1 Soy, 2 Celery … 6 Gluten … 14 Tree nuts.
- **Contradicted by its own wording:** 17 of 108 dishes. Fruits of the Sea has crab and
  prawns but no crustaceans. The Sunday sea bass has no fish. The prawn & leek pies have no
  crustaceans. The crème brûlées, tarte tatin and pavlova have no egg. The walnut sticky
  toffee pudding and the praline desserts have no tree nuts.
- **Inconsistent:** the Christmas scallop codes look copied from another dish, and pine
  nuts are coded on one menu and not another.

Listed menu-only, with estimates.

**Hotel de France (La Terrasse)** writes allergens in words under each dish, on a dozen
menus.
- **Contradicted by its own wording:** 7 dishes, e.g. French onion soup with cheddar
  rarebit but no milk, grilled fish with brown butter but no milk, and Yorkshire pudding
  with no egg.
- **Menus disagree:** the same dish is listed with different allergens on about 20 dishes.
  The roast rump of lamb has celery on three menus but not on the main one. French onion
  soup, fish & chips and the Chicken Caesar burger differ between two main menus.

Listed menu-only, with estimates. Its reading keeps every version of each dish, so the
most cautious set (everything any menu lists) can be built from it.

**The Poplars Tea Room** (codes, standard key):
- The chart reads cleanly, with one contradiction: chicken mayonnaise with no egg.
- It is seasonal and closed until spring, so it isn't listed. Re-read the menu when it
  reopens.

**Sands, Discovery Bay** lists dishes under each allergen. It isn't listed:
- The page dates from September 2025.
- Its dairy list misses cheese burgers, buttermilk, butter and yoghurt.
- It has no peanuts entry.

To put any of these live once the restaurant has confirmed (for Quayside, which codes are right):
1. Fix or confirm the points above.
2. Run its script with `--out Imports/menus/<slug>.csv`.
3. Set `allergen_info_url` and `allergen_info_date`.
4. Review as usual.

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

Fill in coordinates, by hand or with `python3 Tools/importers/geocode.py`, so the app can
tell when someone is at the restaurant. Nominatim rarely finds full addresses; the
restaurant's own website often embeds its coordinates.

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
