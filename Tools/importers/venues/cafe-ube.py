#!/usr/bin/env python3
"""Café Ubé (Jersey Airport, JP Restaurants) allergen chart → Imports/menus/cafe-ube.csv.

Source: "Cafe Ube Allergens - 26 Oct 2026" (3 pages, exported from Excel). The café's
page links the same file as "ALLERGEN MENU":
  https://media-service.tpagency.com/media/jpr/2026/10/6b0df503-ac87-40fc-ae7d-0de2cefec20a.pdf

Why a venue script: the generic allergen_matrix_pdf.py reads each rotated header *line*
as a column. Here eight headers print on two lines ("2. CEREALS CONTAINING" / "GLUTEN
(WHEAT)", "14. SULPHUR DIOXIDE" / "/ SULPHITES"), so it finds lines 8pt apart, takes
that as the column spacing, and then reports real marks as "not under a column".

Layout (pages 1-2; page 3 repeats the header and holds the key):
  * 19 columns, header text rotated 90°, each label centred over its column (pitch 22.9pt):
      1. CELERY · 2. CEREALS CONTAINING GLUTEN (WHEAT / RYE / BARLEY / OATS / SPELT /
      KHORASAN WHEAT) · 3. CRUSTACEANS · 4. EGG · 5. FISH · 6. LUPIN · 7. MILK ·
      8. MOLLUSC · 9. MUSTARD · 10. TREE NUTS · 11. PEANUTS · 12. SESAME · 13. SOYA ·
      14. SULPHUR DIOXIDE / SULPHITES
  * Each printed row sits on a full-width shaded band. Dish rows are Calibri 6.7pt with one
    mark per column; main headings are Calibri Bold 10.9pt (BREAKFAST & POTS), sub-headings
    Calibri Bold 9.2pt (PASTRIES); a long heading runs on over the empty mark columns.
  * One italic note row (under PRE-PACKAGED PRODUCTS) is not a dish.
  * Key, as printed on page 3:
      ✓ = CONTAINS ALLERGEN
      □ = CONTAINS INGREDIENT WITH A LABEL THAT INDICATES IT MAY CONTAIN ALLERGEN
    "-" fills every other cell. The key doesn't define it; it's read as "not marked".

Output: ✓ → Y, □ → M, - → blank. The six gluten cereal columns become Gluten (Y if any ✓,
else M if any □) and TREE NUTS becomes Nuts. category is the nearest heading above the dish
(a sub-heading, or the main heading when no sub-heading follows it), as printed; it
carries over from page 1 to page 2. description and price stay blank: the chart prints
neither and the café's page has no dish menu.

The script stops rather than guess when the chart doesn't match this layout: unexpected
headers or key, a glyph that isn't ✓ □ -, a mark away from every column, text it can't
place, or a repeated (category, dish). A dish with an empty cell is held back from the CSV
and listed, because an empty cell can't be read as "doesn't contain".

Usage:
  python3 Tools/importers/venues/cafe-ube.py cafeube_allergens_26oct2026.pdf \
      [--out Imports/menus/cafe-ube.csv]

Prints every dish with its marks in printed column order, for checking against the PDF.
Needs pdfplumber.
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter

import pdfplumber

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

# The chart's columns left to right, as normalised header text → CSV allergen.
COLUMNS = [
    ("1 CELERY", "Celery"),
    ("2 CEREALS CONTAINING GLUTEN WHEAT", "Gluten"),
    ("2 CEREALS CONTAINING GLUTEN RYE", "Gluten"),
    ("2 CEREALS CONTAINING GLUTEN BARLEY", "Gluten"),
    ("2 CEREALS CONTAINING GLUTEN OATS", "Gluten"),
    ("2 CEREALS CONTAINING GLUTEN SPELT", "Gluten"),
    ("2 CEREALS CONTAINING GLUTEN KHORASAN WHEAT", "Gluten"),
    ("3 CRUSTACEANS", "Crustaceans"),
    ("4 EGG", "Eggs"),
    ("5 FISH", "Fish"),
    ("6 LUPIN", "Lupin"),
    ("7 MILK", "Milk"),
    ("8 MOLLUSC", "Molluscs"),
    ("9 MUSTARD", "Mustard"),
    ("10 TREE NUTS", "Nuts"),
    ("11 PEANUTS", "Peanuts"),
    ("12 SESAME", "Sesame"),
    ("13 SOYA", "Soybeans"),
    ("14 SULPHUR DIOXIDE SULPHITES", "Sulphur Dioxide"),
]
SHORT = ["CEL", "WHE", "RYE", "BAR", "OAT", "SPE", "KHO", "CRU", "EGG", "FIS", "LUP", "MIL",
         "MOL", "MUS", "TRE", "PEA", "SES", "SOY", "SUL"]

KEY = [  # normalised key lines expected on the PDF
    "✓ = CONTAINS ALLERGEN",
    "□ = CONTAINS INGREDIENT WITH A LABEL THAT INDICATES IT MAY CONTAIN ALLERGEN",
]
VALUE = {"✓": "Y", "□": "M", "-": ""}
RANK = {"": 0, "M": 1, "Y": 2}

MARK_TOLERANCE = 4.0  # pt between a mark's centre and its column's centre (pitch is 22.9)


def fail(message):
    sys.exit(f"STOPPED: {message}")


def norm_label(text):
    return " ".join(re.findall(r"[A-Z0-9]+", text.upper()))


def font(char):
    return char["fontname"].split("+")[-1]


def centre(char):
    return (char["x0"] + char["x1"]) / 2


def header_columns(page):
    """Columns from the rotated header labels: [(centre x, label)], left to right."""
    rotated = sorted((c for c in page.chars if not c["upright"]), key=lambda c: c["x0"])
    if not rotated:
        return [], 0
    # A label is a run of rotated glyphs; its two lines are 1.8pt apart, labels 7.7pt+ apart.
    labels = [[rotated[0]]]
    for char in rotated[1:]:
        if char["x0"] - max(c["x1"] for c in labels[-1]) < 4:
            labels[-1].append(char)
        else:
            labels.append([char])
    found = []
    for chars in labels:
        lines = []  # lines of one label: glyphs whose x ranges overlap
        for char in sorted(chars, key=lambda c: c["x0"]):
            if lines and char["x0"] < max(c["x1"] for c in lines[-1]) - 1:
                lines[-1].append(char)
            else:
                lines.append([char])
        # Text rotated 90° anticlockwise reads bottom to top.
        text = " ".join("".join(c["text"] for c in sorted(line, key=lambda c: -c["top"])) for line in lines)
        x = (min(c["x0"] for c in chars) + max(c["x1"] for c in chars)) / 2
        found.append((x, norm_label(text)))
    return found, max(c["bottom"] for c in rotated)


def text_lines(chars, tolerance=1.0):
    rows = []
    for char in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        if rows and abs(rows[-1][0]["top"] - char["top"]) <= tolerance:
            rows[-1].append(char)
        else:
            rows.append([char])
    return [sorted(row, key=lambda c: c["x0"]) for row in rows]


def line_text(chars):
    return " ".join("".join(c["text"] for c in chars).split())


def check_key(page):
    """The key lines (anything with ' = ') must be exactly the two expected."""
    lines = [line_text(l) for l in text_lines([c for c in page.chars if c["upright"]])]
    key = [l for l in lines if " = " in l]
    if key != KEY:
        fail(f"page {page.page_number}: key reads {key}, expected {KEY}")
    return lines


def read(path):
    dishes, held, notes, key_page, other_text = [], [], [], None, []
    category = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            n = page.page_number
            cols, header_bottom = header_columns(page)
            labels = [label for _, label in cols]
            if labels != [label for label, _ in COLUMNS]:
                fail(f"page {n}: header columns are {labels}")
            xs = [x for x, _ in cols]
            pitch = sorted(b - a for a, b in zip(xs, xs[1:]))[len(xs) // 2]
            name_edge = xs[0] - pitch / 2

            body = [c for c in page.chars if c["upright"] and c["top"] > header_bottom]
            bands = sorted((r for r in page.rects if r["top"] >= header_bottom - 1
                            and r["x0"] < 20 and r["x1"] > 590 and r["bottom"] - r["top"] > 4),
                           key=lambda r: r["top"])
            if not bands:  # the key page: no chart rows
                if any(" = " in l for l in (line_text(x) for x in text_lines(body))):
                    lines = check_key(page)
                    key_page = n
                    other_text += [l for l in lines if " = " not in l and l.replace(" ", "") not in ("", "ALLERGENMENU")]
                    continue
                fail(f"page {n}: no chart rows and no key")

            # Group text lines into printed rows by the band each sits on (joins wrapped names).
            rows = {}
            for line in text_lines(body):
                if not "".join(c["text"] for c in line).strip():
                    continue
                mid = (line[0]["top"] + line[0]["bottom"]) / 2
                band = [i for i, r in enumerate(bands) if r["top"] <= mid <= r["bottom"]]
                if len(band) != 1:
                    fail(f"page {n} y={line[0]['top']:.1f}: '{line_text(line)}' isn't on one row band")
                rows.setdefault(band[0], []).append(line)

            for index in sorted(rows):
                lines = sorted(rows[index], key=lambda l: l[0]["top"])
                chars = [c for l in lines for c in l if c["text"].strip()]
                fonts = {(font(c), round(c["size"], 1)) for c in chars}
                whole = " ".join(line_text(l) for l in lines)
                y = lines[0][0]["top"]
                if all(f == "Calibri-Bold" and s >= 9 for f, s in fonts):
                    category = whole  # heading, as printed (may run on over empty columns)
                    continue
                if all(f == "Calibri-Italic" for f, _ in fonts):
                    notes.append(f"p{n} [{category}] {whole}")
                    continue
                name_chars = [c for c in chars if centre(c) < name_edge]
                mark_chars = [c for c in chars if centre(c) >= name_edge]
                if {(font(c), round(c["size"], 1)) for c in name_chars} != {("Calibri", 6.7)}:
                    fail(f"page {n} y={y:.1f}: unexpected row '{whole}' fonts {fonts}")
                name = " ".join(" ".join("".join(c["text"] for c in l if centre(c) < name_edge).split())
                                for l in lines).strip()
                cells = [[] for _ in cols]
                for char in mark_chars:
                    near = [i for i, x in enumerate(xs) if abs(centre(char) - x) <= MARK_TOLERANCE]
                    if len(near) != 1:
                        fail(f"page {n} '{name}': '{char['text']}' at x={centre(char):.1f} isn't under a column")
                    cells[near[0]].append(char["text"])
                glyphs = []
                for i, cell in enumerate(cells):
                    if len(cell) > 1 or (cell and cell[0] not in VALUE):
                        fail(f"page {n} '{name}': column {COLUMNS[i][0]} holds {cell}")
                    glyphs.append(cell[0] if cell else "")
                dish = {"page": n, "y": y, "category": category, "dish": name, "glyphs": glyphs}
                missing = [COLUMNS[i][0] for i, g in enumerate(glyphs) if not g]
                if missing:
                    dish["missing"] = missing
                    held.append(dish)
                else:
                    dishes.append(dish)
    if key_page is None:
        fail("no key found")
    return dishes, held, notes, other_text


def labels(glyphs):
    out = {a: "" for a in ALLERGENS}
    for glyph, (_, allergen) in zip(glyphs, COLUMNS):
        value = VALUE[glyph]
        if RANK[value] > RANK[out[allergen]]:
            out[allergen] = value
    return out


def show(glyphs):
    return " ".join(g or "_" for g in glyphs)


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default=os.path.join(root, "Imports", "menus", "cafe-ube.csv"))
    args = parser.parse_args()

    dishes, held, notes, other_text = read(args.pdf)

    seen = Counter((d["category"], d["dish"]) for d in dishes + held)
    repeated = [pair for pair, count in seen.items() if count > 1]
    if repeated:
        fail(f"repeated (category, dish): {repeated}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for dish in dishes:
            row = labels(dish["glyphs"])
            writer.writerow([dish["category"], dish["dish"], "", ""] + [row[a] for a in ALLERGENS])

    print("Marks in printed column order:", " ".join(SHORT))
    for dish in dishes:
        print(f"p{dish['page']} [{dish['category']}] {dish['dish']}\n      {show(dish['glyphs'])}")
    print(f"\n{len(dishes)} dishes written to {args.out}")
    if held:
        print("\nHELD BACK (an empty cell; ask the café):")
        for dish in held:
            print(f"  p{dish['page']} [{dish['category']}] {dish['dish']}: no mark under {', '.join(dish['missing'])}"
                  f"\n      {show(dish['glyphs'])}")
    if notes:
        print("\nNotes printed in the chart (not dishes):", *notes, sep="\n  ")
    if other_text:
        print("\nOther text on the key page:", *other_text, sep="\n  ")


if __name__ == "__main__":
    main()
