#!/usr/bin/env python3
"""Turn Imports/ into SQL that loads restaurants and their menus into Supabase.

Inputs:
  Imports/restaurants.csv     one row per restaurant (slug, name, address, phone, website,
                              menu_url, allergen_info_url, allergen_info_date, latitude,
                              longitude, free_tier)
  Imports/menus/<slug>.csv    category, dish, description, price, then one column per
                              allergen: Y = contains, M = may contain, blank = doesn't
  Imports/held/<slug>.csv     dishes to leave out (from `allergy-tools review --write`):
                              the menu's wording contradicts the restaurant's allergen data

A restaurant with an allergen_info_url goes live (is_active = true) with its allergens.
One without stays hidden (is_active = false). Its menu is stored, but no dish of it can
reach the app looking allergen-free. Re-running replaces each restaurant's menu, keyed on
its slug. Leave free_tier blank to keep the current setting (new restaurants start as Pro).

Usage:
  python3 Tools/importers/build_import_sql.py [--only slug …] [--new] > import.sql

--new writes insert-only SQL for restaurants that aren't in the database yet: nothing is
deleted or updated, and it fails without changing anything if a slug already exists.
Then run the SQL against the database (e.g. in the Supabase SQL editor).
"""
import argparse
import csv
import os
import sys

ALLERGENS = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
             "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]
LEVELS = {"Y": "contains", "M": "may_contain"}


def q(value):
    """SQL literal, or null for blank."""
    if value is None or str(value).strip() == "":
        return "null"
    return "'" + str(value).strip().replace("'", "''") + "'"


def number(value):
    value = (value or "").strip()
    if not value:
        return "null"
    float(value)  # raises on bad input
    return value


def restaurant_sql(r, dishes, problems, new_only=False):
    slug = r["slug"]
    live = bool(r["allergen_info_url"].strip())
    rid = f"(select id from restaurants where import_slug = {q(slug)})"

    seen = set()
    for d in dishes:
        k = (d["category"], d["dish"])
        if k in seen:
            problems.append(f"{slug}: '{d['dish']}' appears twice in '{d['category']}'")
        seen.add(k)
        for a in ALLERGENS:
            v = d.get(a, "").strip().upper()
            if v and v not in LEVELS:
                problems.append(f"{slug}: '{d['dish']}' has '{v}' for {a}; use Y, M or blank")
            if v and not live:
                problems.append(f"{slug}: '{d['dish']}' has allergens but the restaurant has no allergen_info_url")

    free = r.get("free_tier", "").strip().lower()
    free_sql = {"true": "true", "yes": "true", "y": "true", "false": "false", "no": "false", "n": "false"}.get(free)
    cols = "import_slug, name, address, phone, website, menu_url, allergen_info_url, allergen_info_date, latitude, longitude, is_active"
    vals = ", ".join([q(slug), q(r["name"]), q(r["address"]), q(r["phone"]), q(r["website"]), q(r["menu_url"]),
                      q(r["allergen_info_url"]), q(r["allergen_info_date"]), number(r["latitude"]), number(r["longitude"]),
                      "true" if live else "false"])
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols.split(", ")[1:])
    if free_sql:
        cols += ", is_free_tier"
        vals += f", {free_sql}"
        updates += ", is_free_tier = excluded.is_free_tier"

    out = [f"-- {r['name']} ({'live: allergen data from the restaurant' if live else 'hidden: menu only, no allergen data'})"]
    if new_only:
        # Fails on the unique import_slug if the restaurant is already there.
        out.append(f"insert into restaurants ({cols}) values ({vals});")
    else:
        out.append(f"insert into restaurants ({cols}) values ({vals})\n  on conflict (import_slug) do update set {updates}, updated_at = now();")
        out.append(f"update menu_reports set menu_item_id = null where menu_item_id in (select id from menu_items where restaurant_id = {rid});")
        out.append(f"delete from menu_item_allergens where menu_item_id in (select id from menu_items where restaurant_id = {rid});")
        out.append(f"delete from menu_items where restaurant_id = {rid};")
        out.append(f"delete from menu_categories where restaurant_id = {rid};")

    categories = list(dict.fromkeys(d["category"] or "Menu" for d in dishes))
    if categories:
        rows = ",\n  ".join(f"({q(c)}, {i})" for i, c in enumerate(categories))
        out.append(f"insert into menu_categories (restaurant_id, name, display_order)\nselect {rid}, v.name, v.ord from (values\n  {rows}\n) as v(name, ord);")

    if dishes:
        rows = ",\n  ".join(f"({q(d['category'] or 'Menu')}, {q(d['dish'])}, {q(d['description'])}, {number(d['price'])}::numeric)" for d in dishes)
        out.append(
            "insert into menu_items (category_id, restaurant_id, name, description, price, is_available)\n"
            f"select c.id, c.restaurant_id, v.name, v.description, v.price, true from (values\n  {rows}\n) as v(category, name, description, price)\n"
            f"join menu_categories c on c.restaurant_id = {rid} and c.name = v.category;")

    # One row per dish: comma-separated allergens it contains, and ones it may contain.
    rows, n_links = [], 0
    for d in dishes:
        if not live:
            break
        contains = [a for a in ALLERGENS if d.get(a, "").strip().upper() == "Y"]
        may = [a for a in ALLERGENS if d.get(a, "").strip().upper() == "M"]
        if contains or may:
            n_links += len(contains) + len(may)
            contains_sql = q(",".join(contains)) if contains else "''"
            may_sql = q(",".join(may)) if may else "''"
            rows.append(f"({q(d['category'] or 'Menu')}, {q(d['dish'])}, {contains_sql}, {may_sql})")
    if rows:
        out.append(
            "insert into menu_item_allergens (menu_item_id, allergen_id, level)\n"
            "select mi.id, a.id, x.level from (values\n  " + ",\n  ".join(rows) + "\n) as v(category, item, contains, may)\n"
            f"join menu_categories c on c.restaurant_id = {rid} and c.name = v.category\n"
            "join menu_items mi on mi.category_id = c.id and mi.name = v.item\n"
            "cross join lateral (select unnest(string_to_array(nullif(v.contains, ''), ',')) as name, 'contains' as level\n"
            "                    union all select unnest(string_to_array(nullif(v.may, ''), ',')), 'may_contain') as x\n"
            "join allergens a on a.name = x.name;")
    return "\n".join(out), len(dishes), n_links, live


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--imports", default="Imports")
    parser.add_argument("--only", nargs="*", help="slugs to include (default: all)")
    parser.add_argument("--new", action="store_true", help="insert-only SQL for restaurants not yet in the database")
    args = parser.parse_args()

    problems, parts, summary = [], [], []
    with open(os.path.join(args.imports, "restaurants.csv"), newline="", encoding="utf-8") as f:
        restaurants = list(csv.DictReader(f))
    for r in restaurants:
        if args.only and r["slug"] not in args.only:
            continue
        path = os.path.join(args.imports, "menus", f"{r['slug']}.csv")
        if not os.path.exists(path):
            problems.append(f"{r['slug']}: no menu file at {path}")
            continue
        with open(path, newline="", encoding="utf-8") as f:
            dishes = list(csv.DictReader(f))
        # Dishes `allergy-tools review` held back: the restaurant's data contradicts the menu wording.
        held_path = os.path.join(args.imports, "held", f"{r['slug']}.csv")
        held = set()
        if os.path.exists(held_path):
            with open(held_path, newline="", encoding="utf-8") as f:
                held = {(h["category"], h["dish"]) for h in csv.DictReader(f)}
            before = len(dishes)
            dishes = [d for d in dishes if (d["category"], d["dish"]) not in held]
            summary.append(f"-- {r['slug']}: held back {before - len(dishes)} dishes listed in {held_path}")
        sql, n_dishes, n_links, live = restaurant_sql(r, dishes, problems, new_only=args.new)
        parts.append(sql)
        summary.append(f"-- {r['slug']}: {n_dishes} dishes, {n_links} allergen links, {'live' if live else 'hidden'}")

    if problems:
        print("Problems:", *problems, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    print("-- Generated by Tools/importers/build_import_sql.py from Imports/")
    print("\n".join(summary))
    print()
    print("\n\n".join(parts))


if __name__ == "__main__":
    main()
