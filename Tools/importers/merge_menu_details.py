#!/usr/bin/env python3
"""Add descriptions, prices and menu sections from a restaurant's menu to its allergen data.

The allergen CSV (from allergen_matrix_pdf.py) is the authority: its dishes and their
names are kept as they are. Each is matched to the menu details by name, or through an
explicit alias file for names the restaurant writes differently in the two places:

  aliases.csv: allergen_dish,menu_dish,price,category[,allergen_category]
    Grilled gambas (main),Grilled gambas,,
    Pepper sauce,Steak sauces,2.75,
    Spicy olives,,,To share            ← no menu entry, but file it under this section
    Grilled chicken,,,Children's,Children's   ← only the one in the allergen data's Children's section

Menu dishes with no allergen data are listed at the end and NOT added: a dish without
allergen information must never reach the app, where it would look allergen-free.

Usage:
  python3 Tools/importers/merge_menu_details.py allergens.csv details1.csv [details2.csv …] \
      [--aliases aliases.csv] --out merged.csv
"""
import argparse
import csv
import re
import sys
import unicodedata


def key(name):
    text = re.sub(r"['’‘`]", "", name)  # Chef’s = Chef's = Chefs
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("allergens")
    parser.add_argument("details", nargs="+")
    parser.add_argument("--aliases")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    allergen_rows = read(args.allergens)
    fields = list(allergen_rows[0].keys())

    details = {}
    for path in args.details:  # earlier files win when a dish is listed twice
        for row in read(path):
            details.setdefault(key(row["dish"]), row)

    # An alias can be limited to one section of the allergen data, for dishes listed twice.
    aliases = {(key(a.get("allergen_category") or ""), key(a["allergen_dish"])): a for a in read(args.aliases)} if args.aliases else {}

    used = set()
    unmatched = []
    for row in allergen_rows:
        alias = aliases.get((key(row["category"]), key(row["dish"]))) or aliases.get(("", key(row["dish"])), {})
        # An alias with a blank menu_dish means the dish has no menu entry of its own.
        menu_key = key(alias["menu_dish"]) if alias.get("menu_dish") else (None if alias else key(row["dish"]))
        found = details.get(menu_key) if menu_key else None
        if found:
            used.add(menu_key)
            row["description"] = found["description"]
            row["price"] = found["price"]
            row["category"] = found["category"] or row["category"]
        elif not alias:
            unmatched.append(row["dish"])
        if alias.get("price"):
            row["price"] = alias["price"]
        if alias.get("category"):
            row["category"] = alias["category"]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(allergen_rows)

    print(f"{len(allergen_rows)} dishes written to {args.out}")
    if unmatched:
        print("\nAllergen dishes with no menu details (kept, without description or price):")
        for name in unmatched:
            print(f"  {name}")
    left_over = [row for k, row in details.items() if k not in used]
    if left_over:
        print("\nOn the menu but not in the allergen data (NOT added; ask the restaurant):")
        for row in left_over:
            print(f"  [{row['category']}] {row['dish']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
