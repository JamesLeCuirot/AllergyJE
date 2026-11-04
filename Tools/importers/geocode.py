#!/usr/bin/env python3
"""Fill in missing latitude/longitude in Imports/restaurants.csv from OpenStreetMap.

Looks up "<name>, <address>", then the address alone, with Nominatim. Waits a second
between requests, as its usage policy asks. Rows that already have coordinates are left
alone. Check anything surprising: the result is printed for every row it fills.

Usage:
  python3 Tools/importers/geocode.py [Imports/restaurants.csv]
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request

USER_AGENT = "AllergyJE-restaurant-import/1.0"


def lookup(query):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "je"})
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        results = json.load(response)
    time.sleep(1.1)
    return results[0] if results else None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "Imports/restaurants.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["latitude"].strip() and row["longitude"].strip():
            continue
        found = lookup(f"{row['name']}, {row['address']}") or lookup(row["address"])
        if found:
            row["latitude"], row["longitude"] = found["lat"], found["lon"]
            print(f"{row['slug']}: {found['lat']}, {found['lon']}  ({found['display_name'][:90]})")
        else:
            print(f"{row['slug']}: not found")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
