#!/usr/bin/env python3
"""Read a JPRestaurants-style menu page (Beresford House, Oyster Box, Jersey Crab Shack)
into a menu details CSV: category, dish, description, price, flags.

These sites share one template: sections with `venue-menu-section__title`, and items
with `menu-item-row__name`, `__price`, `__desc` and badge flags (V, VV, DF, NGCI…).

Usage:
  python3 Tools/importers/jprestaurants_menu.py page.html [more.html …] --out details.csv
"""
import argparse
import csv
import re

from bs4 import BeautifulSoup


def price(text):
    """'12.5' → '12.5'. Anything with several prices ('9 / 17 / 24', '3.5 per scoop') → ''."""
    text = text.strip().lstrip("£")
    return text if re.fullmatch(r"\d{1,3}(\.\d{1,2})?", text) else ""


def items(html):
    soup = BeautifulSoup(html, "html.parser")
    for section in soup.select(".venue-menu-section"):
        title = section.select_one(".venue-menu-section__title")
        category = " ".join(title.get_text(" ").split()) if title else ""
        for row in section.select(".menu-item-row"):
            name = row.select_one(".menu-item-row__name")
            if not name:
                continue
            cost = row.select_one(".menu-item-row__price")
            desc = row.select_one(".menu-item-row__desc")
            flags = [b.get_text(strip=True) for b in row.select(".menu-item-row__flags .badge")]
            yield {
                "category": category,
                "dish": " ".join(name.get_text(" ").split()),
                "description": " ".join(desc.get_text(" ").split()) if desc else "",
                "price": price(cost.get_text()) if cost else "",
                "price_text": " ".join(cost.get_text(" ").split()) if cost else "",
                "flags": " ".join(flags),
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("html", nargs="+")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = []
    for path in args.html:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows.extend(items(f.read()))
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "dish", "description", "price", "price_text", "flags"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} dishes written to {args.out}")


if __name__ == "__main__":
    main()
