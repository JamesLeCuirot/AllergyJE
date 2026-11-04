#!/usr/bin/env python3
"""Cheffins at the Beaumont Inn (La Route de la Haule, St Peter): read its menus' allergen
codes into Imports/charts-on-hold/cheffins.csv.

Sources: the menu PDFs linked from https://cheffinsbeaumont.com/the-menu/ (all made in
Canva; each pinned by SHA-256 in MENUS below):
  A LA CARTE        /wp-content/uploads/2026/07/Cheffins-A-La-Carte-Menu-2026.pdf     21 Jul 2026
  DESSERTS          /wp-content/uploads/2026/05/CHEFFINS-ALA-CARTE-DESSERTS.pdf       8 May 2026
  SUNDAY LUNCH      /wp-content/uploads/2026/06/Cheffins-Sunday-Menu-MAY-2026.pdf     3 Jun 2026
    (the page labels it "SUNDAY LUNCH (EXAMPLE MENU)")
  SET MENU          /wp-content/uploads/2026/09/September-Set-Menu-2.pdf              11 Sep 2026
    (printed "CHEFFINS AUTUMN SET MENU, AVAILABLE MONDAY TO SATURDAY")
  Christmas Day / Christmas Party Menu (both links go to the same file)
                    /wp-content/uploads/2026/10/Cheffins-Christmas-Day-Menu-2026.pdf  29 Oct 2026
Not read: KIDS MENU (Kids-Menu-Copy-2.pdf) prints no allergen codes at all; the WINE LIST
link returns an HTML page; the 2024 "CHRISTMAS" link is a 404. The page's "Allergen and
ingredient information" link goes to allergymenu.uk/menu/VUX218, which is stale (Feb 2024).

Format: each dish prints its name (Bentham, capitals), a description line or two (Lato
Light), then its allergen codes (Lato Bold), e.g. "3, 4, 5, 8, 9, 13". A la carte and
dessert dishes carry a price beside the name; the Sunday, set and Christmas menus are
priced per course ("2 COURSES FOR £35 | 3 COURSES £39"), so their dishes have no price.

The key is NON-STANDARD and printed only as icons with the words inside the images; the
numbers 1-14 under (or over) the icons are text, except on the Christmas menu where the
whole key is one image. Read from the rendered pages of every PDF (all identical):
  1 Soybean   2 Celery   3 Crustaceans   4 Egg   5 Fish   6 Gluten   7 Lupin   8 Milk
  9 Molluscs  10 Mustard  11 Peanut  12 Sesame  13 Sulphur Dioxide  14 Treenuts
Because the key words are inside images, the script can't read them; it relies on the
pinned SHA-256 of each file and checks that the numbers 1-14 are printed in order.
Codes are "contains" (Y). The menus print no "may contain" marks; the footer says the
kitchen can't guarantee any dish is free from allergens.

Layout: two columns of dishes either side of the page centre, with some dishes centred
across the page (Fruits of the Sea, the bread, the Chateaubriand). Section headings are
script type (Starters, Mains, Desserts ...). The dessert pages carry a drinks list ("Night
Caps") in the right-hand column, which is left out.

Special cases, handled explicitly:
  * The Chateaubriand prints "Sharing Platter for two persons - 85 | Add King Prawns in
    Garlic Butter - 14" with the codes "3, 8" under the add-on: the add-on becomes its own
    row (price 14, codes 3, 8) and the Chateaubriand gets price 85.
  * ICE-CREAM (100G SCOOP) prints "8, (Pistachio - 8, 14), (Chocolate - 1, 8)" for the
    flavours "Real Vanilla | Coconut & Pineapple | Caramel | Coffee | Chocolate / Mint |
    Pistachio | Bubble-Gum" (a line break, with no "|", between Chocolate and Mint). One row
    per flavour: 8, plus the flavour's own codes. "Chocolate Mint" is read as one flavour
    and gets the Chocolate codes (1, 8), which is right whether it's one flavour or two.
  * Wrapped dish names (a name line with no price straight under a name line, before any
    description) are joined.

A dish with no codes is NOT written: no codes can't be told apart from "not listed" (the a
la carte sides, and "SELECTION OF ARTISAN ICE CREAMS" on the Sunday menu). They're listed.
Anything the script doesn't expect (an unknown heading, font, or line; codes with no dish;
a code outside 1-14) stops it.

category: the menu's own section heading, prefixed with the menu's title for the Sunday,
set and Christmas menus (e.g. "Sunday Lunch - Starters"). Dish names keep the printed
capitals; descriptions are the printed lines joined with spaces.

Usage:
  python3 Tools/importers/venues/cheffins.py <dir with the PDFs> [--out Imports/charts-on-hold/cheffins.csv]
      [--any-version]
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

# Cheffins' own key (read from the icons), code -> (key wording, app allergen).
KEY = {
    1: ("Soybean", "Soybeans"),
    2: ("Celery", "Celery"),
    3: ("Crustaceans", "Crustaceans"),
    4: ("Egg", "Eggs"),
    5: ("Fish", "Fish"),
    6: ("Gluten", "Gluten"),
    7: ("Lupin", "Lupin"),
    8: ("Milk", "Milk"),
    9: ("Molluscs", "Molluscs"),
    10: ("Mustard", "Mustard"),
    11: ("Peanut", "Peanuts"),
    12: ("Sesame", "Sesame"),
    13: ("Sulphur Dioxide", "Sulphur Dioxide"),
    14: ("Treenuts", "Nuts"),
}

# file, SHA-256, heading -> category, headings whose column is drinks (left out),
# whether the key numbers are text (False: the whole key is an image), lines to ignore.
MENUS = [
    {
        "file": "Cheffins-A-La-Carte-Menu-2026.pdf",
        "sha256": "074fa82dbd791b5c521925b4b81d2d75f0086d33432637b6115aa90e8512383f",
        "titles": [],
        "headings": {"Starters": "Starters", "Mains": "Mains"},
        "drinks": [],
        "key_text": True,
        "ignore": ["ALLERGEN KEY:"],
    },
    {
        "file": "CHEFFINS-ALA-CARTE-DESSERTS.pdf",
        "sha256": "897e30d556d469ef193249dd7fc6fcc56b3fe79ec954d943f91fb2217ee561de",
        "titles": ["The secret is to always leave a little extra room for pudding..."],
        "headings": {"Desserts": "Desserts"},
        "drinks": ["Night Caps", "Brandy & Calvados", "Whiskey", "Dessert Wine", "Port"],
        "key_text": True,
        "ignore": [],
    },
    {
        "file": "Cheffins-Sunday-Menu-MAY-2026.pdf",
        "sha256": "2e5edf6c511d9f2ba24e517c05e0277ea2c2623e8d70a21dc8dec8f3ccc23179",
        "titles": ["SUNDAY LUNCH", "The secret is to always leave a little extra room for pudding..."],
        "headings": {"Starters": "Sunday Lunch - Starters", "Mains": "Sunday Lunch - Mains",
                     "Sunday Dessert": "Sunday Dessert"},
        "drinks": ["Night Caps", "Brandy & Calvados", "Whiskey", "Dessert Wine", "Port"],
        "key_text": True,
        "ignore": ["2 COURSES FOR £35 | 3 COURSES £39"],
    },
    {
        "file": "September-Set-Menu-2.pdf",
        "sha256": "f84c787606397b2ca5ab2199c420b2f9379549fa0bc3b2007226e9a6e8c68276",
        "titles": ["CHEFFINS AUTUMN SET MENU", "AVAILABLE MONDAY TO SATURDAY"],
        "headings": {"Starters": "Autumn Set Menu - Starters", "Mains": "Autumn Set Menu - Mains"},
        "drinks": [],
        "key_text": True,
        "ignore": ["2 COURSES FOR £28"],
    },
    {
        "file": "Cheffins-Christmas-Day-Menu-2026.pdf",
        "sha256": "2089f38e36d1fa98158ef05a47450ce74fbdb0d86570ab6e6581e89b4f522fee",
        "titles": ["CHRISTMAS DAY MENU"],
        "headings": {"Starters": "Christmas Day Menu - Starters", "Mains": "Christmas Day Menu - Mains",
                     "Desserts": "Christmas Day Menu - Desserts"},
        "drinks": [],
        "key_text": False,
        "ignore": ["TWO COURSES £85 | THREE COURSES £100"],
    },
]

# The Chateaubriand's sharing-platter line, and the add-on it introduces.
ADD_ON_LINE = re.compile(r"^(Sharing Platter for two persons) - (\d+) \| Add (King Prawns in Garlic Butter) - (\d+)$")
ADD_ON_NAME = "ADD KING PRAWNS IN GARLIC BUTTER"

PRICE = re.compile(r"^£?\d+(\.\d\d)?$")
CODES = re.compile(r"^\d+(\s*,\s*\d+)*$")
VARIANT_CODES = re.compile(r"^(\d+(?:\s*,\s*\d+)*)((?:\s*,\s*\(\s*[A-Za-z][A-Za-z -]*?\s+-\s+\d+(?:\s*,\s*\d+)*\s*\))+)$")
VARIANT = re.compile(r"\(\s*([A-Za-z][A-Za-z -]*?)\s+-\s+(\d+(?:\s*,\s*\d+)*)\s*\)")
DISCLAIMER = "We do our best to reduce the risk of cross-contamination"
GAP = 20  # pt between words that starts a new segment of a line


def fail(message):
    sys.exit(f"cheffins.py: STOPPED: {message}")


def font_of(word):
    return word["fontname"].split("+")[-1]


def kind_of(font, text):
    if font == "ITCEdwardianScriptCom-Bold":
        return "heading"
    if font == "Lato-Bold":
        return "codes"
    if font == "Lato-Light":
        return "desc"
    if font in ("Bentham-Regular", "Lato-Regular") and PRICE.match(text):
        return "price"
    if font == "Bentham-Regular":
        return "name"
    fail(f"unexpected font {font} for {text!r}")


def segments(page):
    """Page text as segments: runs of words on one line, in one font, with no wide gap."""
    words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=1.5)
    words.sort(key=lambda w: (w["top"], w["x0"]))
    lines = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 2:
            lines[-1].append(w)
        else:
            lines.append([w])
    out = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        runs = [[line[0]]]
        for w in line[1:]:
            last = runs[-1][-1]
            if w["x0"] - last["x1"] > GAP or font_of(w) != font_of(last):
                runs.append([w])
            else:
                runs[-1].append(w)
        # A price set close after a name ("HOT OOZING ASH GOATS CHEESE 13"): a trailing number
        # set apart by more than twice the word spacing (2.4pt).
        split = []
        for run in runs:
            if len(run) > 1 and PRICE.match(run[-1]["text"]) and run[-1]["x0"] - run[-2]["x1"] > 4:
                split += [run[:-1], run[-1:]]
            else:
                split.append(run)
        runs = split
        for run in runs:
            text = " ".join(" ".join(w["text"] for w in run).split())
            out.append({"text": text, "font": font_of(run[0]), "size": run[0]["size"],
                        "top": min(w["top"] for w in run), "x0": run[0]["x0"], "x1": run[-1]["x1"],
                        "line": lines.index(line)})
    return out


def column_of(seg, mid):
    if seg["x1"] <= mid + 3:
        return "L"
    if seg["x0"] >= mid - 3:
        return "R"
    return "F"


def parse_codes(text, where):
    """'1, 4, 6' -> ({1, 4, 6}, {}); '8, (Pistachio - 8, 14)' -> ({8}, {'Pistachio': {8, 14}})."""
    variants = {}
    if CODES.match(text):
        base = text
    else:
        m = VARIANT_CODES.match(text)
        if not m:
            fail(f"{where}: can't read codes {text!r}")
        base = m.group(1)
        for name, codes in VARIANT.findall(m.group(2)):
            variants[name] = {int(c) for c in re.findall(r"\d+", codes)}
    numbers = [int(c) for c in re.findall(r"\d+", base)]
    for n in numbers + [n for v in variants.values() for n in v]:
        if n not in KEY:
            fail(f"{where}: code {n} isn't in the key (1-14)")
    if len(numbers) != len(set(numbers)):
        fail(f"{where}: a code is repeated in {text!r}")
    return set(numbers), variants


def read_menu(path, menu):
    dishes, no_codes, skipped_drinks, notes = [], [], 0, []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            n = page.page_number
            mid = page.width / 2
            segs = segments(page)
            where = f"{menu['file']} p{n}"

            # The key's numbers, 1-14 in order on one line (text on all but the Christmas menu).
            by_line = {}
            for s in segs:
                by_line.setdefault(s["line"], []).append(s)
            key_lines = [l for l, ss in by_line.items() if [s["text"] for s in ss] == [str(i) for i in range(1, 15)]]
            disclaimer = [s for s in segs if s["text"].startswith(DISCLAIMER)]
            if len(disclaimer) != 1:
                fail(f"{where}: expected one allergen disclaimer, found {len(disclaimer)}")
            if menu["key_text"]:
                if len(key_lines) != 1:
                    fail(f"{where}: expected the key numbers 1-14 on one line, found {len(key_lines)}")
                xs = [s["x0"] for s in by_line[key_lines[0]]]
                if xs != sorted(xs):
                    fail(f"{where}: key numbers not in left-to-right order")
                end = by_line[key_lines[0]][0]["top"]
            else:
                if key_lines:
                    fail(f"{where}: key numbers found as text; check the key again")
                end = disclaimer[0]["top"]

            headings = [s for s in segs if kind_of(s["font"], s["text"]) == "heading"]
            if not headings:
                fail(f"{where}: no section headings")
            start = min(h["top"] for h in headings)
            for s in segs:
                if s["top"] < start - 1 and s["text"] not in menu["titles"]:
                    fail(f"{where}: unexpected title text {s['text']!r}")

            body = [s for s in segs if start - 1 <= s["top"] < end - 1]
            for s in body:
                s["kind"] = kind_of(s["font"], s["text"])
                s["col"] = column_of(s, mid)
            # Codes printed straight under part of a full-width line belong to that line.
            for s in body:
                if s["kind"] == "codes" and s["col"] != "F":
                    above = [f for f in body if f["col"] == "F" and f["kind"] != "codes"
                             and 0 < s["top"] - f["top"] < 16 and f["x0"] <= s["x0"] and s["x1"] <= f["x1"]]
                    if above:
                        s["col"] = "F"

            # Which heading applies to each column: a full-width heading applies to all.
            def category_for(seg):
                applying = [h for h in headings if h["top"] <= seg["top"] + 1 and h is not seg
                            and (column_of(h, mid) in ("F", seg["col"]) or seg["col"] == "F")]
                if not applying:
                    fail(f"{where}: {seg['text']!r} is above every heading")
                return max(applying, key=lambda h: h["top"])["text"]

            for h in headings:
                if h["text"] not in menu["headings"] and h["text"] not in menu["drinks"]:
                    fail(f"{where}: unknown heading {h['text']!r}")

            for col in ("L", "R", "F"):
                rows = {}
                for s in body:
                    if s["col"] == col and s["kind"] != "heading":
                        rows.setdefault(s["line"], []).append(s)
                current = None
                last_name_top = None

                def close():
                    if current is None:
                        return
                    if current["codes"] is None:
                        no_codes.append(current)
                    else:
                        dishes.append(current)

                for line in sorted(rows, key=lambda l: rows[l][0]["top"]):
                    row = sorted(rows[line], key=lambda s: s["x0"])
                    heading = category_for(row[0])
                    if heading in menu["drinks"]:
                        skipped_drinks += 1
                        continue
                    category = menu["headings"][heading]
                    text = " ".join(s["text"] for s in row)
                    kinds = [s["kind"] for s in row]
                    if text in menu["ignore"]:
                        notes.append(f"{where}: {text}")
                        continue
                    m = ADD_ON_LINE.match(text)
                    if m:
                        if current is None or current["price"] or current["codes"] is None:
                            fail(f"{where}: {text!r} doesn't follow a finished dish")
                        current["price"] = m.group(2)
                        current["description"] += f" | {m.group(1)}"
                        close()
                        current = {"menu": menu["file"], "page": n, "category": category, "name": ADD_ON_NAME,
                                   "description": "", "price": m.group(4), "codes": None, "variants": {},
                                   "top": row[0]["top"], "col": col, "printed": f"Add {m.group(3)}"}
                        last_name_top = None
                        continue
                    if "name" in kinds:
                        if kinds[0] != "name" or any(k not in ("name", "price") for k in kinds) or kinds.count("price") > 1 \
                                or (kinds.count("price") == 1 and kinds[-1] != "price"):
                            fail(f"{where}: can't read the line {text!r} ({kinds})")
                        name = " ".join(s["text"] for s in row if s["kind"] == "name")
                        price = next((s["text"].lstrip("£") for s in row if s["kind"] == "price"), "")
                        size = row[0]["size"]
                        wrapped = (current is not None and not price and not current["description"]
                                   and current["codes"] is None and last_name_top is not None
                                   and row[0]["top"] - last_name_top < 1.6 * size and current["category"] == category)
                        if wrapped:
                            current["name"] += " " + name
                        else:
                            close()
                            current = {"menu": menu["file"], "page": n, "category": category, "name": name,
                                       "description": "", "price": price, "codes": None, "variants": {},
                                       "top": row[0]["top"], "col": col}
                        bare = re.sub(r"\d+g\b", "", name)  # "(700g)"
                        if bare != bare.upper():
                            fail(f"{where}: dish name {name!r} isn't in capitals; is it really a dish?")
                        last_name_top = row[0]["top"]
                        continue
                    if len(set(kinds)) != 1:
                        fail(f"{where}: mixed line {text!r} ({kinds})")
                    if current is None:
                        fail(f"{where}: {kinds[0]} {text!r} before any dish")
                    if current["category"] != category:
                        fail(f"{where}: {text!r} is under a different heading from its dish {current['name']!r}")
                    if kinds[0] == "desc":
                        if current["codes"] is not None:
                            fail(f"{where}: description {text!r} after the codes of {current['name']!r}")
                        current["description"] = (current["description"] + " " + text).strip()
                    elif kinds[0] == "codes":
                        if current["codes"] is not None:
                            fail(f"{where}: second codes line {text!r} for {current['name']!r}")
                        current["codes"], current["variants"] = parse_codes(text, f"{where} {current['name']!r}")
                        current["printed_codes"] = text
                    elif kinds[0] == "price":
                        if current["price"]:
                            fail(f"{where}: second price {text!r} for {current['name']!r}")
                        current["price"] = text.lstrip("£")
                    last_name_top = None
                close()
    return dishes, no_codes, skipped_drinks, notes


def expand(dish):
    """One CSV row per dish, or one per flavour when the codes name flavours."""
    if not dish["variants"]:
        return [(dish["name"], dish["description"], dish["codes"], None)]
    flavours = [f.strip() for f in dish["description"].split("|")]
    for variant in dish["variants"]:
        matches = [f for f in flavours if f == variant or f.startswith(variant + " ")]
        if len(matches) != 1:
            fail(f"{dish['name']!r}: codes name {variant!r}, which matches {matches} of {flavours}")
    rows = []
    for flavour in flavours:
        codes = set(dish["codes"])
        for variant, extra in dish["variants"].items():
            if flavour == variant or flavour.startswith(variant + " "):
                codes |= extra
        note = None
        if flavour != flavour.split()[0] and any(flavour.startswith(v + " ") for v in dish["variants"]):
            note = f"'{flavour}' takes the codes printed for '{flavour.split()[0]}'"
        rows.append((f"{dish['name']} - {flavour}", "", codes, note))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", help="directory holding the PDFs, under their published file names")
    parser.add_argument("--out", default="Imports/charts-on-hold/cheffins.csv")
    parser.add_argument("--any-version", action="store_true",
                        help="read PDFs other than the ones this script was checked against")
    args = parser.parse_args()

    all_dishes, all_no_codes, notes = [], [], []
    for menu in MENUS:
        path = os.path.join(args.sources, menu["file"])
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if digest != menu["sha256"] and not args.any_version:
            fail(f"{path} isn't the version this script was checked against (SHA-256 {digest}). "
                 f"Check the new menu and its key by eye, then run with --any-version.")
        dishes, no_codes, skipped, menu_notes = read_menu(path, menu)
        # Reading order: full-width dishes above the columns, then left column, right column,
        # then full-width dishes below.
        order = {"L": 1, "R": 2}
        first_col_top = {}
        for d in dishes + no_codes:
            if d["col"] != "F":
                key = (d["page"], d["category"])
                first_col_top[key] = min(first_col_top.get(key, 1e9), d["top"])
        section_top = {}
        for d in dishes + no_codes:
            key = (d["page"], d["category"])
            section_top[key] = min(section_top.get(key, 1e9), d["top"])

        def position(d):
            if d["col"] == "F":
                rank = 0 if d["top"] < first_col_top.get((d["page"], d["category"]), 1e9) else 3
            else:
                rank = order[d["col"]]
            return (d["page"], section_top[(d["page"], d["category"])], rank, d["top"])
        dishes.sort(key=position)
        all_dishes += dishes
        all_no_codes += no_codes
        notes += menu_notes
        notes.append(f"{menu['file']}: {len(dishes)} dishes with codes, {len(no_codes)} without, "
                     f"{skipped} drinks lines left out")

    rows, flavour_notes = [], []
    for d in all_dishes:
        for name, description, codes, note in expand(d):
            labels = {KEY[c][1]: "Y" for c in codes}
            rows.append({"category": d["category"], "dish": name, "description": description,
                         "price": d["price"], "labels": labels, "source": d, "codes": codes})
            if note:
                flavour_notes.append(f"{name}: {note}")

    seen = set()
    for r in rows:
        key = (r["category"], r["dish"])
        if key in seen:
            fail(f"'{r['dish']}' appears twice in '{r['category']}'")
        seen.add(key)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for r in rows:
            writer.writerow([r["category"], r["dish"], r["description"], r["price"]]
                            + [r["labels"].get(a, "") for a in ALLERGENS])

    category = None
    for r in rows:
        if r["category"] != category:
            category = r["category"]
            print(f"--- {category}")
        codes = ", ".join(str(c) for c in sorted(r["codes"]))
        names = ", ".join(KEY[c][0] for c in sorted(r["codes"]))
        price = f"  £{r['price']}" if r["price"] else ""
        print(f"p{r['source']['page']} {r['dish']}{price}\n      [{codes}] {names}")
    print(f"\n{len(rows)} rows written to {args.out}")
    print("\nLEFT OUT (no codes printed, so 'no allergens' can't be told from 'not listed'):")
    for d in all_no_codes:
        print(f"  {d['menu']} p{d['page']} [{d['category']}] {d['name']}"
              + (f"  £{d['price']}" if d["price"] else ""))
    print("\nNot read: Kids-Menu-Copy-2.pdf (KIDS MENU) prints no allergen codes.")
    if flavour_notes:
        print("\nFlavour rows:", *flavour_notes, sep="\n  ")
    print("\nNotes:", *notes, sep="\n  ")


if __name__ == "__main__":
    main()
