#!/usr/bin/env python3
"""Sands (Discovery Bay, Grande Route des Mielles, St Ouen): rebuild a dish list from its
inverted allergen page into Imports/charts-on-hold/sands-discovery-bay.csv.

Source: https://www.sands-cafe.co.uk/allergenandappendix ("Allergens & Further Reading",
Squarespace; page content last updated 3 Sep 2025 per its data-updated-on stamp). Prices,
descriptions and categories come from the cafe's menu pages, https://www.sands-cafe.co.uk/menu
(updated 5 Jul 2026) and https://www.sands-cafe.co.uk/kids. Squarespace re-renders the
markup on each request, so the script pins the SHA-256 of what it extracts, not the files.

Format: the allergen page is INVERTED. It's a Squarespace menu block with one tab per
allergen; each tab lists the dishes containing it (title, and a note on which part), and
some tabs carry a note instead of dishes. In the page's flattened text the notes sit
before or after the wrong heading (e.g. "TRACE PRESENT" between Mustard and Celery), but
in the HTML each note is inside its own tab panel, so the order is resolved by the DOM:
  Nuts: BUTTERNUT TACO (ALMOND SALSA); HAZELNUT SYRUP
  Gluten: BANANA PANCAKES; ALL BREAD ITEMS; POACHED EGGS & AVOCADO; BREAKFAST; SMASH BURGER;
          SMASH BEAN BURGER; CHICKEN SANDSWICH; SANDS BURGER; SWEET POTATO; CHICKEN NUGGETS
  Eggs: POACHED EGGS & AVOCADO; BANANA PANCAKES; BREAKFAST / VEG BREAKFAST; SANDS BURGER;
        CHICKEN SANDSWICH
  Dairy: BANANA PANCAKES          Mustard: SANDS BURGER; CUBANO
  Celery: tab note "TRACE PRESENT", no dishes
  Lupin: BREAKFAST (Bloomer toast); "We use pea shoots on some of our dishes as a garnish"
  Sesame: item "TRACE PRESENT", no dishes
  Crustaceans, Molluscs, Fish: tab note "NOTHING ON OUR MENU CURRENTLY CONTAINS ..."
  Soybeans: SMASH BEAN BURGER (BEAN PATTIES)
  Sulphites: tab note "TRACE OF SULPHITES PRESENT", no dishes
  There is NO Peanuts tab: the page says nothing about peanuts.

Output:
  * one row per dish named under at least one allergen and on the current menu: Y for each
    allergen tab it's under. Gluten "BREAKFAST" is read as the full breakfast only (the Eggs
    tab names "BREAKFAST / VEG BREAKFAST" separately).
  * Celery, Sesame and Sulphur Dioxide: M ("may contain") on every row, from the three
    "TRACE PRESENT" notes, which name no dish (set TRACES = {} to drop this).
  * Peanuts and Lupin (apart from BREAKFAST's bloomer toast) are blank on every row: blank
    here means the page doesn't say, not that the dish is free of them.
Left out, and listed when the script runs:
  * VEG BREAKFAST: only under Eggs, and it's ambiguous whether "BREAKFAST" under Gluten and
    Lupin covers it (the menu says it comes with toast and a smash bean patty);
  * ALL BREAD ITEMS (a statement, not a dish), and the three note items;
  * BUTTERNUT TACO and CUBANO: on the allergen page but not on the current menu;
  * every menu dish named under no allergen: no allergens can't be told apart from "not
    listed".
category, description and price: the menu page's section, description and price.

Usage:
  python3 Tools/importers/venues/sands-discovery-bay.py allergenandappendix.html menu.html kids.html
      [--out Imports/charts-on-hold/sands-discovery-bay.csv] [--any-version]
"""
import argparse
import csv
import hashlib
import html.parser
import json
import re
import sys

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]

TABS = {  # the page's tabs, in order -> app allergen
    "Nuts": "Nuts", "Gluten": "Gluten", "Eggs": "Eggs", "Dairy": "Milk", "Mustard": "Mustard",
    "Celery": "Celery", "Lupin": "Lupin", "Sesame": "Sesame", "Crustaceans": "Crustaceans",
    "Molluscs": "Molluscs", "Fish": "Fish", "Soybeans": "Soybeans", "Sulphites": "Sulphur Dioxide",
}
# Notes, by tab: what they say, and how they're read.
NONE_NOTES = {"Crustaceans": "NOTHING ON OUR MENU CURRENTLY CONTAINS CRUSTACEANS",
              "Molluscs": "NOTHING ON OUR MENU CURRENTLY CONTAINS MOLLUSCS",
              "Fish": "NOTHING ON OUR MENU CURRENTLY CONTAINS FISH"}
TRACES = {"Celery": "TRACE PRESENT", "Sesame": "TRACE PRESENT", "Sulphites": "TRACE OF SULPHITES PRESENT"}
OTHER_NOTES = {("Lupin", "We use pea shoots on some of our dishes as a garnish")}
NOT_DISHES = {"ALL BREAD ITEMS"}
# Names on the allergen page -> the dishes they stand for.
SPLIT = {"BREAKFAST / VEG BREAKFAST": ["BREAKFAST", "VEG BREAKFAST"]}
AMBIGUOUS = {"VEG BREAKFAST": "named only under Eggs ('BREAKFAST / VEG BREAKFAST'); whether the Gluten and "
                              "Lupin tabs' 'BREAKFAST' covers it isn't said (the menu lists toast and a smash bean patty)"}
# Allergen-page names -> (menu page, section, item title) for price and description.
MENU_NAMES = {"HAZELNUT SYRUP": ("menu", "COFFEE & T", "SYRUPS")}

ALLERGEN_SHA256 = "5749ce6cc3e73b17e4d04ca6714281c40e70dd1a9640b2a1f81412c41a720206"
MENU_SHA256 = "fed438b315af8777424a707fa65fe5ef1e3aed12f51eace9a53e0c0277ce696c"


def fail(message):
    sys.exit(f"sands-discovery-bay.py: STOPPED: {message}")


class MenuBlocks(html.parser.HTMLParser):
    """Squarespace menu blocks: tabs (label, note) -> sections -> items (title, description, price)."""

    FIELDS = {"menu-description": ("tab", "note"), "menu-section-title": ("section", "title"),
              "menu-section-description": ("section", "description"), "menu-item-title": ("item", "title"),
              "menu-item-description": ("item", "description"), "menu-item-price-top": ("item", "price")}
    VOID = {"img", "br", "meta", "link", "input", "hr", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.tabs, self.field = 0, [], None
        # The menu pages head each menu block with a text block ("BRUNCH", "SANDSWICHES"):
        # the last line of the text block before a menu block is that block's heading.
        self.text_block, self.heading, self.block_heading = None, "", ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag not in self.VOID:
            self.depth += 1
        if "sqs-block-html" in classes:
            self.text_block = (self.depth, [])
        if self.text_block and tag in ("p", "h1", "h2", "h3", "h4", "br"):
            self.text_block[1].append("\n")
        if "sqs-block-menu" in classes:
            self.block_heading = self.heading
        if "js-menu" in classes:
            self.tabs.append({"tab": a.get("aria-label") or "", "note": "", "sections": [],
                              "heading": self.block_heading})
        elif "menu-section" in classes and self.tabs:
            self.tabs[-1]["sections"].append({"title": "", "description": "", "items": []})
        elif "menu-item" in classes and self.tabs:
            if not self.tabs[-1]["sections"]:
                self.tabs[-1]["sections"].append({"title": "", "description": "", "items": []})
            self.tabs[-1]["sections"][-1]["items"].append({"title": "", "description": "", "price": ""})
        for cls, (level, key) in self.FIELDS.items():
            if cls in classes and self.tabs:
                tab = self.tabs[-1]
                target = {"tab": tab, "section": tab["sections"][-1] if tab["sections"] else None,
                          "item": tab["sections"][-1]["items"][-1] if tab["sections"] and tab["sections"][-1]["items"] else None}[level]
                self.field = (key, target, self.depth, [])

    def handle_endtag(self, tag):
        if self.text_block and self.depth == self.text_block[0]:
            lines = [" ".join(l.split()) for l in "".join(self.text_block[1]).split("\n")]
            lines = [l for l in lines if l]
            self.heading = lines[-1] if lines else ""
            self.text_block = None
        if self.field and self.depth == self.field[2]:
            key, target, _, parts = self.field
            target[key] = " ".join("".join(parts).split())
            self.field = None
        self.depth -= 1

    def handle_data(self, data):
        if self.field:
            self.field[3].append(data)
        if self.text_block:
            self.text_block[1].append(data)


def blocks(path):
    p = MenuBlocks()
    with open(path, encoding="utf-8") as f:
        p.feed(f.read())
    return p.tabs


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("allergens", help="allergenandappendix page")
    parser.add_argument("menu", help="menu page")
    parser.add_argument("kids", help="kids page")
    parser.add_argument("--out", default="Imports/charts-on-hold/sands-discovery-bay.csv")
    parser.add_argument("--any-version", action="store_true",
                        help="read pages other than the ones this script was checked against")
    args = parser.parse_args()

    tabs = blocks(args.allergens)
    menus = {"menu": blocks(args.menu), "kids": blocks(args.kids)}
    found = {"allergens": digest(tabs), "menu": digest(menus)}
    if not args.any_version and (found["allergens"] != ALLERGEN_SHA256 or found["menu"] != MENU_SHA256):
        fail(f"the pages aren't the ones this script was checked against (allergens {found['allergens']}, "
             f"menus {found['menu']}). Check them by eye, then run with --any-version.")

    allergen_tabs = [t for t in tabs if t["tab"] in TABS]
    if [t["tab"] for t in allergen_tabs] != list(TABS):
        fail(f"allergen tabs are {[t['tab'] for t in allergen_tabs]}, expected {list(TABS)}")

    contains, notes = {}, []  # dish -> {allergen: (tab, note)}
    for t in allergen_tabs:
        name = t["tab"]
        if len(t["sections"]) != 1 or t["sections"][0]["title"] != name or t["sections"][0]["description"]:
            fail(f"tab {name}: expected one section titled {name!r}")
        items = t["sections"][0]["items"]
        note = t["note"]
        if note:
            expected = NONE_NOTES.get(name) or (TRACES.get(name) if TRACES.get(name) == note else None)
            if note != expected:
                fail(f"tab {name}: unexpected note {note!r}")
            notes.append(f"{name}: tab note {note!r}")
        if name in NONE_NOTES and items:
            fail(f"tab {name} says nothing contains it but lists {items}")
        for item in items:
            title, desc = item["title"], item["description"]
            if item["price"]:
                fail(f"tab {name}: unexpected price on {title!r}")
            if (name, title) in OTHER_NOTES or (TRACES.get(name) == title and not desc):
                notes.append(f"{name}: item {title!r}")
                continue
            for dish in SPLIT.get(title, [title]):
                contains.setdefault(dish, {})[TABS[name]] = desc
    traced = [TABS[t] for t in TRACES]

    # The current menu: section -> items, for prices, descriptions and categories.
    menu_items = {}
    for page, page_tabs in menus.items():
        for t in page_tabs:
            for s in t["sections"]:
                for item in s["items"]:
                    section = s["title"] or t["heading"]
                    if page == "kids":  # its one section title is a note: "All served with chips and lettuce"
                        section = t["heading"]
                        item = dict(item, description=item["description"] or s["title"])
                    menu_items.setdefault(item["title"], []).append((page, t["tab"], section, item))

    rows, left_out = [], []
    for dish, labels in contains.items():
        if dish in NOT_DISHES:
            left_out.append(f"{dish} (under {', '.join(labels)}): a statement, not a dish")
            continue
        if dish in AMBIGUOUS:
            left_out.append(f"{dish} (under {', '.join(labels)}): {AMBIGUOUS[dish]}")
            continue
        if dish in MENU_NAMES:
            page, section, title = MENU_NAMES[dish]
            matches = [m for m in menu_items.get(title, []) if m[0] == page and m[2] == section]
        else:
            matches = menu_items.get(dish, [])
            if len(matches) > 1:  # SWEET POTATO is on both: the allergen page's (brioche bun) is the main menu's
                matches = [m for m in matches if m[0] == "menu"]
        if not matches:
            left_out.append(f"{dish} (under {', '.join(labels)}): not on the current menu or kids menu")
            continue
        if len(matches) > 1:
            fail(f"{dish}: on the menu pages {len(matches)} times: {[m[:3] for m in matches]}")
        page, tab, section, item = matches[0]
        values = {a: "Y" for a in labels}
        for a in traced:
            values.setdefault(a, "M")
        price = re.sub(r"^(add |from )?£?", "", item["price"].strip(), flags=re.I)
        price = {"70p": "0.70"}.get(price, price)
        if not re.fullmatch(r"\d+(\.\d\d)?", price):
            fail(f"{dish}: can't read price {item['price']!r}")
        rows.append({"category": section, "dish": dish, "description": item["description"], "price": price,
                     "values": values, "notes": labels, "page": page})

    named = set(contains) | {t for d in SPLIT.values() for t in d}
    for page, page_tabs in menus.items():
        for t in page_tabs:
            if t["tab"].upper() in ("DRINKS",):
                continue
            for s in t["sections"]:
                section = s["title"] or t["heading"]
                if section in ("DRINKS", "COFFEE & T", "BEER", "CIDER") or section.startswith("WINE"):
                    continue
                for item in s["items"]:
                    if item["title"] not in named and item["title"]:
                        left_out.append(f"{page} [{section}] {item['title']} {item['price']}: under no allergen")

    order = {"BRUNCH": 0, "TACOS - FRESHLY MADE IN HOUSE": 1, "SANDSWICHES": 2, "KIDS MENU": 3, "COFFEE & T": 4}
    rows.sort(key=lambda r: order.get(r["category"], 9))
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "dish", "description", "price"] + ALLERGENS)
        for r in rows:
            writer.writerow([r["category"], r["dish"], r["description"], r["price"]]
                            + [r["values"].get(a, "") for a in ALLERGENS])

    for r in rows:
        y = [a for a in ALLERGENS if r["values"].get(a) == "Y"]
        m = [a for a in ALLERGENS if r["values"].get(a) == "M"]
        why = "; ".join(f"{a}: {n}" if n else a for a, n in r["notes"].items())
        print(f"[{r['category']}] {r['dish']}  £{r['price']}  ({r['page']}: {r['description']})\n"
              f"      contains {', '.join(y)}  [{why}]; may contain {', '.join(m)}")
    print(f"\n{len(rows)} dishes written to {args.out}")
    print("\nLEFT OUT:", *left_out, sep="\n  ")
    print("\nNotes on the allergen page:", *notes, sep="\n  ")
    print("  There is no Peanuts tab.")
    print(f"\nallergens {found['allergens']}\nmenus {found['menu']}")


if __name__ == "__main__":
    main()
