#!/usr/bin/env python3
"""PizzaExpress allergen guide (England, Scotland, Wales and Jersey) -> Imports/menus CSV.

Source: PizzaExpress "Allergen Information - England, Scotland, Wales and Jersey",
November 2026 V1, 46 pages (pizzaexpress_allergen_info_EngScotWalesJersey_Nov2026_V1.pdf).

Layout of the guide (780 x 540 pt landscape pages, a drawn table on each page):
  pp 1-4    introduction, key and contents (no table)
  pp 5-19   DISHES: starters, sides, salads, Al Forno, pizzas, desserts, Dolcetti and the
            Piccolo (kids') menu. Page 19 also holds PICCOLO DRINKS, which is left out.
  pp 20-27  INGREDIENTS: single ingredients. Only the dips (rows named "... Dip ...") are
            taken from here.
  pp 28-37  DRINKS (left out)
  pp 38-46  Breakfast, "Selected Restaurants Only" (left out: nothing in the guide says
            the Jersey pizzerias serve it)

Key, as printed on page 2: "If a dish contains an allergen in its ingredients, a '✓' will
appear in the corresponding allergen column. A '*' indicates that an ingredient is
produced in a factory where the allergen is present and where we believe there is a
significant risk of cross-contamination."
  ✓ (Wingdings U+F0FC)  -> Y
  *                     -> M
  both in one cell      -> Y (only Baked Vanilla Cheesecake: "✓ Wheat * Oats" under Gluten)
Small print under a mark ("Wheat", "In Dressing", "Barley & Wheat", "In Hot Green
Peppers"...) says which ingredient or cereal it comes from. It does not change the mark.
Text in a cell with no ✓ or * stops the import, because the meaning of that cell is unclear.
Gluten is a single column; the cereal is printed under the mark, so no sub-columns need merging.

category is the text of the section bar as printed (the dips get "INGREDIENTS"). dish is
the name cell as printed, with its lines joined. "- NEW" and bracketed notes such as
"[Dine-Out Exclusive]" are kept; only a dangling trailing dash is dropped.

Columns, left to right: dish name, Milk/Dairy, Fish, Crustaceans, Molluscs, Cereals
Containing Gluten, Sulphur Dioxide / Sulphites, Egg, Sesame Seeds, Mustard, Soybeans, Lupin,
Celery, Peanuts, Tree Nuts | Vegetarian, Vegan, Coeliacs | Please note. The suitability and
note columns are ignored.

How the table is read: the green header cells give each column's x range and its rotated
label, and every page must name all 14 allergens. The dish-name cells give each row's y
range and the dark bars give the section headings. Every character in the table body must
fall inside a known cell. If one doesn't, the import stops.

Rows whose allergen cells are replaced by "Due to the nature of this pizza, we cannot
guarantee any allergen or dietary requirements." (Create Your Own, Duo Romana) are left
out: the chart gives no allergen data for them.

Usage:
  python3 Tools/importers/venues/pizzaexpress.py guide.pdf \
      [--out Imports/menus/pizzaexpress-jersey.csv] [--dump PAGE]

Prints every dish with its marks and the small print under them, then the rows it left out.
--dump PAGE prints the raw characters of each cell on that page, to check them against the PDF.
"""
import argparse
import csv
import re
import sys

import pdfplumber
from pdfplumber.utils import extract_text

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

# Header labels exactly as printed (rotated text, lines joined with a space).
COLUMN_LABELS = {
    "Milk/Dairy": "Milk",
    "Fish": "Fish",
    "Crustaceans": "Crustaceans",
    "Molluscs": "Molluscs",
    "Cereals Containing Gluten": "Gluten",
    "Sulphur Dioxide / Sulphites": "Sulphur Dioxide",
    "Egg": "Eggs",
    "Sesame Seeds": "Sesame",
    "Mustard": "Mustard",
    "Soybeans": "Soybeans",
    "Lupin": "Lupin",
    "Celery": "Celery",
    "Peanuts": "Peanuts",
    "Tree Nuts": "Nuts",
    "Vegetarian": None,
    "Vegan": None,
    "Coeliacs": None,
}

TICK = ""   # Wingdings tick
STAR = "*"

DISH_PAGES = range(5, 20)          # 1-based, inclusive of 19
INGREDIENT_PAGES = range(20, 28)   # 20-27
EXCLUDED_SECTIONS = {"PICCOLO DRINKS"}
DIP = re.compile(r"\bDip\b")
NO_DATA = "cannot guarantee any allergen"

HEADER_FILL = (0.663, 0.82, 0.557)   # header cells and dish-name cells
SECTION_FILL = (0.22, 0.341, 0.137)  # dark green section bars

LIGATURES = {"ﬁ": "fi", "ﬂ": "fl"}


def same_colour(a, b):
    return isinstance(a, tuple) and len(a) == len(b) and all(abs(x - y) < 0.02 for x, y in zip(a, b))


def rotated(char):
    a, _, _, d, _, _ = char["matrix"]
    return abs(a) < 0.1 and abs(d) < 0.1


def centre(char):
    return (char["x0"] + char["x1"]) / 2, (char["top"] + char["bottom"]) / 2


def inside(char, x0, x1, top, bottom):
    x, y = centre(char)
    return x0 <= x < x1 and top <= y < bottom


def clean(text):
    for lig, plain in LIGATURES.items():
        text = text.replace(lig, plain)
    return " ".join(text.split())


def text_of(chars):
    """Text of a cell, its lines joined with spaces."""
    return clean(extract_text(sorted(chars, key=lambda c: (c["top"], c["x0"])), x_tolerance=1.5))


class Problem(Exception):
    pass


def header(page, number):
    """(dish column, [(x0, x1, label, allergen or None)], note column, header bottom)."""
    cells = [r for r in page.rects if 60 < r["height"] < 120 and r["top"] < 80 and r["width"] < 400]
    cells.sort(key=lambda r: r["x0"])
    if not cells:
        raise Problem(f"page {number}: no header row")
    bottom = cells[0]["bottom"]
    if any(abs(r["bottom"] - bottom) > 1 for r in cells):
        raise Problem(f"page {number}: header cells don't line up")
    dish, note, middle = cells[0], cells[-1], cells[1:-1]
    columns = []
    for r in middle:
        chars = [c for c in page.chars if rotated(c) and inside(c, r["x0"], r["x1"], r["top"], r["bottom"])]
        # The labels read top to bottom; a two-line label is two runs, right-hand run first.
        runs = {}
        for c in chars:
            runs.setdefault(round(c["x0"]), []).append(c)
        label = clean(" ".join("".join(c["text"] for c in sorted(run, key=lambda c: c["top"]))
                               for _, run in sorted(runs.items(), reverse=True)))
        if label not in COLUMN_LABELS:
            raise Problem(f"page {number}: unknown column heading {label!r}")
        columns.append((r["x0"], r["x1"], label, COLUMN_LABELS[label]))
    found = [c[3] for c in columns if c[3]]
    if sorted(found) != sorted(ALLERGENS):
        raise Problem(f"page {number}: allergen columns are {found}")
    for a, b in zip(columns, columns[1:]):
        if abs(a[1] - b[0]) > 0.5:
            raise Problem(f"page {number}: gap between columns {a[2]} and {b[2]}")
    if abs(dish["x1"] - columns[0][0]) > 0.5 or abs(columns[-1][1] - note["x0"]) > 0.5:
        raise Problem(f"page {number}: dish or note column doesn't meet the allergen columns")
    return dish, columns, note, bottom


def body_rows(page, number, dish, bottom):
    """Dish rows and section bars below the header, top to bottom: (kind, top, bottom)."""
    rows = []
    for r in page.rects:
        if r["top"] < bottom - 0.5 or abs(r["x0"] - dish["x0"]) > 1:
            continue
        fill = r.get("non_stroking_color")
        if same_colour(fill, SECTION_FILL) and r["width"] > 500:
            rows.append(("section", r["top"], r["bottom"], r["x1"]))
        elif same_colour(fill, HEADER_FILL) and abs(r["x1"] - dish["x1"]) < 1:
            rows.append(("dish", r["top"], r["bottom"], r["x1"]))
    rows.sort(key=lambda r: r[1])
    for a, b in zip(rows, rows[1:]):
        if b[1] < a[2] - 0.5:
            raise Problem(f"page {number}: rows overlap at y={b[1]:.1f}")
    return rows


def read_cell(chars):
    """(mark, small print) for one allergen cell. mark is 'Y', 'M' or ''."""
    ticks = [c for c in chars if c["text"] == TICK]
    stars = [c for c in chars if c["text"] == STAR]
    rest = [c for c in chars if c["text"] not in (TICK, STAR)]
    small = text_of(rest)
    if ticks:
        mark = "Y"
    elif stars:
        mark = "M"
    else:
        mark = ""
    return mark, small, len(ticks), len(stars)


def read(path, dump_page=None):
    dishes, skipped, notes = [], [], []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 46:
            raise Problem(f"expected 46 pages, found {len(pdf.pages)}")
        intro = clean(pdf.pages[37].extract_text() or "")
        if "Breakfast at PizzaExpress" not in intro or "Selected Restaurants Only" not in intro:
            raise Problem("page 38 is no longer the breakfast introduction: page ranges have moved")
        category = None
        for number in list(DISH_PAGES) + list(INGREDIENT_PAGES):
            page = pdf.pages[number - 1]
            dish, columns, note, bottom = header(page, number)
            rows = body_rows(page, number, dish, bottom)
            if not rows:
                raise Problem(f"page {number}: no rows")
            left, right = dish["x0"], note["x1"]
            # Space characters are kept so that words stay apart; they never count as marks.
            body = [c for c in page.chars if not rotated(c)
                    and inside(c, left - 2, right + 2, bottom, rows[-1][2] + 2)]
            used = set()
            for kind, top, bot, _ in rows:
                in_row = [c for c in body if inside(c, left, right, top, bot)]
                used.update(id(c) for c in in_row)
                if kind == "section":
                    category = text_of(in_row)
                    if number in INGREDIENT_PAGES and category != "INGREDIENTS":
                        raise Problem(f"page {number}: unexpected section {category!r}")
                    continue
                name = text_of([c for c in in_row if inside(c, dish["x0"], dish["x1"], top, bot)])
                name = re.sub(r"\s*[–-]$", "", name)  # "Blue Cheese Dip Pot [Dine-Out Exclusive] –"
                if not name:
                    raise Problem(f"page {number}: a row with no dish name at y={top:.1f}")
                cells = {}
                for x0, x1, label, allergen in columns:
                    chars = [c for c in in_row if inside(c, x0, x1, top, bot)]
                    cells[label] = (allergen, chars)
                spanning = text_of([c for c in in_row if inside(c, columns[0][0], columns[-1][1], top, bot)])
                note_text = text_of([c for c in in_row if inside(c, note["x0"], note["x1"], top, bot)])
                if dump_page == number:
                    print(f"\n[{category}] {name}  (row y {top:.1f}-{bot:.1f})")
                    for x0, x1, label, _ in columns:
                        chars = [c for c in cells[label][1] if c["text"].strip()]
                        if chars:
                            raw = " ".join(f"{'TICK' if c['text'] == TICK else c['text']}@({centre(c)[0]:.1f},{centre(c)[1]:.1f})" for c in chars)
                            print(f"   {label:28} x {x0:.1f}-{x1:.1f}: {raw}")
                entry = {"page": number, "category": category, "dish": name, "labels": {}, "small": {}, "note": note_text}
                if NO_DATA in spanning:
                    skipped.append((number, category, name, f"no allergen data: \"{spanning}\""))
                    continue
                if category in EXCLUDED_SECTIONS:
                    skipped.append((number, category, name, "drink"))
                    continue
                if number in INGREDIENT_PAGES and not DIP.search(name):
                    continue  # an ingredient, not a dip
                for label, (allergen, chars) in cells.items():
                    mark, small, n_ticks, n_stars = read_cell(chars)
                    if small and not mark:
                        raise Problem(f"page {number} '{name}': text {small!r} in {label} with no ✓ or *")
                    if n_ticks > 1 or n_stars > 1 or (n_ticks and n_stars):
                        notes.append(f"p{number} '{name}' {label}: {n_ticks} ✓ and {n_stars} * ({small}) -> {mark}")
                    if allergen is None:
                        continue
                    if mark:
                        if allergen in entry["labels"]:
                            raise Problem(f"page {number} '{name}': two columns for {allergen}")
                        entry["labels"][allergen] = mark
                    if small:
                        entry["small"][allergen] = small
                dishes.append(entry)
            stray = [c for c in body if id(c) not in used and c["text"].strip()]
            if stray:
                raise Problem(f"page {number}: text outside the table cells: {text_of(stray)!r}")
    seen = set()
    for d in dishes:
        key = (d["category"], d["dish"])
        if key in seen:
            raise Problem(f"'{d['dish']}' appears twice in '{d['category']}'")
        seen.add(key)
    return dishes, skipped, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default="Imports/menus/pizzaexpress-jersey.csv")
    parser.add_argument("--dump", type=int, metavar="PAGE", help="print each cell's raw characters on PAGE")
    args = parser.parse_args()

    try:
        dishes, skipped, notes = read(args.pdf, args.dump)
    except Problem as problem:
        sys.exit(f"Stopped: {problem}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for d in dishes:
            # The guide lists the dips among its single ingredients; file them as a menu section.
            category = "DIPS" if d["category"] == "INGREDIENTS" else d["category"]
            writer.writerow([category, d["dish"], "", ""] + [d["labels"].get(a, "") for a in ALLERGENS])

    for d in dishes:
        contains = [a for a in ALLERGENS if d["labels"].get(a) == "Y"]
        may = [a for a in ALLERGENS if d["labels"].get(a) == "M"]
        line = f"p{d['page']} [{d['category']}] {d['dish']}: {', '.join(contains) or '-'}"
        if may:
            line += f"  (may contain: {', '.join(may)})"
        if d["small"]:
            line += "  {" + "; ".join(f"{a}: {t}" for a, t in d["small"].items()) + "}"
        if not d["labels"]:
            line += "  NO ALLERGENS"
        print(line)
    print(f"\n{len(dishes)} dishes written to {args.out}")
    if skipped:
        print("\nLeft out:", *(f"p{p} [{c}] {n}: {why}" for p, c, n, why in skipped), sep="\n  ")
    if notes:
        print("\nCells with more than one mark:", *notes, sep="\n  ")


if __name__ == "__main__":
    main()
