#!/usr/bin/env python3
"""Salty Dog Café, Bar & Bistro (La Neuve Route, St Aubin), takeaway menu only: read its allergen
codes into Imports/menus/salty-dog.csv.

Source: "Salty Kitchen Takeaway ALLERGY JAN 26", two A3 pages exported from Word on 13 January
2026 ("UPDATED – January 2026"), linked from https://saltydogbistro.com/ as
https://saltydogbistro.com/wp-content/uploads/2026/01/Salty-Kitchen-Takeaway-ALLERGY-JAN-26-WEB.pdf
(SHA-256 90b5782992c43466922d3fdc65acb7d01b82a6bdab1d163e9dd1f6df72eb938a).
Page 1 is the takeaway menu in three columns; page 2 is the allergen statement and key. The
restaurant's dine-in menus (à la carte, small plates, specials, sweets ...) print no codes.

The key, printed on page 2 under "These allergens are contained in dishes marked with the
following codes":
  Celery = 1  Gluten = 2  Crustaceans = 3  Eggs = 4  Fish = 5  Lupin = 6  Milk = 7
  Mollusc = 8  Mustard = 9  Nuts = 10  Peanuts = 11  Sesame seeds = 12  Soya = 13
  Sulphur Dioxide = 14  (vegan = VG)
(the standard order). The script reads it from the page and stops if it differs.

THE DISH NAMES, SECTION HEADINGS AND PRICES ARE PICTURES, not text: on page 1 only the
descriptions and the codes are in the PDF's text layer. So:
  * the descriptions and codes are checked against the text layer: every word on page 1 lies
    in one column, and each column's words, in reading order, are exactly the transcribed
    items' text, word for word; each row's codes are the groups printed in its item;
  * the names, headings and prices are transcribed (ITEMS) from the page rendered at 200 dpi,
    and the script can't check them. If the PDF changes, re-read them by eye.

Codes are numbers separated by spaces, e.g. "(3 7 8 14)"; two are misprinted with an extra
bracket, "VG ((2 11 13)" and "(5 7 14))", and are read as the group inside. "(…...)" is an
unfilled placeholder, not a code: those dishes (the whole Salty Puppy children's selection
and the doughnuts) are left out, as is every dish printed with no codes. The menu doesn't
say every dish is coded ("we cannot guarantee that any dish is completely free from
allergens"), so no codes can't be read as no allergens.

Choices: the Penang curry and the chilli garlic coriander sauce print a row per filling
(Vegetable / Chicken / King Prawn) with its own codes and price; each is its own CSV row. The
stroganoffs print codes only for the jasmine-rice version; the "- OR - Chips" and "Parmesan
Truffle Chips" versions have none and are left out.

category is the menu's own section heading (a picture, transcribed as printed).

Usage:
  python3 Tools/importers/venues/salty-dog.py Salty-Kitchen-Takeaway-ALLERGY-JAN-26-WEB.pdf \
      [--out Imports/menus/salty-dog.csv] [--any-version]
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

EXPECTED_SHA256 = "90b5782992c43466922d3fdc65acb7d01b82a6bdab1d163e9dd1f6df72eb938a"

# The heading above it ("These allergens are contained in dishes marked with the following
# codes") is a picture; the list itself is text.
KEY_TEXT = ("Celery = 1 Gluten = 2 Crustaceans = 3 Eggs = 4 Fish = 5 Lupin = 6 Milk = 7 Mollusc = 8 "
            "Mustard = 9 Nuts = 10 Peanuts = 11 Sesame seeds = 12 Soya = 13 Sulphur Dioxide = 14")
KEY_NAMES = {"Celery": "Celery", "Gluten": "Gluten", "Crustaceans": "Crustaceans", "Eggs": "Eggs",
             "Fish": "Fish", "Lupin": "Lupin", "Milk": "Milk", "Mollusc": "Molluscs", "Mustard": "Mustard",
             "Nuts": "Nuts", "Peanuts": "Peanuts", "Sesame seeds": "Sesame", "Soya": "Soybeans",
             "Sulphur Dioxide": "Sulphur Dioxide"}
CODE_GROUP = re.compile(r"\((\d+(?: \d+)*)\)")
PLACEHOLDER = "(…...)"


def fail(message):
    sys.exit(f"salty-dog.py: STOPPED: {message}")


def norm(text):
    text = " ".join(text.split())
    text = re.sub(r"\(\s+", "(", text)
    return re.sub(r"\s+\)", ")", text)


def strip_codes(text):
    return norm(CODE_GROUP.sub("", text).replace("()", "").replace("((", "("))


def T(text):
    """Text-layer words that aren't a dish (contact details, rules, sub-heading text)."""
    return {"kind": "text", "text": norm(text), "category": None}


def HEADING(category, text=""):
    """A section heading: a picture (not in the text layer), plus any text-layer words in it."""
    return {"kind": "text", "text": norm(text), "category": category}


def R(dish, price, desc, codes):
    return {"dish": dish, "price": price, "desc": desc, "codes": codes}


def DISH(name, price, text, *rows, left_out=None):
    """name and price: read from the picture. text: the item's words in the text layer.
    With no rows, one row: the name, the text without its codes, every code group in it."""
    text = norm(text)
    groups = CODE_GROUP.findall(text)
    if not rows and groups:
        rows = [R(name, price, strip_codes(text), groups)]
    if not groups:
        left_out = left_out or ("codes left as a placeholder “(…...)”" if PLACEHOLDER in text else "no allergen codes")
    return {"kind": "dish", "name": name, "price": price, "text": text, "rows": list(rows), "left_out": left_out}


STARTERS = "STARTERS, SMALL PLATES, SHARING & GRAZING"
MAINS = "SALTY’S CLASSIC - MAINS"
SUNDAY = "SUNDAY SPECIALS (Sunday Only)"
SEASONAL = "SEASONAL SPECIALS"
SIDES = "SIDES"
PUPPY = "SALTY PUPPY SELECTION"
SWEETS = "SWEETS"
RULE = "_" * 63
CURRY_VEG = "Potato, Mushrooms, Peppers, Pak Choi, Green Beans & Snow Peas"

# (column x0, x1 in pt) → items top to bottom. Names and prices are the pictures' text.
COLUMNS = [
    ((0, 390), [
        T("WEDNESDAY TO SUNDAY EVENINGS 5.30-8.30PM + SUNDAY LUNCH 12.30-3PM For the best possible "
          "quality PRE-ORDERS RECOMMENDED AS AVAILABILITY LIMITED WWW.FOOD.JE/SALTYDOG La Neuve Route - "
          "St. Aubin - St. Brelade - JE3 8BS T: (01534) 874263 - or - 742760 info@saltydog.je"),
        HEADING(STARTERS, RULE),
        DISH("The Famous Salty Dog King Prawns “Pana”", "10.5",
             "Oyster Sauce, Garlic & Black Bean Sauce, Sizzling Hot Pan & Lime Squeeze (3 7 8 14)"),
        DISH("Crispy Aromatic Duck Salad", "9.5",
             "Beansprouts, Sugar Snaps, Pineapple, Toasted Peanuts & Sesame Seeds, Teriyaki Dressing (2 11 12 13)"),
        DISH("Bang Bang Chicken Wings", "9.5", "Plum Sauce, Chilli & Coriander (2 13)"),
        DISH("Plum & Hoisin Crispy Sticky Beef", "9.5", "Chilli, Coriander, Sesame (2 12 13)"),
        DISH("Gnocco Fritto Board", "9.5",
             "Italian Chacuterie, Nduja Fondue & Crispy Dough Pillows for Stuffing & Dipping (2 7 14)"),
        DISH("Winter Salad", "9.5", "Pear, Beetroot, Red & White Endive, Pomegranate, Blue Cheese Crumble "
             "Toasted Sunflower Seeds Red Wine Vinegar Dressing - VG (9 14)"),
        DISH("Chicken Croquetas", "9.5", "Shredded Chicken, Serrano Ham, Bechamel (2 4 7 14)"),
        DISH("Cauliflower Tiki Bonbons", "8.5", "Spice Roast Cauliflower, Oat Crumb & Garam Masala - VG (9)"),
        DISH("Crispy Home Made Katso Spring Rolls", "9.5", "Alfalfa & Carrot Salad & Spiced Raita - VG (1 2 9 13)"),
        DISH("Tofu Satay", "9.5", "Glass Noodle, Beansprout, Salad, Nam Jhim Dressing - VG ((2 11 13)"),
    ]),
    ((390, 770), [
        HEADING(MAINS, "- " + RULE),
        DISH("Grilled Mini Beef Fillet & Seared King Prawns", "28", "Ginger & Spring Onion, Cracked Black "
             "Pepper Sauce, Snow Peas, Shitake Mushrooms, Jasmine Rice (3 7 8 14)"),
        DISH("The Salty Dog Beef Stroganoff", "22", "Beef Fillet, Mushrooms, Onions, Mustard & Cream, Jasmine "
             "Rice (7 9) - OR - Chips Parmesan Truffle Chips - (Vegan cheese available on request)",
             R("The Salty Dog Beef Stroganoff", "22",
               "Beef Fillet, Mushrooms, Onions, Mustard & Cream, Jasmine Rice", ["7 9"]),
             left_out="the Chips (23) and Parmesan Truffle Chips (25) versions: no allergen codes"),
        DISH("The Salty Dog Mushroom Stroganoff", "18", "Mushrooms, Onions, Mustard & Cream Jasmine Rice - VG "
             "(1 9 14) - OR - Chips Parmesan Truffle Chips - Vegan cheese available on request",
             R("The Salty Dog Mushroom Stroganoff", "18",
               "Mushrooms, Onions, Mustard & Cream, Jasmine Rice - VG", ["1 9 14"]),
             left_out="the Chips (19) and Parmesan Truffle Chips (21) versions: no allergen codes"),
        DISH("Peruvian Spiced Chicken Breast", "21", "Grilled Zucchini, Yuzu Hot Sauce & Chips (9)"),
        DISH("Home Made Jerusalem Artichoke Gnocchi", "17", "Primavera Sauce, Asparagus, Broad Beans, Peas & "
             "Spring Onion, Baby Spinach & Parmesan Style Cheese - VG (2)"),
        DISH("Tofu Satay", "18", "Glass Noodle, Beansprout, Salad, Nam Jhim Dressing - VG (2 11 13)"),
        DISH("Malaysian Penang Curry", "", "Peanut, Coconut, Kaffir, Lemon Grass, Cumin, Chilli & Jasmine Rice "
             f"- {CURRY_VEG} - VG (11) (5 11) (3 5 11)",
             R("Malaysian Penang Curry – Vegetable", "18", "Peanut, Coconut, Kaffir, Lemon Grass, Cumin, Chilli & "
               f"Jasmine Rice; Vegetable - {CURRY_VEG} - VG", ["11"]),
             R("Malaysian Penang Curry – Chicken", "20", "Peanut, Coconut, Kaffir, Lemon Grass, Cumin, Chilli & "
               "Jasmine Rice; Chicken", ["5 11"]),
             R("Malaysian Penang Curry – King Prawn", "22", "Peanut, Coconut, Kaffir, Lemon Grass, Cumin, Chilli & "
               "Jasmine Rice; King Prawn", ["3 5 11"])),
        DISH("The Chilli Garlic Coriander Sauce", "", f"- {CURRY_VEG} (7 8 14) (7 8 14) (7 8 14)",
             R("The Chilli Garlic Coriander Sauce – Vegetable", "18", f"Vegetable - {CURRY_VEG}", ["7 8 14"]),
             R("The Chilli Garlic Coriander Sauce – Chicken", "20", "Chicken", ["7 8 14"]),
             R("The Chilli Garlic Coriander Sauce – King Prawn", "22", "King Prawn", ["7 8 14"])),
        HEADING(SUNDAY, "(Sunday Only) - Pre-orders by 11.30am " + RULE),
        DISH("Traditional Roast Beef", "20", "Savoy Cabbage & Chilli Bacon, Honey Glazed Carrots, Rosemary "
             "Roasted Potatoes, Yorkshire Pudding, Homemade Beef Gravy, Cauliflower Cheese, Salty Sunday Spice "
             "Mustard Root Accompaniment"),
    ]),
    ((770, 1191), [
        HEADING(SEASONAL, "_" * 62),
        DISH("Lobster Mac n’ Cheese", "30", "Green Beans and Asparagus (2 3 4 7 9)"),
        DISH("Dover Sole", "37", "Filleted, Classic Meunier, New Potatoes, Greens (5 7 14))"),
        HEADING(SIDES, RULE),
        DISH("Nann Bread", "1", "(2)"),
        DISH("Jasmine Rice", "3", ""),
        DISH("Chips", "4", ""),
        DISH("Truffle Chips", "6", "(7)"),
        DISH("Sauté Asian Greens", "5", "Pak Choi, Green Beans, Mange Tout (8)"),
        DISH("Bowl of Greens", "5", "Kale, Mangetout, Broccoli, Miso & Lemon Butter (7 13)"),
        DISH("House Salad Bowl", "4", "Mixed Leaf, Cucumber, Tomato, Capsicum & Vinaigrette (9)"),
        DISH("Thai Crispy Salad", "6", "Beansprouts, Sugar Snaps, Pineapple, Basil, Mint, Coriander, Toasted "
             "Peanuts, Nam Jhim Dressing - VG (11)"),
        HEADING(PUPPY, RULE),
        DISH("Mac n’ Cheese", "8", "Past & Creamy Cheese Sauce (…...)"),
        DISH("Battered Fish Goujons", "8", "Vegetables & Chunky Hand Cut Chips (…...)"),
        DISH("Mild Coconut Chicken Curry & Rice", "8", "(…...)"),
        HEADING(SWEETS, "_" * 56),
        DISH("“Lock Down” Doughnuts", "8", "3 dips – Raspberry Jam, Milk Chocolate & Crème Anglaise (…...)"),
        DISH("Gooey Jersey Black Butter & Banana Toffee Pudding", "8", "Home Made Clotted Chantilly Cream (2 4 7 14)"),
        DISH("Chocolate & Peanut Butter Cheesecake", "8", "Salted Caramel (2 7 11)"),
        DISH("Cheese Platter", "10.5", "Westcombe Cheddar, Form D’Ambert Blue, Normandy Camembert Fig Chutney, "
             "Grapes & Rustic Crackers, Biscuits - Gluten Free Option available (1 2 7 10 12)"),
    ]),
]


def words_of(page):
    words = page.extract_words(extra_attrs=["size"])
    for w in words:
        w["cx"], w["cy"] = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
    return words


def stream(words, x0, x1, tolerance=3.5):
    inside = sorted((w for w in words if x0 <= w["cx"] < x1), key=lambda w: (w["cy"], w["x0"]))
    lines = []
    for w in inside:
        if lines and abs(lines[-1][0] - w["cy"]) <= tolerance:
            lines[-1][1].append(w)
        else:
            lines.append([w["cy"], [w]])
    return norm(" ".join(" ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"])) for _, ws in lines)), inside


def read_key(page):
    text, _ = stream(words_of(page), 0, page.width)
    if KEY_TEXT not in text:
        fail("page 2 doesn't print the expected key")
    if "UPDATED– January 2026" not in text:
        fail("page 2 doesn't say 'UPDATED– January 2026'")
    key = {}
    for name, number in re.findall(r"([A-Z][a-z]+(?: [a-zA-Z]+)?) = (\d+)", KEY_TEXT):
        if name not in KEY_NAMES:
            fail(f"key entry {name} = {number} isn't in KEY_NAMES")
        key[int(number)] = KEY_NAMES[name]
    if sorted(key) != list(range(1, 15)) or sorted(key.values()) != sorted(ALLERGENS):
        fail("the key doesn't give each of the 14 allergens one number")
    return key


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default=os.path.join(root, "Imports", "charts-on-hold", "salty-dog.csv"))
    parser.add_argument("--any-version", action="store_true",
                        help="read a PDF other than the one this script was checked against")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EXPECTED_SHA256 and not args.any_version:
        fail(f"{args.pdf} isn't the January 2026 takeaway menu this script was checked against "
             f"(SHA-256 {digest}). Re-read the names and prices from the rendered page, then run with --any-version.")

    rows, left_out = [], []
    with pdfplumber.open(args.pdf) as pdf:
        if len(pdf.pages) != 2:
            fail(f"expected 2 pages, found {len(pdf.pages)}")
        key = read_key(pdf.pages[1])
        words = words_of(pdf.pages[0])
        claimed = set()
        for (x0, x1), items in COLUMNS:
            text, inside = stream(words, x0, x1)
            claimed |= {id(w) for w in inside}
            expected = norm(" ".join(item["text"] for item in items))
            if text != expected:
                i = next((i for i, (a, b) in enumerate(zip(text, expected)) if a != b), min(len(text), len(expected)))
                fail(f"column x={x0}-{x1} doesn't match the transcription:\n  PDF: …{text[max(0, i - 60):i + 60]!r}"
                     f"\n  transcribed: …{expected[max(0, i - 60):i + 60]!r}")
            category = None
            for item in items:
                if item["kind"] == "text":
                    category = item["category"] or category
                    continue
                groups = CODE_GROUP.findall(item["text"])
                if item["rows"] and len(item["rows"]) > 1 and len(groups) != len(item["rows"]):
                    fail(f"{item['name']!r}: {len(item['rows'])} rows but {len(groups)} code groups")
                used = []
                for row in item["rows"]:
                    for g in row["codes"]:
                        if g not in groups:
                            fail(f"{row['dish']!r} takes ({g}), which {item['name']!r} doesn't print")
                    used += row["codes"]
                    found = set()
                    for g in row["codes"]:
                        for number in g.split():
                            if int(number) not in key:
                                fail(f"{row['dish']!r}: code {number} isn't in the key")
                            found.add(key[int(number)])
                    rows.append({"category": category, "dish": row["dish"], "description": row["desc"],
                                 "price": row["price"], "codes": " + ".join(f"({g})" for g in row["codes"]),
                                 "allergens": found})
                if set(groups) - set(used):
                    fail(f"{item['name']!r} prints codes {sorted(set(groups) - set(used))} that no row uses")
                if item["left_out"]:
                    left_out.append((category, item["name"], item["price"], item["text"], item["left_out"]))
        stray = [w["text"] for w in words if id(w) not in claimed]
        if stray:
            fail(f"page 1: words outside every column: {stray}")

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
            print(f"--- {category}")
        print(f"  {r['dish']} £{r['price']} {r['codes']}: {', '.join(a for a in ALLERGENS if a in r['allergens'])}")
    print(f"\n{len(rows)} rows written to {args.out}")
    print("\nLeft out:")
    for category, name, price, text, why in left_out:
        print(f"  [{category}] {name} £{price}: {text!r} → {why}")


if __name__ == "__main__":
    main()
