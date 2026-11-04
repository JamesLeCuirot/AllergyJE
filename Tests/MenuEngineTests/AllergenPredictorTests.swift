import Testing
@testable import MenuEngine

private func assess(_ text: String) -> DishAssessment {
    AllergenPredictor.standard.assess(text)
}

private func likelihood(_ allergen: UKAllergen, in text: String) -> AllergenLikelihood? {
    assess(text).evidence.first { $0.allergen == allergen }?.likelihood
}

@Suite("Rules table")
struct RulesTableTests {
    @Test func parsesWithoutProblems() {
        let result = AllergenRules.parse(AllergenRules.source)
        #expect(result.problems.isEmpty, "\(result.problems.joined(separator: "\n"))")
        #expect(result.rules.count > 300)
    }

    @Test(arguments: UKAllergen.allCases)
    func everyAllergenHasADirectIngredient(_ allergen: UKAllergen) {
        #expect(AllergenRules.standard.contains { $0.effects[allergen] == .contains })
    }

    @Test func reportsMistakes() {
        let result = AllergenRules.parse("""
        pesto: nuts~
        pesto: milk~
        tofu: soya!
        broken line
        """)
        #expect(result.rules.map(\.term) == ["pesto"])
        #expect(result.problems.count == 3)
    }

    @Test func savedAllergenNamesStillConvert() {
        // These are the exact strings the onboarding screens save to UserDefaults.
        let saved = ["Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk", "Nuts",
                     "Celery", "Mustard", "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"]
        #expect(UKAllergen.set(from: saved) == Set(UKAllergen.allCases))
    }
}

@Suite("Predictions")
struct PredictionTests {
    @Test func classicDishImpliesItsIngredients() {
        #expect(likelihood(.nuts, in: "Pesto linguine") == .likely)
        #expect(likelihood(.milk, in: "Pesto linguine") == .likely)
        #expect(likelihood(.gluten, in: "Pesto linguine") == .contains)
    }

    @Test func matchesPluralsAccentsAndPunctuation() {
        #expect(likelihood(.crustaceans, in: "King Prawns") == .contains)
        #expect(likelihood(.fish, in: "Anchovies") == .contains)
        #expect(likelihood(.molluscs, in: "Moules Marinière") == .contains)
        #expect(likelihood(.eggs, in: "Crème Brûlée") == .contains)
        #expect(likelihood(.fish, in: "Salade Niçoise") == .likely)
        #expect(likelihood(.milk, in: "Shepherd’s pie") == .likely)
        #expect(likelihood(.fish, in: "Fish & Chips") == .contains)
        #expect(likelihood(.gluten, in: "Fish & Chips") == .likely)
        #expect(likelihood(.molluscs, in: "Salt & Pepper Squid") == .contains)
    }

    @Test func doesNotConfuseLookAlikeWords() {
        #expect(likelihood(.nuts, in: "Butternut squash soup with nutmeg and coconut") == nil)
        #expect(likelihood(.nuts, in: "Jam doughnut") == nil)
        #expect(likelihood(.gluten, in: "Jam doughnut") == .contains)
        #expect(likelihood(.milk, in: "Butter bean stew") == nil)
        #expect(likelihood(.eggs, in: "Roasted eggplant") == nil)
        #expect(likelihood(.fish, in: "Char-grilled steak") == nil)
    }

    @Test func longerTermsOverrideShorterOnes() {
        #expect(likelihood(.milk, in: "Grilled chicken with coconut milk and lime") == nil)
        #expect(likelihood(.peanuts, in: "Peanut butter cookie") == .contains)
        #expect(likelihood(.milk, in: "Peanut butter cookie") == .possible)
        #expect(likelihood(.nuts, in: "Almond milk latte") == .contains)
        #expect(likelihood(.soybeans, in: "Soya milk") == .contains)
        #expect(likelihood(.milk, in: "Soya milk") == nil)
    }

    @Test func freeFromClaimsOverrideEvidence() {
        let bread = assess("Gluten-free bread")
        #expect(bread.claimedFreeFrom == [.gluten])
        #expect(!bread.evidence.contains { $0.allergen == .gluten })
        #expect(bread.overriddenByClaims.map(\.allergen) == [.gluten])

        let brownie = assess("Chocolate brownie (GF)")
        #expect(brownie.claimedFreeFrom == [.gluten])
        #expect(!brownie.evidence.contains { $0.allergen == .gluten })
        #expect(brownie.evidence.contains { $0.allergen == .eggs })

        #expect(assess("Nut-free and dairy free").claimedFreeFrom == [.nuts, .milk])
        #expect(assess("Free from gluten and dairy").claimedFreeFrom == [.gluten, .milk])
        #expect(assess("Contains no nuts").claimedFreeFrom == [.nuts])
    }

    @Test func optionsAvailableDoNotChangeTheDishAsDescribed() {
        let salad = assess("Caesar salad – GF option available")
        #expect(salad.claimedFreeFrom.isEmpty)
        #expect(salad.freeFromOnRequest == [.gluten])
        #expect(salad.evidence.contains { $0.allergen == .gluten })

        #expect(assess("Beef burger (GFO)").freeFromOnRequest == [.gluten])
        #expect(assess("Beef burger (GFO)").evidence.contains { $0.allergen == .gluten })
    }

    @Test func cautiousAboutWeakClaims() {
        // Lactose-free milk is still milk; "free range" isn't a free-from claim.
        #expect(likelihood(.milk, in: "Lactose free milk") == .contains)
        #expect(likelihood(.eggs, in: "Free range eggs") == .contains)
        #expect(assess("Free range eggs").claimedFreeFrom.isEmpty)
    }

    @Test func veganClaimsStillFlagWhatVeganFoodCanContain() {
        let toastie = assess("Vegan cheese toastie")
        #expect(toastie.claimedFreeFrom.contains(.milk))
        #expect(!toastie.evidence.contains { $0.allergen == .milk })
        #expect(toastie.evidence.contains { $0.allergen == .nuts && $0.likelihood == .possible })
        #expect(toastie.evidence.contains { $0.allergen == .gluten && $0.likelihood == .contains })

        let wrap = assess("Falafel wrap (VG)")
        #expect(wrap.claimedFreeFrom.isSuperset(of: [.milk, .eggs]))
        #expect(wrap.evidence.contains { $0.allergen == .gluten })
    }

    @Test func readsMenuKeyCodes() {
        let tuna = assess("Sesame-crusted tuna (N)")
        #expect(tuna.evidence.contains { $0.allergen == .nuts && $0.likelihood == .contains })
        #expect(tuna.evidence.contains { $0.allergen == .sesame && $0.likelihood == .contains })
        #expect(tuna.evidence.contains { $0.allergen == .fish })
        // Brackets that aren't codes are read as ordinary text.
        #expect(assess("Steak (served with chips)").evidence.isEmpty)
    }

    @Test func noEvidenceForPlainDishes() {
        let plain = assess("Grilled chicken, rice and salad")
        #expect(plain.evidence.isEmpty)
        #expect(plain.recognisesFood)
        #expect(!assess("Welcome to the Old Court House").recognisesFood)
    }

    @Test func dishesFoundMissingOnASampleMenu() {
        #expect(likelihood(.milk, in: "Lemon posset, shortbread") == .contains)
        #expect(likelihood(.sulphites, in: "Sea bass, beurre blanc") == .likely)
        #expect(likelihood(.sesame, in: "Kale, beetroot, toasted seeds") == .possible)
        #expect(likelihood(.mustard, in: "Wholegrain mustard seeds") == .contains)
    }

    @Test func dishesTheAppDatabaseShowedWereMissing() {
        // Found by `allergy-tools score` against the restaurant data in Supabase.
        #expect(likelihood(.gluten, in: "Lobster thermidor") == .likely)
        #expect(likelihood(.gluten, in: "Passion fruit souffle") == .possible)
        #expect(likelihood(.gluten, in: "Classic prawn cocktail") == .possible)
        #expect(likelihood(.eggs, in: "Jersey beef burger") == .possible)
        #expect(likelihood(.milk, in: "Cauliflower puree") == .possible)
    }

    @Test func jerseySpecialities() {
        #expect(likelihood(.gluten, in: "Jersey Wonders") == .contains)
        #expect(likelihood(.molluscs, in: "Pan-fried ormers") == .contains)
        #expect(likelihood(.crustaceans, in: "Chancre crab salad") == .contains)
        #expect(assess("Jersey Royals").recognisesFood)
    }

    @Test func explainsItself() {
        let pesto = assess("Pesto").evidence.first { $0.allergen == .nuts }
        #expect(pesto?.summary == "Likely contains tree nuts (pesto)")
    }

    @Test func concernsFilterByAllergenAndStrength() {
        let curry = assess("Lamb curry")
        #expect(curry.concerns(for: [.milk]).map(\.allergen) == [.milk])
        #expect(curry.concerns(for: [.milk], minimum: .likely).isEmpty)
        #expect(curry.concerns(for: [.fish]).isEmpty)
    }
}
