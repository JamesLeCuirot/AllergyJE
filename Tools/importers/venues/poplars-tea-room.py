#!/usr/bin/env python3
"""The Poplars Tea Room (The Poplars, La Moye, St Brelade): read the allergen codes on its
menu page into Imports/menus/poplars-tea-room.csv.

Source: https://www.thepoplarstearoom.com/menu (Squarespace), saved as HTML. The page has
no date; its banner says "Re-opening 18th March until 20th September 2026" (seasonal).
Squarespace re-renders the page's markup on every request, so the script pins the SHA-256
of the menu it extracts (MENU_SHA256), not of the file.

Format: a Squarespace menu block with two tabs, FOOD & BITES and DRINKS; each tab has
sections (title, optional description) of items (title, optional description, price).
Allergens are codes in brackets after the dish, e.g. "Egg Mayonnaise (2,4,7,9)". The key
is only a row of icon images, allergen-01-celery.png ... allergen-14-sulphur.png; each icon
also prints its number. Checked by file name and by eye (the script checks the names):
  1 Celery  2 Cereals  3 Crustaceans  4 Eggs  5 Fish  6 Lupin  7 Milk  8 Molluscs
  9 Mustard  10 Nuts*  11 Peanuts  12 Sesame  13 Soya  14 Sulphur
i.e. the standard UK order. Codes are "contains" (Y); the page prints no "may contain"
codes, but warns that all allergens are in the kitchen and in the display counter.

Read: the FOOD & BITES tab. Left out: the DRINKS tab (as for The Loft), and:
  * takeaway price lines ("Takeaway (all)", "Sausage Roll (Takeaway)" ...): prices, not
    dishes, and they print no codes;
  * items with no codes (Crisps, Takeaway soup, the jam / cream scones): no codes can't
    be told apart from "not listed";
  * choose-your-own items whose allergens depend on what's chosen and aren't printed for
    the dish as served: Toasted Sandwiches ("Choose any two fillings on sliced bread
    (2,7)" with per-filling codes), Additional fillings, and Soup & a Sandwich (1,2,7), which
    leave out the chosen sandwich's own codes.
All of these are listed when the script runs.

Section codes: a section description's codes apply to every dish in it for Ploughman's,
Sausage Roll & Cheese Scone Salads and Salads (they describe what every dish there comes
with), so those dishes get the union. The Ploughman's is one row: the section's codes plus
all four fillings' (any two of Brie, Cheddar, Pâté, Ham always include milk). The
Sandwiches description ends "Gluten free bread also available.(4)": the 4 (eggs) is the
gluten free bread's, so it isn't added to the sandwiches; the description of each sandwich
says "Gluten free bread also available (contains egg)" instead.

Names: the item title without its codes. Where a title repeats in a section the item's
description is added ("Homemade Soup & Baguette - Small"). "Per Scoop (2,4,7,13)" under
"Jersey Dairy Vanilla Ice Cream & Rossini Chocolate Curl" is that ice cream's price line.
category: the section title, as printed.

Usage:
  python3 Tools/importers/venues/poplars-tea-room.py poplars_menu.html
      [--out Imports/menus/poplars-tea-room.csv] [--any-version]
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

KEY = {1: "Celery", 2: "Gluten", 3: "Crustaceans", 4: "Eggs", 5: "Fish", 6: "Lupin", 7: "Milk",
       8: "Molluscs", 9: "Mustard", 10: "Nuts", 11: "Peanuts", 12: "Sesame", 13: "Soybeans",
       14: "Sulphur Dioxide"}
ICONS = ["01-celery", "02-cereals", "03-crustaceans", "04-eggs", "05-fish", "06-lupin", "07-milk",
         "08-molluscs", "09-mustard", "10-nuts", "11-peanuts", "12-sesame", "13-soya-v2", "14-sulphur"]

MENU_SHA256 = "d382e8ff61dc7be6f1e68c2b4da5d13bb9e50b2fff53dc88911158ec6d452b89"
TABS = ["FOOD & BITES", "DRINKS"]
SECTION_CODES_APPLY = {"Ploughman’s", "Sausage Roll & Cheese Scone Salads", "Salads"}
SANDWICH_NOTE = "Gluten free bread also available (contains egg)"
CHOOSE_YOUR_OWN = {  # (section, item title) -> why it's left out
    ("Sandwiches", "Additional fillings:"): "an extra filling; codes are per filling",
    ("Toasted Sandwiches", "Fillings - Choose any two for"): "build your own: (2,7) plus the two fillings chosen",
    ("Toasted Sandwiches", "Each Extra Filling"): "an extra filling",
    ("Soup", "Soup & a Sandwich (1,2,7)"): "codes leave out the chosen sandwich's own",
    ("Soup", "Sandwich Supplement"): "supplement for a crab sandwich with Soup & a Sandwich (left out)",
}
NOTES = {("Sausage Roll & Cheese Scone Salads", "Or why not mix one of each!")}
CODES = re.compile(r"\s*\((\d+(?:\s*,\s*\d+)*)\)")


def fail(message):
    sys.exit(f"poplars-tea-room.py: STOPPED: {message}")


class MenuParser(html.parser.HTMLParser):
    """Collects the Squarespace menu block: tabs -> sections -> items, and the key icons."""

    FIELDS = {"menu-section-title": "title", "menu-section-description": "description",
              "menu-item-title": "title", "menu-item-description": "description",
              "menu-item-price-top": "price"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.tabs, self.icons = [], []
        self.field = None  # (key, target dict, depth, text parts)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag not in ("img", "br", "meta", "link", "input"):
            self.depth += 1
        if tag == "img":
            m = re.search(r"/allergen-([0-9a-z-]+)\.png", a.get("src") or a.get("data-src") or "")
            if m:
                self.icons.append(m.group(1))
        if "js-menu" in classes and a.get("role") == "tabpanel":
            self.tabs.append({"tab": a.get("aria-label"), "sections": []})
        elif "menu-section" in classes and self.tabs:
            self.tabs[-1]["sections"].append({"title": "", "description": "", "items": []})
        elif "menu-item" in classes and self.tabs:
            self.tabs[-1]["sections"][-1]["items"].append({"title": "", "description": "", "price": ""})
        for cls, key in self.FIELDS.items():
            if cls in classes:
                section = self.tabs[-1]["sections"][-1]
                target = section if cls.startswith("menu-section") else section["items"][-1]
                self.field = (key, target, self.depth, [])

    def handle_endtag(self, tag):
        if self.field and self.depth == self.field[2]:
            key, target, _, parts = self.field
            target[key] = " ".join("".join(parts).split())
            self.field = None
        self.depth -= 1

    def handle_data(self, data):
        if self.field:
            self.field[3].append(data)


def codes_in(text, where):
    found = [int(c) for group in CODES.findall(text) for c in re.split(r"\s*,\s*", group)]
    for c in found:
        if c not in KEY:
            fail(f"{where}: code {c} isn't in the key")
    return set(found)


def strip_codes(text):
    return " ".join(CODES.sub("", text).split()).rstrip(".")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("html")
    parser.add_argument("--out", default="Imports/menus/poplars-tea-room.csv")
    parser.add_argument("--any-version", action="store_true",
                        help="read a menu other than the one this script was checked against")
    args = parser.parse_args()

    p = MenuParser()
    with open(args.html, encoding="utf-8") as f:
        p.feed(f.read())
    if sorted(set(p.icons)) != ICONS:
        fail(f"key icons are {sorted(set(p.icons))}, expected {ICONS}")
    if [t["tab"] for t in p.tabs] != TABS:
        fail(f"menu tabs are {[t['tab'] for t in p.tabs]}")
    digest = hashlib.sha256(json.dumps(p.tabs, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if digest != MENU_SHA256 and not args.any_version:
        fail(f"the menu isn't the one this script was checked against (menu SHA-256 {digest}). "
             f"Check it by eye, then run with --any-version.")

    food = p.tabs[0]["sections"]
    rows, left_out, notes = [], [], []
    for section in food:
        if not section["title"]:
            if section["items"]:
                fail("a section with items but no title")
            continue
        sname = section["title"]
        section_codes = codes_in(section["description"], sname)
        titles = [i["title"] for i in section["items"]]
        items = section["items"]
        k = 0
        while k < len(items):
            item = items[k]
            k += 1
            title, desc, price = item["title"], item["description"], item["price"].lstrip("£")
            where = f"[{sname}] {title}"
            if (sname, title) in NOTES:
                notes.append(f"{where} {desc}".strip())
                continue
            if (sname, title) in CHOOSE_YOUR_OWN:
                codes = sorted(codes_in(f"{section['description']} {title} {desc}", where))
                left_out.append(f"{where}: {desc} £{price} -- {CHOOSE_YOUR_OWN[(sname, title)]}")
                continue
            if "Takeaway" in title or "Takeaway" in desc:
                left_out.append(f"{where} {desc} £{price} -- takeaway price line, no codes printed")
                continue
            # The ice cream's price and codes are on the item after it.
            if (k < len(items) and not price and not codes_in(title + desc, where)
                    and items[k]["title"].startswith("Per Scoop")):
                nxt = items[k]
                k += 1
                desc = f"Per scoop. {desc}".strip()
                price = nxt["price"].lstrip("£")
                code_text = nxt["title"]
            else:
                code_text = f"{title} {desc}"
            codes = codes_in(code_text, where)
            name = strip_codes(title)
            description = strip_codes(desc)
            if sname == "Ploughman’s":
                if title != "Fillings - Choose Two":
                    fail(f"{where}: unexpected Ploughman's item")
                name = "Ploughman’s"
                description = f"{strip_codes(section['description'])}. Fillings - choose two: {description}"
            if titles.count(title) > 1:
                name = f"{name} - {description}"
            if sname in SECTION_CODES_APPLY:
                codes |= section_codes
                if not description:  # what every dish in the section comes with
                    description = strip_codes(section["description"])
            elif section_codes and sname != "Sandwiches":
                fail(f"{where}: section codes {sorted(section_codes)} with no rule for them")
            if sname == "Sandwiches":
                description = f"{description}. {SANDWICH_NOTE}" if description else SANDWICH_NOTE
            if not codes:
                left_out.append(f"{where} {desc} £{price} -- no codes printed")
                continue
            rows.append({"category": sname, "dish": name, "description": description, "price": price,
                         "codes": codes, "printed": f"{title} | {desc}".strip(" |")})

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
            labels = {KEY[c]: "Y" for c in r["codes"]}
            writer.writerow([r["category"], r["dish"], r["description"], r["price"]]
                            + [labels.get(a, "") for a in ALLERGENS])

    category = None
    for r in rows:
        if r["category"] != category:
            category = r["category"]
            print(f"--- {category}")
        names = ", ".join(KEY[c] for c in sorted(r["codes"]))
        print(f"{r['dish']}  £{r['price']}\n      printed: {r['printed']}\n      "
              f"[{','.join(str(c) for c in sorted(r['codes']))}] {names}")
    print(f"\n{len(rows)} dishes written to {args.out}")
    print("\nLEFT OUT:", *left_out, sep="\n  ")
    drinks = sum(len(s["items"]) for s in p.tabs[1]["sections"])
    print(f"\nLeft out the DRINKS tab: {drinks} items in "
          f"{', '.join(s['title'] for s in p.tabs[1]['sections'] if s['title'])}")
    if notes:
        print("\nNotes:", *notes, sep="\n  ")
    print(f"\nmenu SHA-256 {digest}")


if __name__ == "__main__":
    main()
