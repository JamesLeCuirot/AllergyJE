#!/usr/bin/env python3
"""The Loft: Pizzeria & Coffeehouse (La Neuve Route, St Aubin): read its allergen matrix into
Imports/menus/the-loft.csv.

Source: "Allergen Information", three A4 pages made with ReportLab on 11 May 2026, linked
("For a full allergen list. Click here") from https://www.theloft.je/menu as
https://www.theloft.je/_files/ugd/190ce0_6a159832614e4ed3a4890962ad5c7e26.pdf
(SHA-256 65f1dd6806d5a4f3f5c5a54d35760a45fcfdef65f1ca75dabc855102cb11b926).

Layout: one table across the pages, each page repeating the heading row "Item CE GL ... SU".
Sections are shaded rows with a heading; a section carries on across a page break. The key,
printed at the top of page 1:
  ●  Contains this allergen                    -> Y
  ○  May contain (cross-contact possible)      -> M
and the column codes CE Celery, GL Gluten, ... SU Sulphites, which the script reads and checks.

Kept: food, and food add-ons (waffle and egg extras, pizza toppings, crust dips). Left out:
the four drinks sections (DRINK_SECTIONS), which include the milks and syrups for drinks.
Any section the script doesn't know stops it, so a changed chart can't be read wrongly.

Dish names are written as printed, with the "└ " that marks an add-on removed, and a name
that wraps onto a second row of the table joined into one. The chart prints no
descriptions or prices, so those stay blank.

Usage:
  python3 Tools/importers/venues/the-loft.py the-loft-allergens.pdf [--out Imports/menus/the-loft.csv]
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

EXPECTED_SHA256 = "65f1dd6806d5a4f3f5c5a54d35760a45fcfdef65f1ca75dabc855102cb11b926"

# The chart's column codes, in order, with the name its key gives and the app allergen.
COLUMNS = [
    ("CE", "Celery", "Celery"),
    ("GL", "Gluten", "Gluten"),
    ("CR", "Crustaceans", "Crustaceans"),
    ("EG", "Eggs", "Eggs"),
    ("FI", "Fish", "Fish"),
    ("LU", "Lupin", "Lupin"),
    ("MI", "Milk", "Milk"),
    ("MO", "Molluscs", "Molluscs"),
    ("MU", "Mustard", "Mustard"),
    ("NU", "Nuts", "Nuts"),
    ("PN", "Peanuts", "Peanuts"),
    ("SE", "Sesame", "Sesame"),
    ("SY", "Soya", "Soybeans"),
    ("SU", "Sulphites", "Sulphur Dioxide"),
]

# The key as printed: mark, wording, and the colour it's drawn in.
CONTAINS = ("●", "Contains this allergen", (0.72549, 0.109804, 0.109804))
MAY_CONTAIN = ("○", "May contain (cross-contact possible)", (0.85098, 0.466667, 0.023529))
MARKS = {CONTAINS[0]: ("Y", CONTAINS[2]), MAY_CONTAIN[0]: ("M", MAY_CONTAIN[2])}

DRINK_SECTIONS = [
    "HOT DRINKS — COFFEE & TEA",
    "ICED & COLD DRINKS",
    "SMOOTHIES & PROTEIN SHAKES",
    "MILK ALTERNATIVES & SYRUPS (add-ons)",
]
FOOD_SECTIONS = [
    "BAKERY & SNACKS (counter)",
    "BREAKFAST — BELGIAN WAFFLES (8:30–11:30am)",
    "BREAKFAST — EGGS (8:30–11:30am)",
    "BREAKFAST — GRANOLA, WRAPS & BAGELS (8:30–11:30am)",
    "LIGHT SNACKS (12–4pm)",
    "SIDES, SNACKS & STARTERS (12–9pm)",
    "PIZZA (12–9pm)",
    "PASTA (12–9pm)",
    "KIDS MENU (incl. drink & ice cream)",
    "DESSERT",
    "PIZZA TOPPINGS & EXTRAS",
]

SECTION_SHADE = (0.952941, 0.941176, 0.909804)
HEADER_SHADE = (0.101961, 0.101961, 0.101961)
ADD_ON = "└ "


def fail(message):
    sys.exit(f"the-loft.py: {message}")


def close(a, b):
    return a is not None and len(a) == len(b) and all(abs(x - y) < 0.002 for x, y in zip(a, b))


def centre_in(obj, x0, x1, top, bottom):
    cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
    return x0 <= cx < x1 and top <= cy < bottom


def text_of(chars):
    return " ".join(extract_text(chars).split())


def check_key(page):
    """The key on page 1 must say what this script assumes."""
    text = " ".join(page.extract_text().split())
    for mark, wording, colour in (CONTAINS, MAY_CONTAIN):
        if f"{mark} {wording}" not in text:
            fail(f"page 1 key doesn't say '{mark} {wording}'")
        if not any(c["text"] == mark and close(c["non_stroking_color"], colour) and c["top"] < 140 for c in page.chars):
            fail(f"key mark {mark} isn't in the expected colour")
    for code, name, _ in COLUMNS:
        if f"{code} {name}" not in text:
            fail(f"page 1 key doesn't define {code} as {name}")


def read(path):
    rows = []  # every table row, in order: kind, text, marks
    with pdfplumber.open(path) as pdf:
        check_key(pdf.pages[0])
        for page in pdf.pages:
            xs = sorted({round(l["x0"], 2) for l in page.lines if abs(l["x0"] - l["x1"]) < 0.5})
            ys = sorted({round(l["top"], 2) for l in page.lines if abs(l["top"] - l["bottom"]) < 0.5})
            if len(xs) != len(COLUMNS) + 2:
                fail(f"page {page.page_number}: expected {len(COLUMNS) + 2} column rules, found {len(xs)}")
            shades = [(r["top"], r["bottom"], r["non_stroking_color"]) for r in page.rects]
            in_table = []
            for top, bottom in zip(ys, ys[1:]):
                mid = (top + bottom) / 2
                shade = next((s for t, b, s in shades if t <= mid < b), None)
                chars = [c for c in page.chars if centre_in(c, xs[0], xs[-1], top, bottom)]
                in_table += chars
                marks = [c for c in chars if c["text"] in MARKS]
                words = [c for c in chars if c["text"] not in MARKS]
                text = text_of(words)
                if close(shade, HEADER_SHADE):
                    codes = text.split()
                    if codes != ["Item"] + [code for code, _, _ in COLUMNS]:
                        fail(f"page {page.page_number}: heading row reads {text!r}")
                    for code, (x0, x1) in zip(codes[1:], zip(xs[1:], xs[2:])):
                        if not any(centre_in(w, x0, x1, top, bottom) and w["text"] == code
                                   for w in page.extract_words()):
                            fail(f"page {page.page_number}: {code} isn't over its column")
                    continue
                if close(shade, SECTION_SHADE):
                    if marks:
                        fail(f"page {page.page_number}: marks in section row {text!r}")
                    rows.append({"kind": "section", "text": text, "page": page.page_number})
                    continue
                labels = {}
                for m in marks:
                    value, colour = MARKS[m["text"]]
                    if not close(m["non_stroking_color"], colour):
                        fail(f"page {page.page_number} {text!r}: {m['text']} drawn in an unexpected colour")
                    column = next((i for i, (x0, x1) in enumerate(zip(xs[1:], xs[2:]))
                                   if x0 <= (m["x0"] + m["x1"]) / 2 < x1), None)
                    if column is None:
                        fail(f"page {page.page_number} {text!r}: a mark isn't under an allergen column")
                    allergen = COLUMNS[column][2]
                    if allergen in labels:
                        fail(f"page {page.page_number} {text!r}: two marks under {COLUMNS[column][0]}")
                    labels[allergen] = value
                indent = min((c["x0"] for c in words), default=0) - xs[0]
                rows.append({"kind": "dish", "text": text, "labels": labels, "indent": indent,
                             "page": page.page_number, "top": top, "bottom": bottom})
            # Outside the table there may only be the title and key (page 1) and the footnote
            # (last page), and no marks except the key's own.
            used = {id(c) for c in in_table}
            outside = [c for c in page.chars if id(c) not in used]
            if 1 < page.page_number < len(pdf.pages) and outside:
                fail(f"page {page.page_number}: text outside the table: {text_of(outside)!r}")
            stray = [c for c in outside if c["text"] in MARKS and not (page.page_number == 1 and c["top"] < 140)]
            if stray:
                fail(f"page {page.page_number}: {len(stray)} marks outside the table")
    return rows


def dishes_from(rows):
    dishes, category, notes = [], None, []
    for row in rows:
        if row["kind"] == "section":
            category = row["text"]
            if category not in DRINK_SECTIONS + FOOD_SECTIONS:
                fail(f"unknown section {category!r}: decide whether it's food or drink")
            continue
        if category is None:
            fail(f"dish {row['text']!r} before any section heading")
        text = row["text"]
        previous = dishes[-1] if dishes else None
        # A long name wraps onto the next table row: indented, no marks, and the previous
        # row's bracket still open.
        if (previous and not text.startswith(ADD_ON) and not row["labels"] and row["indent"] > 3
                and previous["dish"].count("(") > previous["dish"].count(")")):
            previous["dish"] += " " + text
            notes.append(f"joined wrapped name: {previous['dish']!r}")
            continue
        under = None
        if text.startswith(ADD_ON):
            text = text[len(ADD_ON):]
            under = next(d for d in reversed(dishes) if not d["under"])["dish"]
        dishes.append({"category": category, "dish": text, "labels": row["labels"], "under": under,
                       "page": row["page"], "top": row["top"], "bottom": row["bottom"]})
    for d in dishes:
        if d["dish"].count("(") != d["dish"].count(")"):
            fail(f"unbalanced brackets in {d['dish']!r}: a wrapped name wasn't joined")
    return dishes, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default="Imports/menus/the-loft.csv")
    parser.add_argument("--any-version", action="store_true",
                        help="read a PDF other than the one this script was checked against")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EXPECTED_SHA256 and not args.any_version:
        fail(f"{args.pdf} isn't the 11 May 2026 chart this script was checked against "
             f"(SHA-256 {digest}). Check the new chart by eye, then run with --any-version.")

    all_dishes, notes = dishes_from(read(args.pdf))
    food = [d for d in all_dishes if d["category"] in FOOD_SECTIONS]
    drinks = [d for d in all_dishes if d["category"] in DRINK_SECTIONS]

    seen = set()
    for d in food:
        key = (d["category"], d["dish"])
        if key in seen:
            fail(f"'{d['dish']}' appears twice in '{d['category']}'")
        seen.add(key)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for d in food:
            writer.writerow([d["category"], d["dish"], "", ""] + [d["labels"].get(a, "") for a in ALLERGENS])

    category = None
    for d in food:
        if d["category"] != category:
            category = d["category"]
            print(f"--- {category}")
        contains = [a for a in ALLERGENS if d["labels"].get(a) == "Y"]
        may = [a for a in ALLERGENS if d["labels"].get(a) == "M"]
        extra = f"  (may contain: {', '.join(may)})" if may else ""
        parent = f"  [└ row under '{d['under']}']" if d["under"] else ""
        print(f"p{d['page']} {d['dish']}: {', '.join(contains) or '—'}{extra}{parent}"
              + ("  NO MARKS" if not d["labels"] else ""))
    print(f"\n{len(food)} dishes written to {args.out}")
    print(f"Left out {len(drinks)} drinks rows from: {', '.join(DRINK_SECTIONS)}")
    if notes:
        print(*notes, sep="\n")


if __name__ == "__main__":
    main()
