#!/usr/bin/env python3
"""Hotel de France, La Terrasse (St Saviour's Road, St Saviour): read the allergens written
under each dish in its menu PDFs into Imports/charts-on-hold/hotel-de-france.csv.

Sources: PDFs linked from https://www.defrance.co.uk/la-terrasse (and the Sunday lunch PDF
from https://www.defrance.co.uk/la-terrasse/sunday-lunch), all under
https://www.defrance.co.uk/s/ and pinned by SHA-256 in MENUS below.

Main menus, read in full (in this order):
  Dinner-menu-Autumn-26.pdf        "La Terrasse dinner menu" (pages 2-6; pages 7-8 are its
                                   2/3-course set menu, read as a secondary menu)
  Day-menu-Autumn-26.pdf           day menu, Ayurvedic menu, sandwiches, sides, desserts
  Brunch-menu-2026.pdf             "La Terrasse Brunch menu"
  Kids-Menu-Autumn-2026.pdf        "La Terrasse kids menu"
  Sunday-lunch-menu-111026.pdf     "La Terrasse Sunday lunch menu" (11 Oct 2026)
  Afternoon-Tea-Autumn-26.pdf      "La Terrasse Afternoon Tea"
Secondary menus: a dish is kept only if it's on no main menu ("only there"):
  the dinner set menu, Delicious-set-Menu-2026.pdf, staycation-menu-Autumn-2026.pdf,
  Spa-menu-Opening-26.pdf, Christmas-menu-26.pdf, Room-service-day-menu-Autumn-2026.pdf,
  Night-Room-service-Autumn-26.pdf (food only; its beverage pages carry no allergens).
Not read: breakfast.pdf (made July 2024, modified Dec 2024: out of date), the drinks list,
the events buffet menu and the room specials sheet.

Format: a dish is a name line (usually with a price on the right), description lines, then
one line of allergens written out in words, e.g. "Milk, wheat, soya". The script finds
that line by its words: every word must be an allergen it knows (VOCAB), so a line it
can't read stops it rather than being taken for a description.
  wheat, barley, rye, oat(s) -> Gluten    milk, dairy -> Milk    soya, soy -> Soybeans
  sulphite(s) -> Sulphur Dioxide          egg(s) -> Eggs         mollusc(s), crustaceans
  any named nut (walnut, almond, pecan, pistachio, chestnut, pine nuts, "nuts") -> Nuts
  "(may contain nuts)" -> Nuts M          "(GF, DF, NF)", "(GF)" ... are diet labels, ignored
A starred allergen ("eggs*", with "bearnaise*" or "Add fried egg*" in the dish) is only in
that option; it's written as Y (contains), and listed.

Lines ending a block: the allergen line, a section heading, or a separator ("***", "_").
Within a block: the first line is the dish name; "Add ..." lines with a price are add-ons
(left out, they have no allergen line of their own); two or more other priced lines are
options, one row each ("Hot Baguette - Back bacon"); other lines are the description.
A block with no allergen line is left out and listed: no allergens written can't be told
apart from "not listed". Names are as printed, with their "(V)" and kcal labels. Prices
are the dish's own; the afternoon tea scones take "Scones (2) £5" from its price list.

Duplicates: dishes are matched by name (lower case, accents, "(V)" labels, supplements and
kcal dropped, ALIASES applied). A dish on several menus with the same allergens is kept
once, under the first main menu it's on. A dish on two main menus with different
allergens is kept on both, and listed. A secondary-menu dish that's also on a main menu is
left out; if its allergens differ, that's listed too.

category: the menu's name and its own section heading, e.g. "Dinner - Small plates".

Usage:
  python3 Tools/importers/venues/hotel-de-france.py <dir with the PDFs>
      [--out Imports/charts-on-hold/hotel-de-france.csv] [--any-version]
Needs pdfplumber.
"""
import argparse
import csv
import hashlib
import os
import re
import sys
import unicodedata

import pdfplumber

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

VOCAB = {
    "milk": "Milk", "dairy": "Milk",
    "wheat": "Gluten", "barley": "Gluten", "rye": "Gluten", "oat": "Gluten", "oats": "Gluten",
    "gluten": "Gluten",
    "soya": "Soybeans", "soy": "Soybeans",
    "sulphites": "Sulphur Dioxide", "sulphite": "Sulphur Dioxide",
    "egg": "Eggs", "eggs": "Eggs",
    "fish": "Fish",
    "celery": "Celery",
    "mustard": "Mustard",
    "crustaceans": "Crustaceans", "crustacean": "Crustaceans",
    "molluscs": "Molluscs", "mollusc": "Molluscs",
    "sesame": "Sesame", "sesame seeds": "Sesame",
    "peanuts": "Peanuts", "peanut": "Peanuts",
    "lupin": "Lupin",
    "nuts": "Nuts", "walnut": "Nuts", "walnuts": "Nuts", "almond": "Nuts", "almonds": "Nuts",
    "pecan": "Nuts", "pecans": "Nuts", "pistachio": "Nuts", "pistachios": "Nuts",
    "hazelnut": "Nuts", "hazelnuts": "Nuts", "cashew": "Nuts", "cashews": "Nuts",
    "chestnut": "Nuts", "chesnut": "Nuts", "pine nuts": "Nuts", "pine-nuts": "Nuts",
}
# Named on the menus as allergens, but not one of the 14 regulated tree nuts: mapped to Nuts
# anyway (the restaurant names them), and listed.
NOT_REGULATED_NUTS = {"chestnut", "chesnut", "pine nuts", "pine-nuts"}
DIET_LABELS = {"gf", "df", "nf", "v", "vg"}

TITLE_LINES = [  # anywhere on a page: titles, opening hours, notes, footers
    r"La Terrasse (dinner|day|Ayurvedic|Brunch|kids|Sunday lunch|room service|night room service) menu",
    r"La Terrasse Afternoon Tea", r"La Terrasse Delicious set menu", r"La Terrasse Staycation menu-2 courses",
    r"LA TERRASSE CHRISTMAS MENU", r"Ayurvedic spa menu",
    r"\d\d[.:]\d\d ?- ?\d\d[.:]\d\d( last order)?", r"\d\d\.\d\d – 12\.00 Hrs\.", r"12:00 – 21:00",
    r"Available from .*", r"Please call 4176 to place your order",
    r"All food is prepared in a kitchen containing common food allergens\..*",
    r"ALL FOOD IS PREPARED IN A KITCHEN CONTAINING COMMON FOOD ALLERGENS\.",
    r"If you have a food allergy, please advise our service team\.",
    r"IF YOU HAVE A FOOD ALLERGY, PLEASE ADVISE OUR SERVICE TEAM\.",
    r"A discretionary 10% service charge .*", r"PRICE IN GBP .*", r"A DISCRETATIONARY SERVICE CHARGE .*",
    r"(inclusive )?of the current goods & services tax\..*", r"again\.",
    r"We look forward to welcoming you again\.", r"Scan the QR code .*", r"and exclusive offerings\.",
    r"£5\.00 per tray charge .*",
]
SEPARATORS = {"***", "_", "`"}

MAIN, SECONDARY = "main", "secondary"
MENUS = [
    {"file": "Dinner-menu-Autumn-26.pdf", "role": MAIN, "pages": [2, 3, 4, 5, 6],
     "sha256": "a0db225ca668b65882605692c3558d773f988b3d65002b05d02f0d0071c7b65a",
     "headings": {"Bread": "Dinner - Bread", "Small plates": "Dinner - Small plates", "Salads": "Dinner - Salads",
                  "Sides": "Dinner - Sides", "Grill": "Dinner - Grill", "To share": "Dinner - To share",
                  "Something simpler": "Dinner - Something simpler", "Desserts": "Dinner - Desserts"},
     "notes": []},
    {"file": "Day-menu-Autumn-26.pdf", "role": MAIN, "pages": [2, 3, 4, 5, 6],
     "sha256": "be26c07bd2e154582c185a9d018e91d5f48fc51fb81daecf6084e93e5cf4a3c6",
     "headings": {"SMALL & LARGE PLATES": "Day menu - Small & large plates",
                  "Balanced, nourishing and crafted for wellbeing, all dishes vegetarian & vegan on request": "Ayurvedic menu",
                  "Sandwiches": "Day menu - Sandwiches", "Side orders": "Day menu - Side orders",
                  "Desserts": "Day menu - Desserts"},
     "notes": ["All served on white, brown or gluten free bread &", "olive oil dressed leaves"]},
    {"file": "Brunch-menu-2026.pdf", "role": MAIN, "pages": [1, 2], "start": "Brunch menu",
     "sha256": "67a7b976de0c42336c91e1d7151f859dba725a7b4d1cba33dd4ffc3009ce3a4a",
     "headings": {}, "notes": []},
    {"file": "Kids-Menu-Autumn-2026.pdf", "role": MAIN, "pages": [1, 2],
     "sha256": "0fbad5f8945567e5c4aed4189a651fb424d272a2537435fe03cdc06c974a91d5",
     "headings": {"Starter": "Kids menu - Starter", "Mains": "Kids menu - Mains",
                  "Side dishes": "Kids menu - Side dishes", "Desserts": "Kids menu - Desserts"},
     "notes": []},
    {"file": "Sunday-lunch-menu-111026.pdf", "role": MAIN, "pages": [1, 2], "start": "Sunday lunch menu",
     "sha256": "51a06915d2a002f4254bb54d64cfc3ef52964110afe619a2323f41897cfec7cf",
     "headings": {}, "notes": []},
    {"file": "Afternoon-Tea-Autumn-26.pdf", "role": MAIN, "pages": [1, 2], "start": "Afternoon tea",
     "sha256": "d4eeb17ad51cd3c379a816dd7048d430b89c8887192ae9c769031946a4fe94f6",
     "headings": {"Patisseries": "Afternoon tea - Patisseries", "Sandwiches": "Afternoon tea - Sandwiches"},
     "dish_headings": {"Scones": "Afternoon tea - Scones"},  # a heading that is also the dish's name
     "prices": {"Scones": "5"},  # from the price list at the top: "Scones (2) £5"
     "notes": []},
    # Secondary menus.
    {"file": "Dinner-menu-Autumn-26.pdf", "role": SECONDARY, "pages": [7, 8], "label": "dinner set menu",
     "sha256": "a0db225ca668b65882605692c3558d773f988b3d65002b05d02f0d0071c7b65a",
     "headings": {"Starters": "Dinner set menu - Starters", "Main courses": "Dinner set menu - Main courses",
                  "Desserts": "Dinner set menu - Desserts"},
     "notes": ["2 course £36.00, 3course £42.00", "£4.00 supplement"]},
    {"file": "Delicious-set-Menu-2026.pdf", "role": SECONDARY, "pages": [1, 2], "start": "Delicious set menu",
     "sha256": "6399f7c82cc1f4c72a58473269c83f49a32500461181cd8efd9a1e472f860ec9",
     "headings": {}, "notes": []},
    {"file": "staycation-menu-Autumn-2026.pdf", "role": SECONDARY, "pages": [1, 2], "start": "Staycation menu",
     "sha256": "17edcd19c0620f30b664106f61e25b66063ba8fe0e1325e1da614b894ddf156d",
     "headings": {}, "notes": []},
    {"file": "Spa-menu-Opening-26.pdf", "role": SECONDARY, "pages": [1, 2],
     "sha256": "50ceb303f196dd9b73a692db98e49c0c091e076dc8767421940c00c4d9c25c4f",
     "headings": {"TO START": "Ayurvedic spa menu - To start", "MAINS": "Ayurvedic spa menu - Mains"},
     "notes": ["Balanced, nourishing and crafted for wellbeing"]},
    {"file": "Christmas-menu-26.pdf", "role": SECONDARY, "pages": [1, 2],
     "sha256": "30aa142a3bb5f14c6f1c0a980cf6ea4215e59ad5bca240acafbe23c1bf725879",
     "headings": {"TO START": "Christmas menu - To start", "FOR MAINS": "Christmas menu - For mains",
                  "FOR PUDDING": "Christmas menu - For pudding", "TO FINISH": "Christmas menu - To finish"},
     "notes": ["£48.00 PER PERSON", "LIMITED PLACES, BOOKING ESSENTIAL",
               "AVAILABLE FOR 10 GUESTS OR MORE; PRE - ORDER REQUIRED", "28TH NOVEMBER-19TH DECEMBER 2026"]},
    {"file": "Room-service-day-menu-Autumn-2026.pdf", "role": SECONDARY, "pages": [1, 2, 3, 4, 5],
     "sha256": "8dd780cc0333e6ed1ec9b33394960b1e08d5183a6e8ce10791339de798044c77",
     "headings": {"To Share": "Room service - To share", "To start": "Room service - To start",
                  "Sandwiches": "Room service - Sandwiches", "Salad": "Room service - Salad",
                  "Main courses": "Room service - Main courses", "Side dishes": "Room service - Side dishes",
                  "Desserts": "Room service - Desserts"},
     "notes": ["All served on white, brown or gluten free bread & olive oil dressed leaves"]},
    {"file": "Night-Room-service-Autumn-26.pdf", "role": SECONDARY, "pages": [1, 2, 3, 4], "stop": "Beverage menu",
     "sha256": "7a53e417cf90de48281fb894224d7bd26cbbb0081ae983a1e83028e64ebebb26",
     "headings": {"Sandwiches": "Night room service - Sandwiches", "Main courses": "Night room service - Main courses",
                  "Dessert": "Night room service - Dessert"},
     "notes": ["Your choice of brown or white bread", "Gluten free bread available on request"]},
]

# Names that mean the same dish on different menus (normalised name -> the name it matches).
# Only used to find duplicates; each row keeps the name its own menu prints.
ALIASES = {
    "skin on fries parmigiano": "skin on fries parmigiano",
    "skin on fries parmesan truffle oil": "skin on fries parmigiano",
    "skin on fries truffle oil parmigiano": "skin on fries parmigiano",
    "roasted tenderstem broccoli": "roasted tender stem broccoli",
    "movenpick ice creams per scoop": "movenpick ice creams per scoop",
    "movenpick ice creams": "movenpick ice creams per scoop",
    "movenpick ice cream 2 scoops": "movenpick ice creams per scoop",
    "selection of cheese": "selection of cheese",
    "selection of artisan cheese": "selection of cheese",
    "cheese plate": "cheese plate",
    "roast rump of lamb": "roasted rump of lamb",
    "grilled catch of the day": "grilled catch of the day",
    "spatchcock spring chicken": "spatchcock spring chicken",
    "fish chips": "fish and chips",
    "seasonal garden veloute cappuccino foam": "seasonal garden veloute cappuccino foam",
    "jersey oysters x 6": "jersey oysters x 6",
}

PRICE = re.compile(r"£(\d+(?:\.\d\d)?)")


def fail(message):
    sys.exit(f"hotel-de-france.py: STOPPED: {message}")


def norm_name(name):
    text = re.sub(r"\(£[\d.]+ supplement\)", " ", name, flags=re.I)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\d+ kcal", " ", text)
    text = re.sub(r"\((v|vg|gf|df|nf)\)", " ", text)
    text = re.sub(r"\(per scoop\)", "per scoop", text)
    text = " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())
    return ALIASES.get(text, text)


def read_allergens(text):
    """Parse an allergen line. Returns (labels, notes) or None if it isn't one."""
    labels, notes = {}, []
    rest = text
    for inner in re.findall(r"\(([^)]*)\)", text):
        words = [w.strip().lower() for w in inner.split(",") if w.strip()]
        m = re.fullmatch(r"\s*may contain (.+?)\s*", inner, re.I)
        if m:
            allergen = VOCAB.get(m.group(1).lower())
            if not allergen:
                return None
            labels.setdefault(allergen, "M")
            notes.append(f"may contain {m.group(1)}")
        elif words and all(w in DIET_LABELS for w in words):
            notes.append(f"diet labels ({inner.strip()})")
        else:
            return None
        rest = rest.replace(f"({inner})", ",")
    found = False
    for token in re.split(r"[,.]", rest):
        token = " ".join(token.lower().split())
        if not token:
            continue
        parts = [token] if (token.rstrip("*") in VOCAB) else re.split(r"(?<=\*)|\s+", token)
        parts = [p for p in parts if p]
        for part in parts:
            star = part.endswith("*")
            word = part.rstrip("*")
            if word not in VOCAB:
                return None
            labels[VOCAB[word]] = "Y"  # a "contains" mention beats "may contain"
            found = True
            if star:
                notes.append(f"starred: {part}")
            if word in NOT_REGULATED_NUTS:
                notes.append(f"'{word}' mapped to Nuts")
    if not found and not notes:
        return None
    return labels, notes


def page_lines(page):
    words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=1.5)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 3.5:  # "per scoop" sits 3pt low
            lines[-1].append(w)
        else:
            lines.append([w])
    out = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        text = " ".join(" ".join(w["text"] for w in line).split()).replace("(cid:976)", "f")
        # A price sits at the right-hand edge, apart from the text.
        price = ""
        right = [w for w in line if w["x0"] > 380]
        left = [w for w in line if w["x0"] <= 380]
        if right and left:
            m = PRICE.fullmatch("".join(w["text"] for w in right))  # "£ 6 . 00"
            if m:
                price = m.group(1)
                text = " ".join(" ".join(w["text"] for w in left).split())
        size = min(w["size"] for w in line)
        out.append({"text": text, "price": price, "size": size, "top": line[0]["top"],
                    "font": line[0]["fontname"].split("+")[-1]})
    return out


def read_menu(path, menu):
    """Blocks of lines, each ending at its allergen line (or not, if it has none)."""
    titles = [re.compile(p) for p in TITLE_LINES]
    dishes, unlisted, add_ons, notes = [], [], [], []
    category = menu.get("start")
    pending = []

    def close(allergens=None, where=None):
        nonlocal pending
        if not pending:
            if allergens is not None:
                fail(f"{where}: allergen line with no dish above it")
            return
        name_line, rest = pending[0], pending[1:]
        if allergens is None:
            # No allergen line: list what's there (a dish, or a price list) and write nothing.
            for l in pending:
                if l is name_line or l["price"]:
                    unlisted.append({"menu": menu, "page": l["page"], "category": category,
                                     "dish": l["text"], "price": l["price"]})
            pending = []
            return
        options =[l for l in rest if l["price"] and not l["text"].startswith("Add ")]
        adds = [l for l in rest if l["price"] and l["text"].startswith("Add ")]
        desc = [l for l in rest if not l["price"]]
        price = name_line["price"]
        base = name_line["text"].rstrip(",")
        if len(options) == 1 and not price:
            price = options[0]["price"]  # the price printed on the description line
            desc = [l for l in rest if not l["text"].startswith("Add ")]
            options = []
        elif options and price:
            fail(f"{where or menu['file']}: {base!r} has its own price and priced lines {[o['text'] for o in options]}")
        description = " ".join(l["text"] for l in desc)
        stem = re.sub(r" *\(choose from the following\):?$", "", base)
        rows = [(f"{stem} - {o['text']}", o["price"]) for o in options] or [(base, price)]
        for name, p in rows:
            p = p or menu.get("prices", {}).get(name, "")
            dish = {"menu": menu, "page": name_line["page"], "category": category, "dish": name,
                    "description": description, "price": p}
            if allergens is None:
                unlisted.append(dish)
            else:
                dish["labels"], dish["notes"], dish["printed"] = allergens
                dishes.append(dish)
        for a in adds:
            add_ons.append({"menu": menu, "page": a["page"], "category": category, "dish": a["text"],
                            "price": a["price"], "under": base})
        pending = []

    with pdfplumber.open(path) as pdf:
        stopped = False
        for n in menu["pages"]:
            page = pdf.pages[n - 1]
            for line in page_lines(page):
                text = line["text"]
                where = f"{menu['file']} p{n} {text!r}"
                line["page"] = n
                if menu.get("stop") and text == menu["stop"]:
                    stopped = True
                    break
                if any(t.fullmatch(text) for t in titles) and not line["price"]:
                    continue
                if text in SEPARATORS:
                    close(where=where)
                    continue
                if text in menu["notes"]:
                    notes.append(f"p{n}: {text}")
                    continue
                if text in menu["headings"] and not line["price"]:
                    close(where=where)
                    category = menu["headings"][text]
                    continue
                if text in menu.get("dish_headings", {}) and not line["price"]:
                    close(where=where)
                    category = menu["dish_headings"][text]
                    pending = [line]
                    continue
                parsed = None if line["price"] else read_allergens(text)
                if parsed:
                    labels, line_notes = parsed
                    if line["size"] > 9:
                        line_notes = line_notes + [f"allergen line set in {line['size']:.0f}pt, like a description"]
                    close((labels, line_notes, text), where)
                    continue
                if line["size"] <= 8.5 and not line["price"]:
                    # Small print that isn't an allergen line: decide what it is before going on.
                    if not re.fullmatch(r"per scoop", text):
                        fail(f"{where}: small print that isn't an allergen line")
                if category is None:
                    fail(f"{where}: text before the first heading")
                pending.append(line)
            if stopped:
                break
        close()
    return dishes, unlisted, add_ons, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", help="directory holding the PDFs under their published file names")
    parser.add_argument("--out", default="Imports/charts-on-hold/hotel-de-france.csv")
    parser.add_argument("--any-version", action="store_true",
                        help="read PDFs other than the ones this script was checked against")
    args = parser.parse_args()

    checked = {}
    everything = []
    for menu in MENUS:
        path = os.path.join(args.sources, menu["file"])
        if path not in checked:
            with open(path, "rb") as f:
                checked[path] = hashlib.sha256(f.read()).hexdigest()
        if checked[path] != menu["sha256"] and not args.any_version:
            fail(f"{path} isn't the version this script was checked against (SHA-256 {checked[path]}). "
                 f"Check it by eye, then run with --any-version.")
        everything.append((menu, read_menu(path, menu)))

    kept, unlisted, add_ons, conflicts, duplicates, left_secondary = [], [], [], [], [], []
    by_name = {}  # normalised name -> rows kept with it
    for menu, (dishes, no_allergens, adds, notes) in everything:
        unlisted += no_allergens
        add_ons += adds
        for d in dishes:
            key = norm_name(d["dish"])
            same = by_name.get(key, [])
            match = [k for k in same if k["labels"] == d["labels"]]
            if menu["role"] == SECONDARY and any(k["menu"]["role"] == MAIN for k in same):
                if not match:
                    conflicts.append((d, list(same)))
                    left_secondary.append((d, "on a main menu with different allergens"))
                else:
                    duplicates.append((d, match[0]))
                continue
            if match:
                duplicates.append((d, match[0]))
                continue
            if same:
                conflicts.append((d, list(same)))
            by_name.setdefault(key, []).append(d)
            kept.append(d)

    seen = set()
    for d in kept:
        k = (d["category"], d["dish"])
        if k in seen:
            fail(f"'{d['dish']}' appears twice in '{d['category']}'")
        seen.add(k)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for d in kept:
            writer.writerow([d["category"], d["dish"], d["description"], d["price"]]
                            + [d["labels"].get(a, "") for a in ALLERGENS])

    def label(m):
        return m.get("label") or m["file"]

    category = None
    for d in kept:
        if d["category"] != category:
            category = d["category"]
            print(f"--- {category}")
        y = [a for a in ALLERGENS if d["labels"].get(a) == "Y"]
        m = [a for a in ALLERGENS if d["labels"].get(a) == "M"]
        extra = f"; may contain {', '.join(m)}" if m else ""
        price = f"  £{d['price']}" if d["price"] else ""
        notes = f"  [{'; '.join(d['notes'])}]" if d["notes"] else ""
        print(f"p{d['page']} {d['dish']}{price}\n      printed: {d['printed']}\n      -> {', '.join(y) or '-'}{extra}{notes}")
    print(f"\n{len(kept)} dishes written to {args.out}")

    print("\nLEFT OUT, no allergens written (can't be told apart from 'not listed'):")
    for d in unlisted:
        print(f"  {label(d['menu'])} p{d['page']} [{d['category']}] {d['dish']}" + (f"  £{d['price']}" if d["price"] else ""))
    print("\nLEFT OUT, add-ons with no allergen line of their own:")
    for a in add_ons:
        print(f"  {label(a['menu'])} p{a['page']} [{a['category']}] {a['dish']} £{a['price']} (under {a['under']!r})")
    print("\nSAME DISH, DIFFERENT ALLERGENS:")
    for d, others in conflicts:
        status = "left out (secondary menu)" if d["menu"]["role"] == SECONDARY else "kept on both"
        print(f"  {label(d['menu'])} [{d['category']}] {d['dish']}: {d['printed']}  -- {status}")
        for o in others:
            print(f"      vs {label(o['menu'])} [{o['category']}] {o['dish']}: {o['printed']}")
            for x, y in ((d, o), (o, d)):
                more = [a for a in ALLERGENS if x["labels"].get(a) and not y["labels"].get(a)]
                if more and (y["menu"]["role"] == MAIN):
                    print(f"      ! the {label(x['menu'])} one lists {', '.join(more)}, which the kept "
                          f"{label(y['menu'])} row [{y['category']}] doesn't")
    print("\nKept once (same dish, same allergens, on another menu):")
    for d, k in duplicates:
        print(f"  {label(d['menu'])} [{d['category']}] {d['dish']}  =  [{k['category']}] {k['dish']}")
    for menu, (_, _, _, notes) in everything:
        if notes:
            print(f"\nNotes printed in {label(menu)}:", *notes, sep="\n  ")


if __name__ == "__main__":
    main()
