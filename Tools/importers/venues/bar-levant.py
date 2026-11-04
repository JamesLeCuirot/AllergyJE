#!/usr/bin/env python3
"""Bar Levant (Broad Street, St Helier): read its menu's allergen codes into Imports/menus/bar-levant.csv.

Source: "UPDATED Bar Levant Menu 2026", eight narrow pages made with Canva on 28 August 2026,
linked from https://barlevant.je/ as
https://barlevant.je/wp-content/uploads/2026/08/UPDATED-Bar-Levant-Menu-2026.pdf
(SHA-256 4afc5eb4ee00408038dac1d6bf7c4db7fb54f4c6d35551db96bd377a754675b5).

Layout: pages 1-2 are food (Small Plates, Toasted Focaccia Sandwiches, Pizzas); pages 3-8 are
drinks, with no allergen codes, and are left out. Each dish is a line in the Typewriter font
("Padron Peppers  £7"), then one or two description lines in Futura that end with its codes,
e.g. "With Maldon sea salt and aioli dip (Mu, E)". Section headings are in Jedira. The key,
printed at the foot of page 2 as "Allergen Key Chart":
  F - Fish   G - Gluten   Da - Dairy   Pn - Peanuts   Tn - Tree nuts
  So - Soybean   Su - Sulphur Dioxide   Ce - Celery   Mu - Mustard   Se - Sesame
  Lu - Lupin   Cr - Crustaceans   E - Eggs   Mo - Molluscs
The script reads the codes from this printed key (KEY_NAMES maps each name to the app's
allergen) and stops if it changes.

One dish has extras with their own codes: "Caesar Salad (Add Chicken or Prawn - £4)" ...
"(G, Se, Mu, Da, F) (Chicken - E) (Prawn - Cr)". It becomes three rows: the salad, the salad
with chicken (adds E) and the salad with prawn (adds Cr), the last two priced £11 + £4.

A dish with no codes is left out and listed: the menu doesn't say every dish is coded, so
no codes can't be read as no allergens. (On this menu: Beef Dripping Chunky Chips.)
Codes are taken off the end of the description; anything the script doesn't recognise
(an unknown code, a code group not at the end, text in an unexpected font, a drinks page
with codes) stops it.

Usage:
  python3 Tools/importers/venues/bar-levant.py UPDATED-Bar-Levant-Menu-2026.pdf \
      [--out Imports/menus/bar-levant.csv] [--any-version]
Needs pdfplumber.
"""
import argparse
import csv
import hashlib
import os
import re
import sys
from decimal import Decimal

import pdfplumber

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

EXPECTED_SHA256 = "4afc5eb4ee00408038dac1d6bf7c4db7fb54f4c6d35551db96bd377a754675b5"

KEY_LINES = [
    "F - Fish G - Gluten Da - Dairy Pn - Peanuts Tn - Tree nuts",
    "So - Soybean Su - Sulphur Dioxide Ce - Celery Mu - Mustard Se - Sesame",
    "Lu - Lupin Cr - Crustaceans E - Eggs Mo - Molluscs",
]
KEY_NAMES = {"Fish": "Fish", "Gluten": "Gluten", "Dairy": "Milk", "Peanuts": "Peanuts",
             "Tree nuts": "Nuts", "Soybean": "Soybeans", "Sulphur Dioxide": "Sulphur Dioxide",
             "Celery": "Celery", "Mustard": "Mustard", "Sesame": "Sesame", "Lupin": "Lupin",
             "Crustaceans": "Crustaceans", "Eggs": "Eggs", "Molluscs": "Molluscs"}

FOOD_PAGES = [1, 2]
SECTIONS = ["Small Plates", "Toasted Focaccia Sandwiches", "Pizzas"]
NAME_FONT, TEXT_FONT, HEADING_FONT = "Typewriter-Serial-Medium-Regular", "FuturaCyrillicBook", "Jedira-Regular"
CODE = r"[A-Z][a-z]?"
GROUP = re.compile(rf"\(({CODE}(?:, {CODE})*)\)")
EXTRA_GROUP = re.compile(rf"\((\w+) - ({CODE}(?:, {CODE})*)\)")
ADD_EXTRAS = re.compile(r"^(?P<dish>.+?) \(Add (?P<a>\w+) or (?P<b>\w+) - £(?P<price>\d+(?:\.\d\d)?)\)$")


def fail(message):
    sys.exit(f"bar-levant.py: STOPPED: {message}")


def font(word):
    return word["fontname"].split("+")[-1]


def lines_of(page, tolerance=3.0):
    words = page.extract_words(extra_attrs=["fontname", "size"])
    words.sort(key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"]))
    lines = []
    for w in words:
        mid = (w["top"] + w["bottom"]) / 2
        if lines and abs(lines[-1]["mid"] - mid) <= tolerance:
            lines[-1]["words"].append(w)
        else:
            lines.append({"mid": mid, "words": [w]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
        line["text"] = " ".join(" ".join(w["text"] for w in line["words"]).split())
        line["fonts"] = {font(w) for w in line["words"]}
    return lines


def read_key(lines):
    text = [l["text"] for l in lines if l["fonts"] == {NAME_FONT} and " - " in l["text"]]
    if text != KEY_LINES:
        fail(f"the key reads {text}, expected {KEY_LINES}")
    key = {}
    for line in KEY_LINES:
        for code, name in re.findall(rf"({CODE}) - (.+?)(?= {CODE} - |$)", line):
            if name not in KEY_NAMES or code in key:
                fail(f"key entry {code} - {name} isn't expected")
            key[code] = KEY_NAMES[name]
    if sorted(key.values()) != sorted(ALLERGENS):
        fail("the key doesn't name each of the 14 allergens once")
    return key


def allergens(codes, key):
    found = set()
    for code in codes.split(", "):
        if code not in key:
            fail(f"code {code!r} isn't in the key")
        found.add(key[code])
    return found


def read(path):
    with pdfplumber.open(path) as pdf:
        pages = {p.page_number: lines_of(p) for p in pdf.pages}
    key = read_key(pages[2])

    for n, lines in pages.items():
        if n not in FOOD_PAGES and any(GROUP.search(l["text"]) or EXTRA_GROUP.search(l["text"]) for l in lines):
            fail(f"page {n} (drinks) prints allergen codes: decide what to do with them")

    dishes, category = [], None
    for n in FOOD_PAGES:
        for line in pages[n]:
            text, fonts = line["text"], line["fonts"]
            if fonts == {HEADING_FONT}:
                if text == "Allergen Key Chart":
                    category = "KEY"
                    continue
                if text not in SECTIONS:
                    fail(f"page {n}: unknown section {text!r}")
                category = text
                continue
            if category == "KEY":
                continue  # read and checked by read_key
            if fonts == {NAME_FONT}:
                m = re.fullmatch(r"(.+) £(\d+(?:\.\d\d)?)", text)
                if not m:
                    fail(f"page {n}: dish line without a price: {text!r}")
                if category is None:
                    fail(f"page {n}: {text!r} before any section")
                dishes.append({"page": n, "category": category, "name": m[1], "price": m[2], "desc": []})
                continue
            if fonts == {TEXT_FONT} and dishes and dishes[-1]["page"] == n:
                dishes[-1]["desc"].append(text)
                continue
            fail(f"page {n}: unexpected line {text!r} in fonts {fonts}")

    rows, left_out = [], []
    for d in dishes:
        desc = " ".join(d["desc"])
        # The codes are the run of bracketed groups at the very end of the description.
        tail = re.search(rf"((?: ?(?:{GROUP.pattern}|{EXTRA_GROUP.pattern}))+)$", desc)
        body = desc[:tail.start()].strip() if tail else desc
        if GROUP.search(body) or EXTRA_GROUP.search(body):
            fail(f"{d['name']!r}: a code group that isn't at the end of the description")
        groups = GROUP.findall(tail[1]) if tail else []
        extras = EXTRA_GROUP.findall(tail[1]) if tail else []
        if len(groups) > 1:
            fail(f"{d['name']!r}: more than one plain code group")
        m = ADD_EXTRAS.match(d["name"])
        if bool(m) != bool(extras):
            fail(f"{d['name']!r}: extras in the name and coded extras don't match up")
        if not groups:
            left_out.append((d, "no allergen codes"))
            continue
        base = allergens(groups[0], key)
        name = m["dish"] if m else d["name"]
        rows.append({**d, "dish": name, "description": body, "allergens": base, "codes": f"({groups[0]})"})
        if m:
            if sorted(e for e, _ in extras) != sorted([m["a"], m["b"]]):
                fail(f"{d['name']!r}: extras {m['a']}/{m['b']} but codes for {[e for e, _ in extras]}")
            for extra, codes in extras:
                price = Decimal(d["price"]) + Decimal(m["price"])
                rows.append({**d, "dish": f"{name} with {extra}", "price": f"{price:.2f}".removesuffix(".00"),
                             "description": f"{body} (Add {extra} £{m['price']})",
                             "allergens": base | allergens(codes, key),
                             "codes": f"({groups[0]}) + ({extra} - {codes})"})
    return rows, left_out, len(pages)


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default=os.path.join(root, "Imports", "menus", "bar-levant.csv"))
    parser.add_argument("--any-version", action="store_true",
                        help="read a PDF other than the one this script was checked against")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EXPECTED_SHA256 and not args.any_version:
        fail(f"{args.pdf} isn't the 28 August 2026 menu this script was checked against "
             f"(SHA-256 {digest}). Check the new menu by eye, then run with --any-version.")

    rows, left_out, n_pages = read(args.pdf)
    seen = set()
    for r in rows:
        if (r["category"], r["dish"]) in seen:
            fail(f"{r['dish']!r} appears twice in {r['category']!r}")
        seen.add((r["category"], r["dish"]))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for r in rows:
            writer.writerow([r["category"], r["dish"], r["description"], r["price"]]
                            + ["Y" if a in r["allergens"] else "" for a in ALLERGENS])

    category = None
    for r in rows:
        if r["category"] != category:
            category = r["category"]
            print(f"--- p{r['page']} {category}")
        print(f"  {r['dish']} £{r['price']} {r['codes']}: {', '.join(a for a in ALLERGENS if a in r['allergens'])}")
    print(f"\n{len(rows)} rows written to {args.out}")
    print("\nLeft out:")
    for d, why in left_out:
        print(f"  p{d['page']} [{d['category']}] {d['name']} £{d['price']}: {' '.join(d['desc'])!r} → {why}")
    print(f"  pages {', '.join(str(n) for n in range(1, n_pages + 1) if n not in FOOD_PAGES)}: drinks (no codes)")


if __name__ == "__main__":
    main()
