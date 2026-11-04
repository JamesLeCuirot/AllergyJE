#!/usr/bin/env python3
"""Quayside Seafood Bistro & Grill (Liberty Wharf, St Helier): read its menus' allergen codes
into Imports/menus/quayside.csv.

Sources, both linked from https://quaysidejersey.co.uk/ ("A La Carte Menu", "Express Lunch Menu"):
  https://quaysidejersey.co.uk/uploads/2026_Quayside_ALa_Carte_Menu.pdf
    four A4 pages made with Canva on 28 August 2026
    (SHA-256 42ad0c1f183b12cbbae59b4f6834a0bd161462ad2a55cc536d386189acc189a0)
  https://quaysidejersey.co.uk/uploads/2026_Quayside_Express_Menu.pdf
    one A4 page made with Canva, 14-16 July 2026
    (SHA-256 1050be7574d136a0611f5279892833ae4aa42037227ff4cb92b870fc274726ce)
Not read: the Tennerfest menu and "Tennerfest Desserts" card (an event), the Christmas,
party, Winterfest, Valentine, Mother's Day and Easter menus (events and set menus), and the
Sunday lunch menu (August 2025, a different letter key that its own codes don't follow).

THE KEY IS NOT THE USUAL ORDER. As printed:
  1 Gluten · 2 Milk (Dairy on the express menu) · 3 Peanuts · 4 Crustaceans · 5 Eggs · 6 Fish ·
  7 Sulphur Dioxide · 8 Molluscs · 9 Mustard · 10 Sesame · 11 Soybean · 12 Tree-nuts ·
  13 Celery · 14 Lupin
On the à la carte's page 1 the names are set as running text ("Contains Gluten Contains /
Milk Contains Peanuts / ...") beside a column of numbers (1)...(14), and the lines don't line
up with the numbers. The script reads the names in order and pairs the i-th with (i). The
express menu prints the same key as three tidy columns, one "Contains X (n)" per line; the
script reads that too and stops unless the two agree. The dishes bear it out: crab dishes
carry 4, scallops 8, Moules Marinière (white wine) 7 and 8, the "sesame pak choi" duck 10,
the walnut bon-bon 12.

Layout: à la carte pages 2-4 are two columns each under a page heading (STARTERS, MAINS),
with sub-headings (Fish, Crab, Shellfish ...). A dish is a bold line "Name  £price", then a
description in small capitals that ends with its codes, e.g. "... poached egg and wilted
spinach. (2, 5, 6, 8)". Page 4 ends with SIDES, "All Side Orders £6.50", one side per line
with its codes. The express menu is one column: name, then description ending with codes,
all "£20.95 per dish". The codes are only ever the numbers 1-14; any other bracketed number
group, or one not at the end of a description, stops the script.

category is the page heading and sub-heading, e.g. "Starters — Crab", "Mains — From the
Grill", "Sides", and "Express Lunch Menu (Monday - Friday)". Dishes printed with no codes
are left out and listed: the menus don't say every dish is coded ("we cannot fully
guarantee the complete absence of allergens"), so no codes can't be read as no allergens.

Usage:
  python3 Tools/importers/venues/quayside.py 2026_Quayside_ALa_Carte_Menu.pdf \
      2026_Quayside_Express_Menu.pdf [--out Imports/menus/quayside.csv] [--any-version]
Needs pdfplumber.
"""
import argparse
import csv
import hashlib
import os
import re
import sys

import pdfplumber

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

EXPECTED = {
    "a la carte": "42ad0c1f183b12cbbae59b4f6834a0bd161462ad2a55cc536d386189acc189a0",
    "express": "1050be7574d136a0611f5279892833ae4aa42037227ff4cb92b870fc274726ce",
}

# Names as the keys print them → the app's allergen.
KEY_NAMES = {"Gluten": "Gluten", "Milk": "Milk", "Dairy": "Milk", "Peanuts": "Peanuts",
             "Crustaceans": "Crustaceans", "Eggs": "Eggs", "Fish": "Fish",
             "Sulphur Dioxide": "Sulphur Dioxide", "Molluscs": "Molluscs", "Mustard": "Mustard",
             "Sesame": "Sesame", "Soybean": "Soybeans", "Tree-nuts": "Nuts", "Celery": "Celery",
             "Lupin": "Lupin"}
ALC_KEY_TEXT = ("Contains Gluten Contains Milk Contains Peanuts Contains Crustaceans Contains Eggs "
                "Contains Fish Contains Sulphur Dioxide Contains Molluscs Contains Mustard Contains "
                "Sesame Contains Soybean Contains Tree-nuts Contains Celery Contains Lupin")

CODES = re.compile(r"\((\d+(?:,\s*\d+)*)\)")
NAME_FONT = "GentiumPlus-Bold"
TEXT_FONT = "TrajanPro-Regular"
COLUMN_SPLIT = 340       # pt: left column words start left of this, right column words right of it
HEADER_BOTTOM = 145      # pt: page logo and page heading above this
FOOTER_TOP = 795         # pt: service-charge line below this
SIDES_TOP = 585          # pt: on page 4, the SIDES block (full width) starts here
PAGE_HEADINGS = {"starters": "Starters", "MAINS": "Mains", "SIDES": "Sides"}
SUBHEADINGS = {"Fish", "Crab", "Squid", "Meat", "Vegetarian", "Shellfish", "Oysters", "Scallops",
               "Mussels", "Surf & Turf", "Pastas / Risotto / Vegetarian", "From the Grill"}
FOOTER = "A 10% discretionary service charge will be added to your bill."
EXPRESS_CATEGORY = "Express Lunch Menu (Monday - Friday)"


def fail(message):
    sys.exit(f"quayside.py: STOPPED: {message}")


def font(word):
    return word["fontname"].split("+")[-1]


def lines_in(words, x0, top, x1, bottom, tolerance=3.0):
    inside = [w for w in words if x0 <= w["x0"] < x1 and top <= (w["top"] + w["bottom"]) / 2 < bottom]
    inside.sort(key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"]))
    lines = []
    for w in inside:
        mid = (w["top"] + w["bottom"]) / 2
        if lines and abs(lines[-1]["mid"] - mid) <= tolerance:
            lines[-1]["words"].append(w)
        else:
            lines.append({"mid": mid, "words": [w]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
        line["text"] = " ".join(" ".join(w["text"] for w in line["words"]).split())
        line["fonts"] = {font(w) for w in line["words"]}
        line["size"] = max(w["size"] for w in line["words"])
    return lines, inside


def words_of(page):
    return page.extract_words(extra_attrs=["fontname", "size"])


def allergens(codes, key, where):
    found = set()
    for number in re.split(r",\s*", codes):
        if int(number) not in key:
            fail(f"{where}: code {number} isn't in the key")
        found.add(key[int(number)])
    return found


def alc_key(page):
    """Page 1: the names as running text, and the numbers (1)..(14) in their own column."""
    words = words_of(page)
    names = " ".join(w["text"] for w in sorted(
        (w for w in words if font(w) == "GentiumPlus" and not re.fullmatch(r"\(\d+\)", w["text"])),
        key=lambda w: (round(w["top"]), w["x0"])))
    numbers = [w["text"] for w in sorted((w for w in words if re.fullmatch(r"\(\d+\)", w["text"])),
                                         key=lambda w: w["top"])]
    if names != ALC_KEY_TEXT:
        fail(f"à la carte key reads {names!r}")
    if numbers != [f"({i})" for i in range(1, 15)]:
        fail(f"à la carte key numbers read {numbers}")
    printed = [n.strip() for n in names.split("Contains") if n.strip()]
    return {i + 1: KEY_NAMES[name] for i, name in enumerate(printed)}


def express_key(page):
    """Three columns of 'Contains X (n)', each pair on one line."""
    words = [w for w in words_of(page) if font(w) == "GentiumPlus" and w["top"] > 700 and w["size"] < 13.6]
    key = {}
    for x0, x1 in ((0, 200), (200, 405), (405, 600)):
        # The numbers drift up to ~5pt below their names, so pair them in order down the
        # column, and require each pair to be nearer than half the 16pt line spacing.
        column = [w for w in words if x0 <= w["x0"] < x1]
        numbers = sorted((w for w in column if re.fullmatch(r"\(\d+\)", w["text"])), key=lambda w: w["top"])
        names, _ = lines_in([w for w in column if w not in numbers], x0, 700, x1, 800)
        if len(names) != len(numbers):
            fail(f"express key column at x={x0}: {len(names)} names but {len(numbers)} numbers")
        for line, number in zip(names, numbers):
            m = re.fullmatch(r"Contains (.+)", line["text"])
            if not m or m[1] not in KEY_NAMES:
                fail(f"express key line {line['text']!r}")
            if abs(line["mid"] - (number["top"] + number["bottom"]) / 2) > 8:
                fail(f"express key: {number['text']} isn't level with {line['text']!r}")
            key[int(number["text"].strip("()"))] = KEY_NAMES[m[1]]
    return key


def finish(dish, key, where):
    """Split the description from its trailing codes."""
    desc = " ".join(dish.pop("lines"))
    m = re.search(rf"\s*{CODES.pattern}\s*$", desc)
    body = desc[:m.start()] if m else desc
    if CODES.search(body):
        fail(f"{where} {dish['dish']!r}: a code group that isn't at the end of the description")
    dish["description"] = body.strip()
    dish["codes"] = m[1] if m else None
    dish["allergens"] = allergens(m[1], key, f"{where} {dish['dish']!r}") if m else set()
    return dish


def read_alc(pdf, key):
    dishes = []
    for page in pdf.pages[1:]:
        n = page.page_number
        words = words_of(page)
        header, used_h = lines_in(words, 0, 0, 600, HEADER_BOTTOM)
        footer, used_f = lines_in(words, 0, FOOTER_TOP, 600, 900)
        if header[0]["text"] != "Seafood Bistro & Grill" or len(header) != 2 or header[1]["text"] not in PAGE_HEADINGS:
            fail(f"à la carte page {n}: header reads {[l['text'] for l in header]}")
        if [l["text"] for l in footer] != [FOOTER]:
            fail(f"à la carte page {n}: footer reads {[l['text'] for l in footer]}")
        heading = PAGE_HEADINGS[header[1]["text"]]
        body_bottom = SIDES_TOP if n == 4 else FOOTER_TOP
        blocks = [(0, COLUMN_SPLIT, HEADER_BOTTOM, body_bottom), (COLUMN_SPLIT, 600, HEADER_BOTTOM, body_bottom)]
        if n == 4:
            blocks.append((0, 600, SIDES_TOP, FOOTER_TOP))
        used = {id(w) for w in used_h + used_f}
        for x0, x1, top, bottom in blocks:
            lines, inside = lines_in(words, x0, top, x1, bottom)
            used |= {id(w) for w in inside}
            category, side_price = None, None
            for line in lines:
                text, fonts, where = line["text"], line["fonts"], f"à la carte p{n}"
                if fonts == {TEXT_FONT} and line["size"] > 9.5:
                    if text in SUBHEADINGS:
                        category = f"{heading} — {text}"
                    elif text == "SIDES":
                        category = "Sides"
                    else:
                        fail(f"{where}: unknown heading {text!r}")
                    continue
                if category is None:
                    fail(f"{where}: {text!r} before any heading")
                if category == "Sides":
                    if fonts == {NAME_FONT} and text == "All Side Orders £6.50":
                        side_price = "6.50"
                        continue
                    if fonts != {"GentiumPlus"} or side_price is None:
                        fail(f"{where}: unexpected line in SIDES {text!r}")
                    m = re.fullmatch(rf"(.+?)\s*(?:{CODES.pattern})?", text)
                    dishes.append(finish({"page": n, "category": category, "dish": m[1], "price": side_price,
                                          "lines": [f"({m[2]})"] if m[2] else []}, key, where))
                    continue
                if fonts == {NAME_FONT}:
                    m = re.fullmatch(r"(.+?)(?: £(\d+\.\d\d))?", text)
                    dishes.append({"page": n, "category": category, "dish": m[1].rstrip("."),
                                   "price": m[2] or "", "lines": []})
                    continue
                if fonts == {TEXT_FONT} and line["size"] < 8 and dishes and "lines" in dishes[-1]:
                    dishes[-1]["lines"].append(text)
                    continue
                fail(f"{where}: unexpected line {text!r} in {fonts} {line['size']:.1f}")
            for d in dishes:
                if "lines" in d:
                    finish(d, key, f"à la carte p{d['page']}")
        stray = [w["text"] for w in words if id(w) not in used]
        if stray:
            fail(f"à la carte page {n}: words outside every block: {stray}")
    return dishes


def read_express(pdf, key):
    page = pdf.pages[0]
    words = words_of(page)
    lines, _ = lines_in(words, 0, 0, 600, 680)  # the key box starts below 680pt
    texts = [l["text"] for l in lines]
    if texts[:3] != ["EXPRESS LUNCH MENU", "Lunch Only | Monday - Friday", "£20.95 per dish"]:
        fail(f"express menu heading reads {texts[:3]}")
    dishes = []
    for line in lines[3:]:
        if line["fonts"] == {NAME_FONT}:
            dishes.append({"page": 1, "category": EXPRESS_CATEGORY, "dish": line["text"], "price": "20.95", "lines": []})
        elif line["fonts"] == {TEXT_FONT} and dishes:
            dishes[-1]["lines"].append(line["text"])
        else:
            fail(f"express menu: unexpected line {line['text']!r}")
    return [finish(d, key, "express") for d in dishes]


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("a_la_carte_pdf")
    parser.add_argument("express_pdf")
    parser.add_argument("--out", default=os.path.join(root, "Imports", "charts-on-hold", "quayside.csv"))
    parser.add_argument("--any-version", action="store_true",
                        help="read PDFs other than the ones this script was checked against")
    args = parser.parse_args()

    for name, path in (("a la carte", args.a_la_carte_pdf), ("express", args.express_pdf)):
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if digest != EXPECTED[name] and not args.any_version:
            fail(f"{path} isn't the {name} menu this script was checked against (SHA-256 {digest}). "
                 "Check the new menu and its key by eye, then run with --any-version.")

    with pdfplumber.open(args.a_la_carte_pdf) as alc, pdfplumber.open(args.express_pdf) as exp:
        key = alc_key(alc.pages[0])
        if express_key(exp.pages[0]) != key:
            fail("the express menu's key doesn't match the à la carte key")
        if sorted(key) != list(range(1, 15)) or sorted(key.values()) != sorted(ALLERGENS):
            fail("the key doesn't give each of the 14 allergens one number")
        dishes = read_alc(alc, key) + read_express(exp, key)

    rows = [d for d in dishes if d["codes"]]
    left_out = [d for d in dishes if not d["codes"]]
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

    print("Key:", ", ".join(f"{n} {a}" for n, a in sorted(key.items())))
    category = None
    for r in rows:
        if r["category"] != category:
            category = r["category"]
            print(f"--- {category}")
        print(f"  p{r['page']} {r['dish']} £{r['price'] or '-'} ({r['codes']}): "
              f"{', '.join(a for a in ALLERGENS if a in r['allergens'])}")
    print(f"\n{len(rows)} rows written to {args.out}")
    print("\nLeft out (no allergen codes printed):")
    for d in left_out:
        print(f"  p{d['page']} [{d['category']}] {d['dish']} £{d['price'] or '-'}: {d['description']!r}")

    by_name = {}
    for r in rows:
        by_name.setdefault(re.sub(r"\W+", " ", r["dish"].lower().replace("à", "a")).strip(), []).append(r)
    print("\nSame dish on both menus:")
    for rs in by_name.values():
        if len({r["category"].startswith("Express") for r in rs}) > 1:
            same = len({frozenset(r["allergens"]) for r in rs}) == 1
            print(f"  {'same codes' if same else 'DIFFERENT CODES'}: "
                  + " | ".join(f"{r['dish']} [{r['category']}] ({r['codes']})" for r in rs))


if __name__ == "__main__":
    main()
