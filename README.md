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
| `Package.swift` | Builds only the engine, so its tests run without Xcode. The app doesn't use it. |

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

## Backend

Restaurant data lives in Supabase (`RestaurantStore.swift`) in these tables: `restaurants`, `menu_categories`, `menu_items`, `menu_item_allergens`, `allergens` and `menu_reports`. Subscriptions use RevenueCat (`SubscriptionManager.swift`) with the "AllergyJE Pro" entitlement.
