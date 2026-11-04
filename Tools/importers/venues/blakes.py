#!/usr/bin/env python3
"""Blakes (59-61 King Street, St Helier): read its menus' allergen codes into Imports/menus/blakes.csv.

Source: "Blakes Menu", two A3 pages made with Canva on 21 August 2026, linked from
https://www.blakes.je/ as
https://irp.cdn-website.com/cd44ce23/files/uploaded/Blakes_Menu_08_26.pdf
(SHA-256 fd2095f7e99fe90b485331c7e20cfac14c9b2522c03301728bcc6aa44048a12d).
Page 1 is the day menu (breakfast, lunch plates, sides, desserts); page 2 is the evening
menu. The site also links Blakes_Lunch_Menu_08_26.pdf and Blakes_Dinner_Menu_08_26.pdf: their
text is identical to pages 1 and 2 of this file, so only this file is read.

Layout: free-form Canva pages. Each dish prints its allergen codes in brackets after its
name, e.g. "Cheese Toastie (2AB,7) 8.50", and some extras print their own codes, e.g.
"Smoked Salmon (5) +4.00". The key, printed at the foot of both pages:
  1 Celery | 2 Gluten (Cereals) A) wheat B) barley C) Rye | 3 Crustacean | 4 Eggs | 5 Fish |
  6 Lupin | 7 Milk | 8 Mollusc | 9 Mustard | 10 Nuts | 11 Peanuts | 12 Sesame Seeds |
  13 Soya | 14 Sulphur Dioxide (Sulphites)
2, 2A, 2AB, 2AC all mean Gluten. The script reads the code numbers from this printed key
(KEY_NAMES maps each printed name to the app's allergen) and stops if it is different.

How it reads the page: the menu's items are transcribed below (ITEMS), region by region,
from the rendered pages. The script then checks the transcription against the PDF itself:
  * every word on each page lies in exactly one region;
  * each region's words, in reading order, are exactly its items' printed text, word for
    word, so nothing on the page is skipped or misread;
  * every allergen code group in a CSV row is printed in that item (or, for an extra, in the
    dish it is added to), every code group an item prints is used, and every price is printed.
So the codes in the CSV are the PDF's own text; only which dish they belong to comes from
reading the rendered page.

What goes in the CSV:
  * Every dish that prints codes, with its codes as Y (the menu has no "may contain").
  * An extra that prints its own codes (smoked salmon on the omelette, a fried or poached
    egg, the salad toppings) becomes its own row "<dish> with <extra>", with the dish's codes
    plus the extra's, priced as the dish plus the supplement.
  * A choice of sauce with its own codes (the ribeye's peppercorn sauce) becomes one row per
    choice. The pancakes' three toppings are listed with " | " like any other dish's
    components, so it isn't clear whether they're a choice; they're one row with all codes.
Left out, and listed when the script runs: anything printed with no codes. The menu doesn't
say every dish is coded ("Full allergen information is available upon request"), so no
codes can't be read as no allergens. That includes uncoded extras (bacon, sausage, avocado,
grilled chicken, halloumi), the 6oz flat iron steak with peppercorn sauce (evening menu: the
peppercorn option is uncoded there), the sweet trolley, and the orange juice.

category is the menu's own section heading. The day menu's headings carry their printed
serving times; the evening menu's are prefixed "EVENING —". Codes are stripped from
descriptions (they're in the allergen columns); two-size prices go in the description.

Usage:
  python3 Tools/importers/venues/blakes.py Blakes_Menu_08_26.pdf [--out Imports/menus/blakes.csv] [--any-version]
Prints every row with its allergens, then what was left out. Needs pdfplumber.
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

EXPECTED_SHA256 = "fd2095f7e99fe90b485331c7e20cfac14c9b2522c03301728bcc6aa44048a12d"

KEY_TEXT = ("1 Celery | 2 Gluten (Cereals) A) wheat B) barley C) Rye | 3 Crustacean | 4 Eggs | "
            "5 Fish | 6 Lupin | 7 Milk | 8 Mollusc | 9 Mustard | 10 Nuts | 11 Peanuts | "
            "12 Sesame Seeds | 13 Soya | 14 Sulphur Dioxide (Sulphites)")
# Each name as the key prints it → the app's allergen. The numbers come from KEY_TEXT.
KEY_NAMES = {
    "Celery": "Celery",
    "Gluten (Cereals) A) wheat B) barley C) Rye": "Gluten",
    "Crustacean": "Crustaceans",
    "Eggs": "Eggs",
    "Fish": "Fish",
    "Lupin": "Lupin",
    "Milk": "Milk",
    "Mollusc": "Molluscs",
    "Mustard": "Mustard",
    "Nuts": "Nuts",
    "Peanuts": "Peanuts",
    "Sesame Seeds": "Sesame",
    "Soya": "Soybeans",
    "Sulphur Dioxide (Sulphites)": "Sulphur Dioxide",
}
GLUTEN_NUMBER, GLUTEN_LETTERS = 2, "ABC"  # 2A wheat, 2B barley, 2C rye
CODE_GROUP = re.compile(r"\((\s*\d+[A-Z]*\s*(?:,\s*\d+[A-Z]*\s*)*)\)")


def fail(message):
    sys.exit(f"blakes.py: STOPPED: {message}")


# ---- transcription helpers ---------------------------------------------------------------

def norm(text):
    text = " ".join(text.split())
    text = re.sub(r"\(\s+", "(", text)
    return re.sub(r"\s+\)", ")", text)


def strip_codes(text):
    return norm(CODE_GROUP.sub("", text))


def H(printed, category=None):
    """Printed text that isn't a dish (heading, note). With category, starts that section."""
    return {"kind": "text", "printed": norm(printed), "category": category}


def R(dish, codes, price="", desc="", base=None):
    """A CSV row. codes: the printed code groups it takes (without brackets). price: as
    printed, or a tuple of printed prices to add. base: the dish an extra is added to."""
    return {"dish": dish, "codes": list(codes), "price": price, "desc": desc, "base": base}


def D(printed, *rows, left_out=None, summary=()):
    """A printed item, the rows it becomes, and what of it (if anything) is left out.
    summary: printed code groups that only total up the item's other groups (not used)."""
    return {"kind": "dish", "printed": norm(printed), "rows": list(rows), "left_out": left_out,
            "summary": list(summary)}


def X(printed, why):
    """A printed item left out of the CSV entirely."""
    return {"kind": "dish", "printed": norm(printed), "rows": [], "left_out": why, "summary": []}


def _price(price):
    if " | " in price:  # two sizes: no single price
        return "", f" ({price.replace(' | ', ' / ')})"
    return price, ""


def L(name, codes, price, desc=""):
    """List layout: 'Name (codes) price' then the description."""
    printed = " ".join(p for p in (name, f"({codes})" if codes else "", price, desc) if p)
    if codes is None:
        return X(printed, "no allergen codes")
    csv_price, extra = _price(price)
    return D(printed, R(name, [codes] + CODE_GROUP.findall(desc), csv_price, strip_codes(desc) + extra))


def T(name, codes, desc, price):
    """Tile layout: name, (codes), description, price."""
    printed = " ".join(p for p in (name, f"({codes})" if codes else "", desc, price) if p)
    if codes is None:
        return X(printed, "no allergen codes")
    csv_price, extra = _price(price)
    return D(printed, R(name, [codes] + CODE_GROUP.findall(desc), csv_price, strip_codes(desc) + extra))


# ---- the menu, as printed ----------------------------------------------------------------

DAY_PLATES = "PLATES (12:00pm - 3:00pm)"
DAY_SIDES = "SIDES (12:00pm - 3:00pm)"
EVE_PLATES = "EVENING — PLATES"
EVE_SIDES = "EVENING — SIDES"

CAESAR = ("Classic Caesar Salad", "2AB,4,5,7,9",
          "Romaine Lettuce | Classic Dressing | Boiled Egg | Crispy Bacon | Parmesan | Croutons | Anchovies")
BLAKES_SALAD = ("Blakes Salad", "2AB,4,7,10",
                "Mixed Leaves | Olives | Boiled Egg | Tomatoes | Parmesan | Croutons | Walnuts | Oil Dressing")
PANCAKES_DESC = ("Berry Compote & Jersey Yogurt (7) | Hot Nutella & Whipped Cream (7,10,13) | "
                 "Scoop of Jersey Ice Cream (7)")
PANCAKES = D(f"Buttermilk Pancakes (2A,4,7) 12.00 {PANCAKES_DESC}",
             R("Buttermilk Pancakes", ["2A,4,7", "7", "7,10,13"], "12.00", strip_codes(PANCAKES_DESC)))
KEY_BAND = H("ALLERGEN KEY " + KEY_TEXT + " Please inform a member of staff of any allergies or "
             "intolerances before placing your order. Full allergen information is available upon request.")


def topping_rows(salad, price):
    name, codes, _ = salad
    return [R(f"{name} with Grilled Goat Cheese", [codes, "7"], (price, "+5.50"),
              "Topping: Grilled Goat Cheese +5.50", base=name),
            R(f"{name} with Smoked Salmon", [codes, "5"], (price, "+6.50"),
              "Topping: Smoked Salmon +6.50", base=name)]


TOPPINGS_LEFT_OUT = "toppings Grilled Chicken +5.50 and Halloumi +5.50: no allergen codes"

# page → list of (region box x0, top, x1, bottom in pt, starting category, items in reading order)
PAGES = {
    1: [
        ((0, 100, 300, 760), None, [
            H("OPENING TIMES Monday - Saturday 10am - Late"),
            H("BREAKFAST from 10:00am - 11:45am", "BREAKFAST (10:00am - 11:45am)"),
            X("Add Freshly Squeezed Orange Juice for 4.50", "drink, no allergen codes"),
            D("Sausage or Bacon Breakfast Roll (2A,7,13) 6.50 Sausage | Bacon | Omelette | Fried Egg (4) +2.00 each",
              R("Sausage or Bacon Breakfast Roll", ["2A,7,13"], "6.50"),
              R("Sausage or Bacon Breakfast Roll with Fried Egg", ["2A,7,13", "4"], ("6.50", "+2.00"),
                "Extra: Fried Egg +2.00"),
              left_out="extras Sausage, Bacon and Omelette +2.00 each: no allergen codes"),
            L("Cheese Toastie", "2AB,7", "8.50", "Cheese Mix | Béchamel"),
            L("Croque Monsieur", "2AB,7", "10.00", "Ham | Cheese Mix | Béchamel"),
            L("Croque Madame", "2AB,4,7", "12.00", "Ham | Cheese Mix | Béchamel | Fried Egg"),
            D("Omelette (4,7) 9.50 Bacon +2.00 | Sausage +2.00 | Smoked Salmon (5) +4.00 | Avocado +3.00",
              R("Omelette", ["4,7"], "9.50"),
              R("Omelette with Smoked Salmon", ["4,7", "5"], ("9.50", "+4.00"), "Extra: Smoked Salmon +4.00"),
              left_out="extras Bacon +2.00, Sausage +2.00 and Avocado +3.00: no allergen codes"),
            D("Crushed Avo on Sourdough (2A) 8.50 Bacon Bits +2.00 | Poached Egg(4) +2.00",
              R("Crushed Avo on Sourdough", ["2A"], "8.50"),
              R("Crushed Avo on Sourdough with Poached Egg", ["2A", "4"], ("8.50", "+2.00"),
                "Extra: Poached Egg +2.00"),
              left_out="extra Bacon Bits +2.00: no allergen codes"),
            L("Smoked Salmon Sourdough", "2A,5,7", "9.50", "Cream Cheese | Lemon | Black Pepper"),
            PANCAKES,
            L("Overnight Oats", "7,10", "9.50",
              "Blueberries | Coconut | Granola | Blue Spirulina | Yoghurt | Pecan | Almond | Hazelnut"),
            H("*All our eggs are Clarence Court Burford Brown free range"),
        ]),
        ((300, 100, 890, 145), None, [H("PLATES from 12:00pm - 3:00pm")]),
        ((300, 145, 452, 600), DAY_PLATES, [
            T("Blakes Baguettes", "2A,4,7,9", "Chicken, Bacon, Sweetcorn & Mayo or Ham, Emmental, Dijon "
              "Mustard, Mayo & Rocket, served with crisps", "9.95"),
            T("Seasonal Vegetable Quiche", "2A,4,7,9", "Seasonal Vegetable Quiche | Mixed Dressed Leaves", "13.50"),
            T("Blakes Club Sandwich", "2AB,4,9", "Roast Chicken | Smoked Bacon | Egg Mayo | Vine Tomatoes | "
              "Baby Gem | Toasted Granary", "14.00"),
            T("6oz Flat Iron Steak", "4,5,7,9,10", "Prime Centre-Cut 6oz Steak | Blakes Dijon Butter-Herb "
              "Sauce | Skin-On Fries", "19.50"),
        ]),
        ((452, 145, 589, 600), DAY_PLATES, [
            T("Beef Carpaccio", "7,9", "Thin-Sliced Fillet | Extra Virgin Olive Oil | Lemon Juice | Shaved "
              "Parmesan | Rocket", "15.95"),
            T(*CAESAR, "13.50"),
            T("Lobster Roll", "2A,3,4,7,9", "Atlantic Lobster | Lightly dressed in Blakes Lemon - Butter Mayo | "
              "Toasted Brioche Roll", "19.95"),
            T("Chicken Milanese with Truffle Sauce", "2A,4,7", "Crumbed Chicken Breast | Fried Hen’s Egg | "
              "Green Leaves | Parmesan", "18.95"),
        ]),
        ((589, 145, 735, 600), DAY_PLATES, [
            T("Smoked Salmon Plate", "2A,5,7", "Norwegian Smoked VAR Salmon | Black Pepper | Lemon Thin "
              "Sourdough | Horse Radish Cream Cheese (7)", "15.95"),
            T(*BLAKES_SALAD, "13.50"),
            T("Petite Fillet Steak Ciabatta", "2AC,4,9", "5-oz of Filet Medallions | Caramelised Onions | "
              "Crisp Rocket | Horseradish Mayo", "16.95"),
            T("Jersey Beef Smash Burger", "2AC,4,7,9", "Double Patties | Bacon | Brioche | Cheese | Burger "
              "Sauce | Caramelised Onion", "16.50"),
        ]),
        ((735, 145, 890, 600), DAY_PLATES, [
            T("Scottish Smoked Haddock & Salmon Fishcake", "2A,4,5,7", "Blakes Haddock & Salmon Fishcake | "
              "Fish Velouté | Dill Oil", "18.95"),
            D("Choose Your Salad Topping (7,5) Grilled Goat Cheese +5.50 (7) Grilled Chicken +5.50 "
              "Smoked Salmon +6.50 (5) Halloumi +5.50",
              *topping_rows(CAESAR, "13.50"), *topping_rows(BLAKES_SALAD, "13.50"),
              left_out=TOPPINGS_LEFT_OUT, summary=["7,5"]),  # (7,5) = goat cheese (7) + salmon (5)
            T("Blakes Pasta Bowl", "2A,7,10", "Penne Pasta in a Creamy Pesto Sauce with Chicken, Parmesan and "
              "Pine Nuts", "16.50"),
            T("Seabass Fillet", "5,7", "Pan-Fried Fillet | Lemon and Chive Beurre Blanc | Crushed New "
              "Potatoes", "19.95"),
        ]),
        ((300, 600, 890, 640), None, [H("SIDES from 12:00pm - 3:00pm")]),
        ((300, 640, 598, 760), DAY_SIDES, [
            L("Mixed Leaf Salad", None, "5.00"),
            L("Mixed Seasonal Vegetables", "7", "5.00"),
            L("Smoked Almonds", "10", "4.50"),
            L("Spiced Gordal Olives", None, "4.50"),
            L("Asparagus & Butter", "7", "6.00"),
        ]),
        ((598, 640, 890, 760), DAY_SIDES, [
            L("Jersey Royals or New Potatoes (Seasonal)", "7", "5.00"),
            L("Skin On Fries", None, "5.00"),
            L("Skin On Fries with Truffle & Parmesan", "7", "6.00"),
            L("Salt Crusted Sourdough", "2A", "5.00"),
            L("Mini Chorizo", "7", "7.50"),
        ]),
        ((890, 100, 1190, 760), None, [
            H("THE SWEET TROLLEY Available All Day"),
            X("Fresh Baked Croissants, Pain au Chocolat, Pain aux Raisins, Scones & tempting selection of "
              "Blakes Cakes. All made with care, absolutely delicious, and all best enjoyed before they’re "
              "gone! All of these irresistible in house treats are freshly prepared using the finest "
              "ingredients and are available on The Sweet Trolley.", "sweet trolley: no allergen codes"),
            H("DESSERTS from 12:00pm - 3:30pm", "DESSERTS (12:00pm - 3:30pm)"),
            L("The Famous Albert Adrià Cheesecake", "2A,4,7", "9.00", "Cape Gooseberries & Raspberry Coulis"),
            L("Frozen Forest Berries", None, "9.00", "Mixed Red & Black Berries | Hot Luxury Valrhona Melted "
              "Chocolate"),
            L("Apple Tarte Tatin", "2A,4,7", "9.00", "Jersey Vanilla Ice Cream"),
            L("Jersey Vanilla Ice Cream", "2A,7", "6.00", "Jersey Butter Shortbread"),
            PANCAKES,
        ]),
        ((0, 760, 1190, 842.25), None, [KEY_BAND]),
    ],
    2: [
        ((0, 100, 300, 760), None, [
            H("EVENING MEAL TIMES Wednesday - Saturday 6:00PM - 9:00PM"),
            H("SNACKS", "EVENING — SNACKS"),
            L("Spiced Gordial Olives", None, "4.50", "Chilli | Coriander | Lemon"),
            L("Smoked Almonds", "10", "4.50"),
            L("Salt Crusted Sourdough", "2A", "5.00", "Olive Oil | Balsamic"),
            L("Mini Chorizos", "7", "7.50"),
            L("Ham Hock Croquettes", "1,2,4,7,9", "8.00", "Slow Cooked Ham Hock | Mustard Aioli"),
            L("Spicy & Tangy Chicken Bites", "2,7", "11.95", "Crispy Chicken Breast Bites | Spicy & Tangy "
              "Buffalo Glaze | Cooling Blue Cheese Dip"),
            H("BLAKES SALADS", "EVENING — BLAKES SALADS"),
            L(CAESAR[0], CAESAR[1], "13.50", CAESAR[2]),
            L(BLAKES_SALAD[0], BLAKES_SALAD[1], "13.50", BLAKES_SALAD[2]),
            D("ADD: Grilled Goat Cheese +5.50 (7) | Grilled Chicken +5.50 | Smoked Salmon +6.50 (5) | "
              "Halloumi +5.50",
              *topping_rows(CAESAR, "13.50"), *topping_rows(BLAKES_SALAD, "13.50"),
              left_out=TOPPINGS_LEFT_OUT),
        ]),
        ((300, 100, 890, 145), None, [H("PLATES", EVE_PLATES)]),
        ((300, 145, 455, 630), EVE_PLATES, [
            T("Crab on Toast", "2A,3,4,9", "Sourdough | Crab Meat | Fresh Chilli | Sriracha | Devilled "
              "Sweetcorn | Lime | Ginger | Garlic", "14.95"),
            T("Smoked Salmon Plate", "2A,5,7", "Norwegian Smoked VAR Salmon | Black Pepper | Thin Sourdough | "
              "Lemon Horse Radish Cream Cheese (7)", "15.95"),
            T("Jersey Beef Smash Burger", "2AC,4,7,9", "Double Patties | Bacon | Brioche | Cheese | Burger "
              "Sauce | Caramelised Onion", "16.50"),
            D("6oz Flat Iron Steak (4,5,7,9,10) Prime Centre-Cut 6oz Steak | Blakes Dijon Butter-Herb Sauce or "
              "Peppercorn | Skin-On Fries 19.50",
              R("6oz Flat Iron Steak with Blakes Dijon Butter-Herb Sauce", ["4,5,7,9,10"], "19.50",
                "Prime Centre-Cut 6oz Steak | Blakes Dijon Butter-Herb Sauce | Skin-On Fries"),
              left_out="the Peppercorn sauce option: no allergen codes for it on this dish"),
        ]),
        ((455, 145, 601, 630), EVE_PLATES, [
            T("Panko Prawns", "2A,3,4,8,9", "Golden Panko King Prawns | House Asian Dipping Sauce | Spring "
              "Onions | Sesame Seeds", "10.95 | 17.95"),
            T("Scottish Smoked Haddock & Salmon Fishcake", "2A,4,5,7", "Blakes Haddock & Salmon Fishcake | "
              "Fish Velouté | Dill Oil", "18.95"),
            T("Chicken Milanese with Truffle Sauce", "2A,4,7", "Crumbed Chicken Breast | Fried Hen’s Egg | "
              "Green Leaves | Parmesan", "18.95"),
            T("Buttermilk Chicken Bites & Chips", "2A,7", "Crispy Chicken Breast Bites | Spicy & Tangy "
              "Buffalo Glaze | Skin-on Fries | Blue Cheese Dip", "18.95"),
        ]),
        ((601, 145, 741, 630), EVE_PLATES, [
            T("Salt & Pepper Squid", "2A,4,8,9,13", "Tender Salt & Pepper Squid | Lightly Fried until Crisp | "
              "Garlic Mayo | Fresh Lemon Wedges", "10.95 | 17.95"),
            T("Lobster Roll", "2A,3,4,7,9", "Atlantic Lobster | Lightly dressed in Blakes Lemon - Butter Mayo | "
              "Toasted Brioche Roll", "19.95"),
            T("Blakes Chicken Burger", "2AC,4,7,9", "Crumbed Chicken Breast | Bacon | Brioche | Cheese | "
              "Burger Sauce | Caramelised Onion", "16.50"),
            T("Petite Fillet Steak Ciabatta", "2AC, 4, 9", "5-oz of Filet Medallions | Caramelised Onions | "
              "Crisp Rocket | Horseradish Mayo", "16.95"),
        ]),
        ((741, 145, 890, 630), EVE_PLATES, [
            T("Beef Carpaccio", "7,9", "Thin-Sliced Fillet | Extra Virgin Olive Oil | Lemon Juice | Shaved "
              "Parmesan | Rocket", "15.95"),
            T("Seabass Fillet", "5,7", "Pan-Fried Fillet | Lemon and Chive Beurre Blanc | Crushed New "
              "Potatoes", "19.95"),
            D("10oz Ribeye Steak (4,5,7,9,10) 10oz Ribeye Steak | Blakes Dijon Butter-Herb Sauce or Peppercorn "
              "Sauce (1,7,14) | Skin-On Fries 32.95",
              R("10oz Ribeye Steak with Blakes Dijon Butter-Herb Sauce", ["4,5,7,9,10"], "32.95",
                "10oz Ribeye Steak | Blakes Dijon Butter-Herb Sauce | Skin-On Fries"),
              R("10oz Ribeye Steak with Peppercorn Sauce", ["4,5,7,9,10", "1,7,14"], "32.95",
                "10oz Ribeye Steak | Peppercorn Sauce | Skin-On Fries")),
            T("Blakes Pasta Bowl", "2A,7,10", "Penne Pasta in a Creamy Basil Pesto Sauce with Chicken, "
              "Parmesan and Pine Nuts", "16.50"),
        ]),
        ((300, 630, 890, 665), None, [H("SIDES", EVE_SIDES)]),
        ((300, 665, 598, 760), EVE_SIDES, [
            L("Mixed Leaf Salad", None, "5.00"),
            L("Mixed Seasonal Vegetables", "7", "5.00"),
            L("Asparagus & Butter", "7", "6.00"),
        ]),
        ((598, 665, 890, 760), EVE_SIDES, [
            L("Jersey Royals or New Potatoes (Seasonal)", "7", "5.00"),
            L("Skin On Fries", None, "5.00"),
            L("Skin On Fries with Truffle & Parmesan", "7", "6.00"),
        ]),
        ((890, 100, 1190, 760), None, [
            H("AFTER DINNER INDULGENCES", "EVENING — AFTER DINNER INDULGENCES"),
            D("Espresso Martini Affogato (7) - 15.00 Jersey Vanilla Ice Cream | Double Espresso | Kahlua | "
              "Vodka | Chocolate Shavings",
              R("Espresso Martini Affogato", ["7"], "15.00",
                "Jersey Vanilla Ice Cream | Double Espresso | Kahlua | Vodka | Chocolate Shavings")),
            D("Limoncello Sundae (7) - 15.00 Lemon Sorbet | Vanilla Ice Cream | Limoncello | Candied Lemon Peel",
              R("Limoncello Sundae", ["7"], "15.00", "Lemon Sorbet | Vanilla Ice Cream | Limoncello | Candied "
                "Lemon Peel")),
            D("Baileys Brownie Sundae - 15.00 (2A,4,7,13) Warm Brownie | Vanilla Ice Cream | Baileys & "
              "Chocolate sauce",
              R("Baileys Brownie Sundae", ["2A,4,7,13"], "15.00", "Warm Brownie | Vanilla Ice Cream | Baileys & "
                "Chocolate sauce")),
            H("DESSERTS", "EVENING — DESSERTS"),
            L("The Famous Albert Adrià Cheesecake", "2A,4,7", "9.00", "Cape Gooseberries & Raspberry Coulis"),
            L("Frozen Forest Berries", None, "9.00", "Mixed Red & Black Berries | Hot Luxury Valrhona Melted "
              "Chocolate"),
            L("Apple Tarte Tatin", "2A,4,7", "9.00", "Jersey Vanilla Ice Cream"),
            L("Jersey Vanilla Ice Cream", "2A,7", "6.00", "Jersey Butter Shortbread"),
            PANCAKES,
        ]),
        ((0, 760, 1190, 842.25), None, [KEY_BAND]),
    ],
}


# ---- checking the transcription against the PDF ------------------------------------------

def read_key():
    """The printed key → {code number: app allergen}."""
    key = {}
    for part in KEY_TEXT.split(" | "):
        number, name = part.split(" ", 1)
        if name not in KEY_NAMES:
            fail(f"key entry {part!r} isn't in KEY_NAMES")
        key[int(number)] = KEY_NAMES[name]
    if sorted(key) != list(range(1, 15)) or sorted(key.values()) != sorted(ALLERGENS):
        fail("the key doesn't give each of the 14 allergens one number")
    return key


def allergens_of(group, key):
    found = set()
    for token in group.split(","):
        m = re.fullmatch(r"(\d+)([A-Z]*)", token.strip())
        if not m or int(m[1]) not in key:
            fail(f"code {token!r} in ({group}) isn't in the key")
        if m[2] and (int(m[1]) != GLUTEN_NUMBER or set(m[2]) - set(GLUTEN_LETTERS)):
            fail(f"code {token!r} in ({group}): only {GLUTEN_NUMBER} takes letters {GLUTEN_LETTERS}")
        found.add(key[int(m[1])])
    return found


def region_text(words, box, tolerance=3.5):
    """The words whose centre is in box, in reading order (line by line, left to right)."""
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


def price_tokens(text):
    return set(re.findall(r"\+?\d+\.\d\d", text))


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
            claimed = {}
            items_by_name = {}
            for box, category, items in PAGES[n]:
                text, inside = region_text(words, box)
                for w in inside:
                    if id(w) in claimed:
                        fail(f"page {n}: {w['text']!r} is in two regions")
                    claimed[id(w)] = box
                expected = norm(" ".join(item["printed"] for item in items))
                if text != expected:
                    fail(f"page {n} region {box} doesn't match the transcription:\n  {first_difference(text, expected)}")
                for item in items:
                    if item["kind"] == "dish" and item["rows"]:
                        items_by_name[item["rows"][0]["dish"]] = item
            stray = [w["text"] for w in words if id(w) not in claimed]
            if stray:
                fail(f"page {n}: words outside every region: {stray}")
            if KEY_TEXT not in norm(page.extract_text()):
                fail(f"page {n} doesn't print the expected allergen key")

            for box, category, items in PAGES[n]:
                for item in items:
                    if item["kind"] == "text":
                        category = item["category"] or category
                        continue
                    if item["left_out"]:
                        left_out.append((n, category, item["printed"], item["left_out"]))
                    printed_groups = CODE_GROUP.findall(item["printed"])
                    used = set()
                    for row in item["rows"]:
                        if category is None:
                            fail(f"page {n}: {row['dish']!r} has no section")
                        allowed = list(printed_groups)
                        own = printed_groups[:1]
                        if row["base"]:
                            base = items_by_name.get(row["base"])
                            if not base:
                                fail(f"page {n}: {row['dish']!r}: no dish {row['base']!r} on this page")
                            own = CODE_GROUP.findall(base["printed"])[:1]
                            allowed += own
                        for group in row["codes"]:
                            if group not in allowed:
                                fail(f"page {n}: {row['dish']!r} takes ({group}), which its item doesn't print")
                        if not own or own[0] not in row["codes"]:
                            fail(f"page {n}: {row['dish']!r} must include its dish's own codes {own}")
                        used.update(row["codes"])
                        prices = row["price"] if isinstance(row["price"], tuple) else (row["price"],)
                        printed_prices = price_tokens(item["printed"]) | (
                            price_tokens(items_by_name[row["base"]]["printed"]) if row["base"] else set())
                        for p in prices:
                            if p and p not in printed_prices:
                                fail(f"page {n}: {row['dish']!r} price {p} isn't printed with it")
                        total = sum(Decimal(p.lstrip("+")) for p in prices if p)
                        found = set()
                        for group in row["codes"]:
                            found |= allergens_of(group, key)
                        rows.append({"page": n, "category": category, "dish": row["dish"],
                                     "description": row["desc"],
                                     "price": f"{total:.2f}" if any(prices) else "",
                                     "allergens": found, "codes": row["codes"]})
                    for group in item["summary"]:
                        if group not in printed_groups or allergens_of(group, key) != set().union(
                                *(allergens_of(g, key) for g in printed_groups if g != group)):
                            fail(f"page {n}: ({group}) isn't the total of {item['printed'][:40]!r}'s other codes")
                    unused = [g for g in printed_groups if g not in used and g not in item["summary"]]
                    if item["rows"] and unused:
                        fail(f"page {n}: {item['printed'][:50]!r} prints codes {unused} that no row uses")
    return rows, left_out


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--out", default=os.path.join(root, "Imports", "menus", "blakes.csv"))
    parser.add_argument("--any-version", action="store_true",
                        help="read a PDF other than the one this script was checked against")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EXPECTED_SHA256 and not args.any_version:
        fail(f"{args.pdf} isn't the 21 August 2026 menu this script was checked against "
             f"(SHA-256 {digest}). Check the new menu by eye, update ITEMS, then run with --any-version.")

    key = read_key()
    rows, left_out = read(args.pdf, key)

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
        codes = " + ".join(f"({c})" for c in r["codes"])
        print(f"  {r['dish']} {codes}: {', '.join(a for a in ALLERGENS if a in r['allergens'])}")
    print(f"\n{len(rows)} rows written to {args.out}")

    print("\nLeft out (no allergen codes printed):")
    for n, category, printed, why in left_out:
        print(f"  p{n} [{category}] {printed[:90]}{'…' if len(printed) > 90 else ''}\n      → {why}")

    by_name = {}
    for r in rows:
        by_name.setdefault(r["dish"], []).append(r)
    differ = [(name, rs) for name, rs in by_name.items() if len({frozenset(r["allergens"]) for r in rs}) > 1]
    print("\nSame dish, different codes on different menus:" if differ else
          "\nNo dish has different codes on the day and evening menus.")
    for name, rs in differ:
        for r in rs:
            print(f"  {name} [{r['category']}]: {', '.join(a for a in ALLERGENS if a in r['allergens'])}")


if __name__ == "__main__":
    main()
