# Putting Allergy.je on TestFlight

You need a Mac with Xcode 26 and a phone on iOS 26.2 or later (the app's deployment
target). Sign in to Xcode with the Apple account that has the App Store Connect app
(Xcode › Settings › Accounts).

## 1. Get the code

```bash
git clone https://github.com/JamesLeCuirot/AllergyJE.git
cd AllergyJE
git checkout claude/stoic-ritchie-4wuizm
```

(Or, in an existing clone: `git fetch origin claude/stoic-ritchie-4wuizm` and then
`git checkout claude/stoic-ritchie-4wuizm`.)

## 2. Signing

Open `AllergyJE.xcodeproj`. Supabase is the only package; Xcode fetches it.

In the AllergyJE target › Signing & Capabilities:

- Tick **Automatically manage signing** and pick your **Team**. The project doesn't set one yet.
- **Bundle Identifier** must match the app record in App Store Connect
  (App Store Connect › your app › App Information › Bundle ID). The project uses
  `JamesLeCuirot.AllergyJE`; if the record uses something else, change it here.

## 3. Try it on your phone first

Connect the iPhone, turn on Developer Mode if asked (Settings › Privacy & Security), pick it
as the run destination and press Run. Then work through the demo below.

## 4. Upload a build

Version is 1.1. Each upload needs a new build number: target › General › Build (1, 2, 3 …).

In Xcode: pick **Any iOS Device (arm64)**, then Product › Archive. When the Organizer opens,
choose Distribute App › App Store Connect › Upload.

From the terminal instead (uses the account signed in to Xcode):

```bash
xcodebuild -project AllergyJE.xcodeproj -scheme AllergyJE -destination 'generic/platform=iOS' -archivePath build/AllergyJE.xcarchive archive -allowProvisioningUpdates
```

```bash
xcodebuild -exportArchive -archivePath build/AllergyJE.xcarchive -exportOptionsPlist docs/ExportOptions.plist -exportPath build/export -allowProvisioningUpdates
```

`ITSAppUsesNonExemptEncryption` is set to NO (the app only uses HTTPS), so App Store Connect
won't ask the encryption question for each build.

## 5. TestFlight

The build appears in App Store Connect › TestFlight after processing (usually 10–30 minutes).

- **You and your team (internal testers):** add yourself to an internal group and install
  through the TestFlight app. No review needed.
- **Charities and the public (external testers):**
  1. Create an external group.
  2. Fill in Test Information: what to test, a beta description, a feedback email,
     and a contact.
  3. Submit the build for Beta App Review. The first review usually takes a day or two.
  4. Once it's approved, turn on the group's **public link** and share it. Anyone with the
     link can install the app, up to 10,000 testers.

Testers can send feedback and screenshots from the TestFlight app; it shows up under
TestFlight › Feedback.

## Demo walkthrough

1. **Onboarding:** pick a couple of allergies, e.g. Milk and Gluten.
2. **A restaurant with its own allergen information:** Home › find a restaurant ›
   The Moorings or Beresford House.
   - The green banner names the restaurant's allergen document and its date, with a link.
   - Tap **Show me what I can eat**: dishes with your allergens dim; the rest show a green tick.
   - "May contain" allergens are labelled as such and dim too.
3. **A menu-only restaurant:** e.g. Oyster Box.
   - The orange banner says the allergens are estimates from the menu wording.
   - **Dim likely allergens** dims dishes whose wording suggests your allergens. The others
     get an orange question mark, never a tick.
   - The ⓘ on a dish explains which words triggered each estimate.
4. **Scan:** the Scan tab reads a printed menu with the camera and greys out dishes whose
   wording suggests your allergens.
5. **Report:** the flag on any dish sends a correction to the `menu_reports` table.

## What the app tells people

- Allergens shown for a restaurant either come from that restaurant's published
  information (with the source and date shown), or are estimates, labelled as estimates.
- Estimates come from rules in code (`AllergyJE/MenuScan/Engine`), not from an AI model. They
  are weakest for celery, mustard, sesame, soya and sulphites, which recipes hide.
- Every screen tells people to confirm with staff.
