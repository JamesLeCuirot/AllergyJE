#!/usr/bin/env python3
"""Samphire (7-11 Don Street, St Helier): read its allergen chart into Imports/menus/samphire.csv.

Source: "Autumn 2026" allergen chart, one A4 page exported from Excel, linked from
https://www.samphire.je/menus/%C3%A0-la-carte-1-1 as
https://www.samphire.je/build/img/slider/Autumn-2026.pdf
(SHA-256 d6a149374e880d4e8aaf25a426a088cd8b006e05c0334065617bdbfd2623cee8).

Layout: dish names down the left, 15 rotated column headings ("1.Celery" ... "14. Sulphur
Dioxide", then "15 onion, garlic, chives, leek", which is not one of the 14 allergens and is
skipped). Sections are separated by yellow bands with no heading text, so category is blank.

The chart prints NO key. What the cells hold, and how they are written:
  ✓                      Y. The usual "contains" tick.
  x / X                  Y, but unconfirmed. Without a key it can't be shown whether x means
                         "contains" or "may contain"; Y is the stricter of the two. Every x in
                         an allergen column is listed when the script runs.
  a word, in "2. Cereals Containing Gluten" ("wheat", "Wheat + Rye") or "10. Tree Nuts"
  ("walnuts", "Almonds + hazelnut")
                         Y. The word names which cereal or nut.
Anything else in a cell stops the script, so a changed chart can't be read wrongly.

A row with marks but no dish name is reported and left out. Descriptions and prices come
from the restaurant's menu page (--menu), only for the dishes listed in MENU_MATCHES.

Usage:
  python3 Tools/importers/venues/samphire.py samphire-allergens.pdf \
      [--menu Imports/details/samphire.csv] [--out Imports/charts-on-hold/samphire.csv]
Needs pdfplumber.
"""
import argparse
import csv
import hashlib
import sys

import pdfplumber
from pdfplumber.utils import extract_text

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

EXPECTED_SHA256 = "d6a149374e880d4e8aaf25a426a088cd8b006e05c0334065617bdbfd2623cee8"

# Column headings exactly as printed, left to right, and the app allergen each one is.
COLUMNS = [
    ("1.Celery", "Celery"),
    ("2. Cereals Containing Gluten", "Gluten"),
    ("3. Crustaceans (shrimp paste)", "Crustaceans"),
    ("4. Egg", "Eggs"),
    ("5. Fish", "Fish"),
    ("6. Lupin", "Lupin"),
    ("7.Milk", "Milk"),
    ("8. Molluscs", "Molluscs"),
    ("9. Mustard", "Mustard"),
    ("10. Tree Nuts", "Nuts"),
    ("11. Peanuts", "Peanuts"),
    ("12. Sesame Seeds", "Sesame"),
    ("13. Soya", "Soybeans"),
    ("14. Sulphur Dioxide", "Sulphur Dioxide"),
    ("15 onion, garlic, chives, leek", None),  # not one of the 14 allergens
]

TICK = "✓"
X_MARKS = {"x", "X"}
X_MEANS = "Y"  # no key on the chart; see the docstring
# Words that name the cereal or nut, and the only columns they may appear in.
WORD_MARKS = {
    "Gluten": {"wheat", "wheat + rye"},
    "Nuts": {"walnuts", "almonds + hazelnut"},
}

# Chart name -> dish on the restaurant's menu page, where it is clearly the same dish.
# Left out on purpose: Sourdough (the menu has a "Homemade bread roll", which may or may not
# be it), the three steak sauces and the sides (no menu entry of their own), and the
# desserts other than Cheese (the menu page lists different desserts).
MENU_MATCHES = {
    "Oysters - Natural": "Jersey Oysters (Natural)",
    "Oyster - Tempura": "Jersey Oysters (Tempura)",
    "crab croquettes": "Brown Crab Croquette",
    "Lobster roll": "Lobster & Brioche Roll",
    "Arancini": "Arancini",
    "Beef tartare": "Beef Tartare",
    "Truffle Linguinie": "Truffle Linguine",
    "tuna": "Bluefin Tuna",
    "Beetroot Salad": "Baby Beetroot Salad",
    "Grilled Octopus": "Octopus",
    "Scallop": "Jersey Hand-Dived Scallops",
    "brill": "Roast Brill on the bone",
    "sea bass": "Wild Jersey Sea Bass",
    "Lemon Sole": "Grilled Lemon Sole",
    "Lobster": "Grilled Lobster",
    "venison": "Venison",
    "beef fillet": "Beef Fillet",
    "celeriac": "Baked Celeriac",
    "mushroom rice": "Slow-cooked wild mushroom rice",
    "Cheese": "Selection of Cheese",
}

YELLOW = (1.0, 1.0, 0.0)


def fail(message):
    sys.exit(f"samphire.py: {message}")


def centre_in(obj, x0, x1, top, bottom):
    cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
    return x0 <= cx < x1 and top <= cy < bottom


def heading(chars):
    """Text rotated 90° anticlockwise: lines run left to right, characters bottom to top."""
    lines = {}
    for c in chars:
        lines.setdefault(round(c["x0"], 1), []).append(c)
    text = " ".join("".join(c["text"] for c in sorted(line, key=lambda c: -c["top"]))
                    for _, line in sorted(lines.items()))
    return " ".join(text.split())


def read(path):
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 1:
            fail(f"expected one page, found {len(pdf.pages)}")
        page = pdf.pages[0]
        # Excel draws its grid as thin filled rectangles.
        xs = sorted(r["x0"] for r in page.rects if r["width"] < 1 and r["height"] > 300)
        hlines = sorted(r["top"] for r in page.rects if r["height"] < 1 and r["width"] > 400)
        bands = [(r["top"], r["bottom"]) for r in page.rects
                 if tuple(r["non_stroking_color"] or ()) == YELLOW]
        if len(xs) != len(COLUMNS) + 2:
            fail(f"expected {len(COLUMNS) + 2} vertical rules, found {len(xs)}")
        name_col = (xs[0], xs[1])
        cells = list(zip(xs[1:], xs[2:]))

        header_bottom = hlines[1]
        stray = [c for c in page.chars if not centre_in(c, xs[0], xs[-1], hlines[0], hlines[-1])]
        if stray:
            fail(f"text outside the table: {''.join(c['text'] for c in stray)!r}")
        for (x0, x1), (expected, _) in zip(cells, COLUMNS):
            label = heading([c for c in page.chars if centre_in(c, x0, x1, 0, header_bottom)])
            if label != expected:
                fail(f"column heading {label!r} where {expected!r} was expected")

        rows, orphans, notes = [], [], []
        section = 1  # counted, not named: the bands carry no heading
        for top, bottom in zip(hlines[1:], hlines[2:]):
            in_chars = [c for c in page.chars if centre_in(c, name_col[0], xs[-1], top, bottom)]
            yellow = any(b_top <= (top + bottom) / 2 < b_bottom for b_top, b_bottom in bands)
            if yellow:
                if in_chars:
                    fail(f"text in a yellow band near y={top:.0f}")
                section += 1
                continue
            name = " ".join(extract_text([c for c in in_chars if centre_in(c, *name_col, top, bottom)]).split())
            labels, raw = {}, []
            for (x0, x1), (column, allergen) in zip(cells, COLUMNS):
                text = " ".join(extract_text([c for c in in_chars if centre_in(c, x0, x1, top, bottom)]).split())
                if not text:
                    continue
                raw.append((column, text))
                if text == TICK:
                    value = "Y"
                elif text in X_MARKS:
                    value = X_MEANS
                    if allergen:
                        notes.append(f"'{name or '(no name)'}': '{text}' under {column}; no key on the chart, written as {X_MEANS}")
                elif allergen in WORD_MARKS and text.lower() in WORD_MARKS[allergen]:
                    value = "Y"
                    notes.append(f"'{name or '(no name)'}': '{text}' under {column}; written as Y")
                else:
                    fail(f"'{name}': unrecognised cell '{text}' under {column}")
                if allergen:
                    labels[allergen] = value
            if not name:
                if raw:
                    orphans.append(f"section {section}, row at y={top:.1f}-{bottom:.1f}, has marks but no dish name: "
                                   + ", ".join(f"{t} under {c}" for c, t in raw))
                continue
            rows.append({"dish": name, "labels": labels, "section": section, "top": top, "bottom": bottom})
    return rows, orphans, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--menu", help="menu details CSV (category,dish,description,price), e.g. Imports/details/samphire.csv")
    parser.add_argument("--out", default="Imports/charts-on-hold/samphire.csv")
    parser.add_argument("--any-version", action="store_true",
                        help="read a PDF other than the one this script was checked against")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EXPECTED_SHA256 and not args.any_version:
        fail(f"{args.pdf} isn't the Autumn 2026 chart this script was checked against "
             f"(SHA-256 {digest}). Check the new chart by eye, then run with --any-version.")

    rows, orphans, notes = read(args.pdf)

    seen = set()
    for row in rows:
        if row["dish"] in seen:
            fail(f"'{row['dish']}' appears twice")
        seen.add(row["dish"])

    menu = {}
    if args.menu:
        with open(args.menu, newline="", encoding="utf-8") as f:
            menu = {r["dish"]: r for r in csv.DictReader(f)}
        for chart_name, menu_name in MENU_MATCHES.items():
            if chart_name not in seen:
                fail(f"MENU_MATCHES names '{chart_name}', which isn't on the chart")
            if menu_name not in menu:
                fail(f"MENU_MATCHES names '{menu_name}', which isn't in {args.menu}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for row in rows:
            details = menu.get(MENU_MATCHES.get(row["dish"], ""), {})
            writer.writerow(["", row["dish"], details.get("description", ""), details.get("price", "")]
                            + [row["labels"].get(a, "") for a in ALLERGENS])

    section = None
    for row in rows:
        if row["section"] != section:
            section = row["section"]
            print(f"--- section {section} (no heading printed)")
        contains = [a for a in ALLERGENS if row["labels"].get(a)]
        match = f"  [menu: {MENU_MATCHES[row['dish']]}]" if args.menu and row["dish"] in MENU_MATCHES else ""
        print(f"{row['dish']}: {', '.join(contains) or 'NO MARKS'}{match}")
    print(f"\n{len(rows)} dishes written to {args.out}")
    if notes:
        print("\nCells that aren't a plain tick:", *notes, sep="\n  ")
    if orphans:
        print("\nLeft out:", *orphans, sep="\n  ")


if __name__ == "__main__":
    main()
