#!/usr/bin/env python3
"""Read a restaurant's allergen matrix PDF into the Imports/ menu CSV format.

Works with the common layout: rotated allergen names across the top, one dish per row,
and a mark in each column where the dish contains that allergen. Marks:
  ✓ ✔ Y X  → contains
  MC CR M  → may contain (an ingredient labelled "may contain", or cross-contamination)

Section headings (rows with no marks, in italics or ending in "…") become the category.
Several gluten cereal columns (wheat, rye, barley, oats, spelt, khorasan) become one Gluten.

Usage:
  python3 Tools/importers/allergen_matrix_pdf.py menu.pdf --out Imports/menus/<slug>.csv

Prints each dish with its allergens so the result can be checked against the PDF by eye.
Needs pdfplumber (pip install pdfplumber).
"""
import argparse
import csv
import re
import sys
from collections import defaultdict

import pdfplumber

# Order and names match UKAllergen raw values in the app.
ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

# Checked in order: "peanut" before "nut", "khorasan wheat" is gluten.
HEADER_PATTERNS = [
    (r"gluten|wheat|rye|barley|oat|spelt|khorasan|kamut", "Gluten"),
    (r"crustacean", "Crustaceans"),
    (r"\begg", "Eggs"),
    (r"\bfish", "Fish"),
    (r"peanut", "Peanuts"),
    (r"soy", "Soybeans"),
    (r"milk|dairy|lactose", "Milk"),
    (r"nut", "Nuts"),
    (r"celery|celeriac", "Celery"),
    (r"mustard", "Mustard"),
    (r"sesame", "Sesame"),
    (r"sulph|sulf", "Sulphur Dioxide"),
    (r"lupin", "Lupin"),
    (r"mollus", "Molluscs"),
]

CONTAINS = {"✓", "✔", "Y", "X", "x", "✗"}
MAY_CONTAIN = {"MC", "CR", "M"}


def allergen_for(label):
    text = label.lower()
    for pattern, allergen in HEADER_PATTERNS:
        if re.search(pattern, text):
            return allergen
    return None


def rotated(char):
    a, b, c, d, _, _ = char["matrix"]
    return abs(a) < 0.1 and abs(d) < 0.1  # rotated 90° either way


def columns(page):
    """Allergen columns from rotated header text: list of (x centre, allergen, label)."""
    groups = defaultdict(list)
    for char in page.chars:
        if rotated(char):
            groups[round((char["x0"] + char["x1"]) / 2)].append(char)
    found = []
    for x, chars in sorted(groups.items()):
        label = "".join(c["text"] for c in sorted(chars, key=lambda c: c["top"], reverse=True)).strip()
        allergen = allergen_for(label)
        if allergen:
            found.append((x, allergen, label, max(c["bottom"] for c in chars)))
    return found


def lines(words, tolerance=3):
    rows = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(rows[-1][0]["top"] - word["top"]) <= tolerance:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def read(path):
    dishes = []
    category = ""
    problems = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            cols = columns(page)
            if not cols:
                problems.append(f"page {page_number}: no allergen columns found")
                continue
            spacing = min(b[0] - a[0] for a, b in zip(cols, cols[1:])) if len(cols) > 1 else 20
            first_x = cols[0][0]
            header_bottom = max(c[3] for c in cols)
            words = page.extract_words(keep_blank_chars=False, extra_attrs=["fontname"])
            body = [w for w in words if w["top"] > header_bottom + 2]
            for row in lines(body):
                name_words = [w for w in row if w["x1"] < first_x - spacing / 2]
                marks = [w for w in row if w["x0"] >= first_x - spacing / 2]
                name = " ".join(w["text"] for w in name_words).strip()
                if not name:
                    if marks:
                        problems.append(f"page {page_number}: marks with no dish name near y={row[0]['top']:.0f}")
                    continue
                if not marks:
                    italic = all("italic" in w["fontname"].lower() for w in name_words)
                    if italic or name.endswith(("…", "...")):
                        category = name.rstrip("….").strip()
                        continue
                labels = {}
                for mark in marks:
                    text = mark["text"].strip()
                    centre = (mark["x0"] + mark["x1"]) / 2
                    x, allergen, label, _ = min(cols, key=lambda c: abs(c[0] - centre))
                    if abs(x - centre) > spacing / 2:
                        problems.append(f"page {page_number} '{name}': mark '{text}' isn't under a column")
                        continue
                    if text in CONTAINS:
                        labels[allergen] = "Y"
                    elif text in MAY_CONTAIN:
                        labels.setdefault(allergen, "M")
                    else:
                        problems.append(f"page {page_number} '{name}': unknown mark '{text}'")
                dishes.append({"category": category, "dish": name, "labels": labels, "page": page_number})
    return dishes, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    dishes, problems = read(args.pdf)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for dish in dishes:
            writer.writerow([dish["category"], dish["dish"], "", ""] + [dish["labels"].get(a, "") for a in ALLERGENS])

    for dish in dishes:
        contains = [a for a in ALLERGENS if dish["labels"].get(a) == "Y"]
        may = [a for a in ALLERGENS if dish["labels"].get(a) == "M"]
        extra = f"  (may contain: {', '.join(may)})" if may else ""
        print(f"p{dish['page']} [{dish['category']}] {dish['dish']}: {', '.join(contains) or '—'}{extra}")
    print(f"\n{len(dishes)} dishes written to {args.out}")
    if problems:
        print("\nProblems:", *problems, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
