#!/usr/bin/env python3
"""Sorrento (Le Boulevard, St Aubin): read its menu's allergen codes into Imports/menus/sorrento.csv.

Source: "D1549 Sorrento Summer Menu 2026", two pages (each three folded panels) made with
InDesign on 28 April 2026, linked from https://www.sorrento.je/ as
http://www.sorrento.je/wp-content/uploads/2026/06/D1549-Sorrento-Summer-Menu-2026.pdf
(SHA-256 502eefab27734601b0af2c9533444c06ec0cd8816470c459e5934afe20289515).
Page 1 holds starters, sides, pasta & risotto, fish, meats, desserts & cheeses; page 2 the
pizzas, the contact panel and the cover. The site's wine and drinks lists carry no codes.

Layout: centred panels. Each dish is its name, a description, then "£price (codes)", e.g.
"Caprese (V) / Fresh mozzarella, tomatoes and basil. / £10.95 (7)"; desserts and garlic breads
print the price and codes on the name line. The key, printed on both pages:
  Allergens: 1 – Celery, 2 – Cereals containing gluten, 3 – Crustaceans, 4 – Eggs, 5 – Fish,
  6 – Lupins, 7 – Milk, 8 – Molluscs, 9 – Mustard, 10 – Nuts, 11 – Peanuts, 12 – Sesame seeds,
  13 – Soyabeans, 14 – Sulphur Dioxide,
(the standard order). The script reads the numbers from this printed key (KEY_NAMES maps each
name to the app's allergen) and stops if it differs.

How it reads the pages: the items are transcribed below (PAGES), panel by panel, from the
rendered pages. The script checks the transcription against the PDF: every word on each
page lies in exactly one region; each region's words, in reading order, are exactly its
items' printed text; each row's codes and price are the ones printed in its item. So the
codes in the CSV are the PDF's own text; only which dish they belong to comes from reading
the rendered page.

Left out, and listed when the script runs: anything printed without codes. The menu doesn't
say every dish is coded ("please ask the management for assistance"), so no codes can't be
read as no allergens: two side salads, the Milanese's spaghetti add-on, the gluten-free
pizza base and extra toppings. "Choice of sauces £3.00 (7)" under the meats is its own row.
category is the menu's own heading, as printed.

Usage:
  python3 Tools/importers/venues/sorrento.py D1549-Sorrento-Summer-Menu-2026.pdf \
      [--out Imports/menus/sorrento.csv] [--any-version]
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

EXPECTED_SHA256 = "502eefab27734601b0af2c9533444c06ec0cd8816470c459e5934afe20289515"

KEY_TEXT = ("Allergens: 1 – Celery, 2 – Cereals containing gluten, 3 – Crustaceans, 4 – Eggs, "
            "5 – Fish, 6 – Lupins, 7 – Milk, 8 – Molluscs, 9 – Mustard, 10 – Nuts, 11 – Peanuts, "
            "12 – Sesame seeds, 13 – Soyabeans, 14 – Sulphur Dioxide,")
KEY_NAMES = {"Celery": "Celery", "Cereals containing gluten": "Gluten", "Crustaceans": "Crustaceans",
             "Eggs": "Eggs", "Fish": "Fish", "Lupins": "Lupin", "Milk": "Milk", "Molluscs": "Molluscs",
             "Mustard": "Mustard", "Nuts": "Nuts", "Peanuts": "Peanuts", "Sesame seeds": "Sesame",
             "Soyabeans": "Soybeans", "Sulphur Dioxide": "Sulphur Dioxide"}
CODE_GROUP = re.compile(r"\((\d+(?:\s*,\s*\d+)*)\s*,?\)")   # "(2, 4, 7, 8,)" is printed once
CONCERNED = ("If you are concerned about the presence of nuts, small bones, seeds, sources of gluten or "
             "other allergies in our food please ask the management for assistance when choosing your meal")


def fail(message):
    sys.exit(f"sorrento.py: STOPPED: {message}")


def norm(text):
    text = " ".join(text.split())
    text = re.sub(r"\(\s+", "(", text)
    return re.sub(r"\s+\)", ")", text)


def H(printed, category=None):
    """Printed text that isn't a dish. With category, starts that section."""
    return {"kind": "text", "printed": norm(printed), "category": category}


def D(printed, dish=None, desc="", price="", why=None):
    """A printed item: its exact text, and the row it becomes (or why it's left out)."""
    return {"kind": "dish", "printed": norm(printed), "dish": dish, "desc": desc, "price": price, "why": why}


def S(name, desc, price, codes):
    """Name, description, then '£price (codes)'."""
    printed = " ".join(p for p in (name, desc, f"£{price}", f"({codes})" if codes else "") if p)
    return D(printed, name, desc, price) if codes else D(printed, why="no allergen codes")


def I(name, price, codes, desc=""):
    """'Name £price (codes)' on one line, then the description."""
    printed = " ".join(p for p in (name, f"£{price}", f"({codes})" if codes else "", desc) if p)
    return D(printed, name, desc, price) if codes else D(printed, why="no allergen codes")


KEY_BAND = H(KEY_TEXT + " (V) = Vegetarian (VG)= Vegan")

PAGES = {
    1: [
        ((0, 0, 475, 590), None, [
            H("Antipasti-Starter", "Antipasti-Starter"),
            S("Caprese (V)", "Fresh mozzarella, tomatoes and basil.", "10.95", "7"),
            S("Prosciutto di Parma DOC, pomodorini, rucola, focaccia calda",
              "Parma ham DOC, cherry tomatoes, rocket and home-made focaccia", "13.95", "2"),
            S("Carpaccio di manzo", "Thinly sliced raw beef served with sun dried tomato, parmesan chips, "
              "rocket salad and a drizzle of olive oil", "13.95", "7"),
            S("Vitello tonnato", "Chilled veal thinly sliced and served with creamy sauce made of tuna and "
              "capers, sundried tomatoes", "13.95", "4,5"),
            S("Carpaccio di Polpo", "Thinly sliced octopus, octopus mayo, green olives", "13.95", "7, 8"),
            S("Impepata di cozze", "Mussels sautéed in extra virgin olive oil, cracked black pepper white "
              "wine and garlic", "11.95", "8,14"),
            S("Capesante alla St Jacques", "Fresh Jersey scallops, prawns and mushrooms in a white wine sauce "
              "Served in a shell edged with mashed potatoes then gratinated", "13.75", "7, 8"),
            D("Ostriche Chilled local Grouville oysters with red wine and shallot vinegar x 6 £15.00 x 12 £30.00 (8)",
              "Ostriche", "Chilled local Grouville oysters with red wine and shallot vinegar (x 6 £15.00 / x 12 £30.00)"),
        ]),
        ((0, 590, 475, 778), None, [
            H("Contorni-Side Orders", "Contorni-Side Orders"),
            S("Basket of bread and butter", "", "3.50", "2,7"),
            S("Tomatoes, onions and fresh basil salad", "", "3.50", None),
            S("Rocket, cherry tomatoes and parmesan shaving salad", "", "3.95", "7"),
            S("Mixed salad", "", "3.50", None),
            S("Spinach sautéed with garlic and butter", "", "3.95", "7"),
        ]),
        ((0, 778, 240, 810), "Contorni-Side Orders", [S("Chips", "", "3.50", "2")]),
        ((240, 778, 475, 810), "Contorni-Side Orders", [S("Onion rings", "", "3.50", "2")]),
        ((0, 810, 475, 921), None, []),
        ((475, 0, 930, 921), None, [
            H("Le Paste E Risotti-Pasta & Risotto", "Le Paste E Risotti-Pasta & Risotto"),
            S("Sartu’ di riso", "Baked rice seasoned with beef ragù, peas, pancetta, mushrooms, mozzarella.",
              "21.50", "2"),
            S("Ravioli ripieni alla crema di funghi", "BHome made ravioli, mushroom cream sauce.", "18.50", "2,4,7,14"),
            S("Tagliatelle alla Bolognese", "Beef ragù sauce.", "17.95", "1, 2, 4"),
            S("Linguine al granchio", "Freshly picked crab meat, cherry tomato sauce, white wine and extra "
              "virgin olive oil.", "22.95", "2, 3, 14"),
            S("Spaghetti alla Nerano (V)", "Courgette, parmesan cheese, fresh mint and basil.", "17.95", "12, 7"),
            S("Scialatielli ai frutti di Mare", "Scialatielli is fresh pasta made from semolina flour, water, "
              "pecorino cheese and basil, shellfish, cherry tomatoes.", "22.95", "2, 4, 7, 8,"),
            S("Spaghetti polpo alla Luciana", "Spaghetti pasta, local octopus, black olives in rich tomato "
              "sauce.", "22.95", "2, 8, 14"),
            S("Rigatoni pasta al ragù Napoletano", "Rigatoni pasta with Neapolitan ragù: stewed meats in a "
              "rich tomato sauce.", "17.95", "2"),
            H("I Pesci-Fishes", "I Pesci-Fishes"),
            S("Filetto di spigola alla mugnaia", "Pan fried fillet of sea bass, seasonal vegetables, "
              "Citronette sauce", "26.95", "2, 5"),
            S("Spiedino di pesce", "Scallops, king prawns, squid, white fish grilled on skewer, grilled "
              "vegetables, pinzimonio sauce.", "22.95", "1, 3, 5, 8"),
            S("Polpo e seppia in umido", "Stewed octopus and cuttlefish served on toasted sourdough bread.",
              "21.95", "2, 5, 8"),
            D("Pescato del giorno (min 1Kg serves 2) Catch of the day cooked to your choice: salt crust or "
              "grilled served with seasonal vegetables. from £29.50pp (1, 5)",
              "Pescato del giorno (min 1Kg serves 2)", "Catch of the day cooked to your choice: salt crust or "
              "grilled served with seasonal vegetables. (from £29.50 per person)"),
            H("Please ask for gluten free options"),
        ]),
        ((930, 0, 1403, 921), None, [
            H("Le Carni-Meats", "Le Carni-Meats"),
            S("Pollo alla Cacciatora", "Half chicken stew/casserole done in the traditional Tuscan style "
              "served with roasted potatoes", "20.95", "1"),
            S("Cotoletta alla Milanese rucola e pomodorini (veal)", "served with cherry tomatoes and rocket.",
              "28.25", "2,4"),
            D("Add: Spaghetti arrabbiata or with tomato sauce £3.50", why="add-on, no allergen codes"),
            S("Porchetta con patate al forno", "Pork belly, roast potatoes, seasonal vegetables", "22.95", "2, 14"),
            S("Tagliata di manzo (220 gr)", "Sliced Sirloin steak on bed of rocket salad, cherry tomatoes, "
              "shaved parmesan and French fries", "27.95", "2, 7"),
            I("Choice of sauces", "3.00", "7", "Black pepper or garlic butter."),
            H("Dolci E Formaggio-Desserts & Cheeses", "Dolci E Formaggio-Desserts & Cheeses"),
            I("Tiramisu della casa", "7.95", "2, 4, 7", "Ladyfingers dipped in coffee and liquor, layered with a "
              "whipped cream made of eggs, sugar and mascarpone cheese, finished with a sprinkle of cocoa powder."),
            I("Pannacotta al limone", "7.95", "2, 4, 7", "Lemon pannacotta, red berries compote."),
            I("Semifreddo al torroncino", "8.50", "2, 4, 7", "Cold, creamy semifreddo with crunchy torrone, "
              "finished with salted caramel"),
            I("Torta Caprese", "7.95", "2, 4, 7, 10", "Famous dessert from the Island of Capri: Flourless "
              "chocolate and almond cake, scoop vanilla ice cream"),
            I("Mille foglie", "7.95", "2, 4, 7", "Crisp layers of puff pastry, cream pâtissier, wild cherry"),
            I("Affogato", "6.50", "2, 7", "A shot of espresso, scoop of vanilla ice cream, whipped cream and "
              "chocolate topping"),
            I("Italian Ice Cream x 3 scoops", "7.50", "2, 7", "Triple chocolate, vanilla, coffee, strawberry and "
              "pistacchio."),
            I("Sorbet x 3 scoops", "6.95", "2", "Lemon, blood orange and black currant."),
            I("A selection of Italian cheeses and biscuits", "14.95", "1, 2, 7, 10, 14", "Selection of Italian "
              "cheeses, truffle, Italian honey and marmalade."),
            H(CONCERNED + "."),
            KEY_BAND,
            H("All prices are fully inclusive of GST at 5%"),
        ]),
    ],
    2: [
        ((0, 0, 475, 921), None, [
            H("Le Pizze", "Le Pizze"),
            I("Garlic bread with cheese (V)", "4.95", "2, 7"),
            I("Garlic bread with tomato (V)", "5.25", "2, 7"),
            I("Garlic bread with cheese and tomato (V)", "5.95", "2, 7"),
            S("Margherita (V) (Vegan Cheese available)", "Tomato, mozzarella, parmesan cheese and fresh basil.",
              "11.95", "2, 7"),
            S("Napoletana (V)", "Tomato, black olives, oregano and garlic.", "10.95", "2"),
            S("Diavola (spicy)", "Tomato, mozzarella, spicy ‘Nduja salami and chilli pepper flakes.", "13.95", "2, 7"),
            S("Prosciutto cotto & funghi", "Tomato, mozzarella, ham and mushrooms.", "13.95", "2, 7"),
            S("Prosciutto Crudo, rucola and parmiggiano", "Tomato, Parma ham, rocket and parmesan shavings",
              "14.95", "2, 7"),
            S("Contadina (V) (Vegan)", "Mozzarella, mushrooms, peppers, olives and capers.", "12.95", "2, 7"),
            S("Salsiccia & Friarielli", "Mozzarella, Italian pork sausage, wild broccoli and extra virgin olive oil",
              "13.50", "2, 7"),
            S("Pepperoni", "Mozzarella, spicy pepperoni and tomato sauce.", "13.95", "2, 7"),
            S("Tonno, cipolle e capperi", "Mozzarella, tuna, onions and capers.", "13.95", "2, 5, 7"),
            S("Calzone", "Folded pizza with ricotta cheese, parmesan, ham, salami Napoli and tomatoes", "17.95", "2, 7"),
            D("For gluten free base extra £3.50", why="gluten-free base option, no allergen codes"),
            D("Extra topping £2.50", why="extra toppings, no allergen codes"),
            H(KEY_TEXT + " (V) = Vegetarian (VG)= Vegan All prices are fully inclusive of GST at 5%"),
            H(CONCERNED),
        ]),
        ((475, 0, 930, 921), None, [
            H("RESTAURANT & PIZZE RIA Le Boulevard, St. Aubin, Jersey, C.I. JE3 8AB Tel: 01534 741049 | "
              "Email: info@sorrento.je Facebook: facebook.com/sorrento.je | Instagram: @sorrento.jsy www.sorrento.je"),
        ]),
        ((930, 0, 1403, 921), None, [H("R E S T A U R A N T & P I Z Z E R I A Menu")]),
    ],
}


def read_key():
    body = KEY_TEXT.removeprefix("Allergens: ").rstrip(",")
    key = {}
    for part in body.split(", "):
        number, name = part.split(" – ", 1)
        if name not in KEY_NAMES:
            fail(f"key entry {part!r} isn't in KEY_NAMES")
        key[int(number)] = KEY_NAMES[name]
    if sorted(key) != list(range(1, 15)) or sorted(key.values()) != sorted(ALLERGENS):
        fail("the key doesn't give each of the 14 allergens one number")
    return key


def region_text(words, box, tolerance=3.5):
    x0, top, x1, bottom = box
    inside = [w for w in words if x0 <= w["cx"] < x1 and top <= w["cy"] < bottom]
    inside.sort(key=lambda w: (w["cy"], w["x0"]))
    lines = []
    for w in inside:
        if lines and abs(lines[-1][0] - w["cy"]) <= tolerance:
            lines[-1][1].append(w)
        else:
            lines.append([w["cy"], [w]])
    return norm(" ".join(" ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"])) for _, ws in lines)), inside


def first_difference(a, b):
    i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return f"PDF: …{a[max(0, i - 60):i + 60]!r}\n  transcribed: …{b[max(0, i - 60):i + 60]!r}"


def read(path, key):
    rows, left_out = [], []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != len(PAGES):
            fail(f"expected {len(PAGES)} pages, found {len(pdf.pages)}")
        for page in pdf.pages:
            n = page.page_number
            words = page.extract_words(extra_attrs=["size"])  # a change of size starts a new word
            for w in words:
                w["cx"], w["cy"] = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
            claimed = set()
            for box, category, items in PAGES[n]:
                text, inside = region_text(words, box)
                if claimed & {id(w) for w in inside}:
                    fail(f"page {n}: region {box} overlaps another")
                claimed |= {id(w) for w in inside}
                expected = norm(" ".join(item["printed"] for item in items))
                if text != expected:
                    fail(f"page {n} region {box} doesn't match the transcription:\n  {first_difference(text, expected)}")
                for item in items:
                    if item["kind"] == "text":
                        category = item["category"] or category
                        continue
                    groups = CODE_GROUP.findall(item["printed"])
                    if item["why"]:
                        if groups:
                            fail(f"page {n}: {item['printed'][:40]!r} is left out but prints codes {groups}")
                        left_out.append((n, category, item["printed"], item["why"]))
                        continue
                    if len(groups) != 1:
                        fail(f"page {n}: {item['dish']!r} prints {len(groups)} code groups")
                    if item["price"] and f"£{item['price']}" not in item["printed"]:
                        fail(f"page {n}: {item['dish']!r} price {item['price']} isn't printed with it")
                    if not item["printed"].startswith(item["dish"]):
                        fail(f"page {n}: {item['dish']!r} isn't the start of its printed text")
                    found = set()
                    for number in re.split(r"\s*,\s*", groups[0]):
                        if int(number) not in key:
                            fail(f"page {n}: {item['dish']!r} code {number} isn't in the key")
                        found.add(key[int(number)])
                    rows.append({"page": n, "category": category, "dish": item["dish"], "description": item["desc"],
                                 "price": item["price"], "codes": groups[0], "allergens": found})
            stray = [w["text"] for w in words if id(w) not in claimed]
            if stray:
                fail(f"page {n}: words outside every region: {stray}")
            # The regions were checked word for word above, so this says the page prints the key.
            if not any(KEY_TEXT in item["printed"] for _, _, items in PAGES[n] for item in items):
                fail(f"page {n}: the transcription has no key")
    return rows, left_out


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default=os.path.join(root, "Imports", "charts-on-hold", "sorrento.csv"))
    parser.add_argument("--any-version", action="store_true",
                        help="read a PDF other than the one this script was checked against")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EXPECTED_SHA256 and not args.any_version:
        fail(f"{args.pdf} isn't the Summer 2026 menu this script was checked against (SHA-256 {digest}). "
             "Check the new menu by eye, update PAGES, then run with --any-version.")

    rows, left_out = read(args.pdf, read_key())
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
        print(f"  {r['dish']} £{r['price'] or '-'} ({r['codes']}): {', '.join(a for a in ALLERGENS if a in r['allergens'])}")
    print(f"\n{len(rows)} rows written to {args.out}")
    print("\nLeft out:")
    for n, category, printed, why in left_out:
        print(f"  p{n} [{category}] {printed} → {why}")


if __name__ == "__main__":
    main()
