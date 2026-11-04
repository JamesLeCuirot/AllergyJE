# Allergy.je

An iOS app for eating out in Jersey with food allergies. You pick your allergens once. The app then:

- **Restaurant menus**: shows menus from restaurants in the Allergy.je database and dims the dishes that contain your allergens, based on the restaurant's own allergen data.
- **Scan any menu**: point the camera at a printed menu, or pick a photo of one. The app reads the text, predicts which allergens each dish is likely to contain, darkens everything else, and leaves the dishes that show no sign of your allergens bright.

Predictions come from the wording of the menu. They can say a dish probably contains something. They can never prove a dish is free of it, and the app says so throughout.

## Project layout

| Path | What it is |
| --- | --- |
| `AllergyJE/` | The SwiftUI app (iOS 26.2, Xcode 26). Open `AllergyJE.xcodeproj`. |
| `AllergyJE/MenuScan/` | Camera scanning (VisionKit DataScanner), photo OCR (Vision), the dimming overlay and the review screens. |
| `AllergyJE/MenuScan/Engine/` | Plain-Swift engine with no UIKit: groups OCR lines into dishes (`MenuLayout`) and predicts allergens (`AllergenPredictor`, `AllergenRules`). |
| `Tests/MenuEngineTests/` | Unit tests for the engine. |
| `Tools/` | `allergy-tools`: scores the predictor against real menus and learns new rules (see below). Not part of the app. |
| `Data/` | Dishes with known allergens, used for scoring and learning. |
| `Package.swift` | Builds the engine and tools, so tests run without Xcode. The app doesn't use it. |

## Running the tests

```bash
swift test
```

This works on a Mac with Xcode 26, or on Linux with Swift 6.2.

## How scanning works

1. **Read the text.** Live: VisionKit's `DataScannerViewController` returns text and its position on screen as the camera moves. Photo: Vision's `VNRecognizeTextRequest` reads a still image.
2. **Find the dishes.** `MenuLayout` joins lines that sit close together in the same column (name, description, price) into one block. When a block holds several prices, it splits it so each dish keeps one.
3. **Predict allergens.** `AllergenPredictor` matches the block's words against `AllergenRules.source`, a readable table of about 900 ingredients, dishes and cooking terms. Each entry is tagged *contains* (prawns → crustaceans), *likely* (pesto → nuts) or *possible* (curry → mustard). It also reads the menu's own claims: "gluten free", "(GF)", "(VG)", "(N)", and "GF option available", which doesn't change the dish as described.
4. **Draw the overlay.** Everything is darkened except dishes with no evidence for the user's allergens. Tap any dish to see why.

To teach it a new word, add a line to `AllergenRules.source` and a test.

## Teaching the predictor from real menus

Everything here is plain code that runs on your machine. There's no AI model or online service.

`Data/` holds dishes whose allergens are known, as CSV files with one row per dish and one column per allergen. Allergen cells are `Y` (contains), `M` (may contain) or blank. A restaurant's own allergen chart saved as CSV usually works as it is: common column names like "Soya", "Tree nuts" and "Sulphites" are recognised.

```bash
swift run allergy-tools fetch-supabase --url <project url> --key <anon key>
```
Exports every dish in the app's database to `Data/allergy-je-database.csv`.

```bash
swift run allergy-tools score
```
For each allergen, shows how many dishes that contain it the predictor misses (the number that matters: the app would show those dishes bright), and how many it flags wrongly. It lists examples of both.

```bash
swift run allergy-tools learn --write
```
Finds words that reliably go with an allergen in the dishes the rules miss, and writes them to `LearnedAllergenRules.swift` for you to review in the diff. Learned rules can only add or strengthen warnings, never remove one. It also lists hand-written rules that the data disagrees with.

```bash
swift run allergy-tools score --write-baseline
```
Saves the current misses to `Data/baseline.json`. `swift test` fails if a later change misses more, or if the data changes without a new baseline.

## Backend

Restaurant data lives in Supabase (`RestaurantStore.swift`) in these tables: `restaurants`, `menu_categories`, `menu_items`, `menu_item_allergens`, `allergens` and `menu_reports`. Subscriptions use RevenueCat (`SubscriptionManager.swift`) with the "AllergyJE Pro" entitlement.
