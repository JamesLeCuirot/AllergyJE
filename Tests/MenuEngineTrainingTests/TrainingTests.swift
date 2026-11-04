import Foundation
import Testing
@testable import MenuEngine
@testable import MenuEngineTraining

/// Made-up ingredient names, so these tests don't depend on (or claim) real recipes.
private func dish(_ name: String, _ description: String = "", _ allergens: UKAllergen..., mayContain: [UKAllergen] = [], restaurant: String = "Test Kitchen") -> LabelledDish {
    var labels: [UKAllergen: AllergenLabel] = [:]
    for allergen in allergens { labels[allergen] = .contains }
    for allergen in mayContain { labels[allergen] = .mayContain }
    return LabelledDish(source: "test", restaurant: restaurant, dish: name, description: description, labels: labels)
}

@Suite("Dataset CSV")
struct DatasetTests {
    @Test func roundTrips() throws {
        let dishes = [
            dish("Fish Pie", "Cod, prawns, \"creamy\" mash", .fish, .crustaceans, .milk, mayContain: [.mustard]),
            dish("Green salad"),
        ]
        let csv = DishDataset.csv(from: dishes)
        #expect(try DishDataset.read(csv: csv) == dishes)
    }

    @Test func readsRestaurantAllergenChartsLoosely() throws {
        let csv = """
        \u{FEFF}Dish Name,Description,Cereals containing gluten,Soya,Tree Nuts,Sulphites,Milk
        Pesto pasta,"Basil, pine nuts, parmesan",✓,,✓,,yes
        Lemon sorbet,,,,,May contain,
        """
        let dishes = try DishDataset.read(csv: csv)
        #expect(dishes.count == 2)
        #expect(dishes[0].labels == [.gluten: .contains, .nuts: .contains, .milk: .contains])
        #expect(dishes[0].description == "Basil, pine nuts, parmesan")
        #expect(dishes[1].labels == [.sulphites: .mayContain])
    }

    @Test func readsExtraColumnsRowByRow() throws {
        let csv = """
        category,dish,description,price,Gluten
        Starters,Soup,,6,Y
        Starters,,,,
        Mains,Pie,,14,Y
        """
        #expect(DishDataset.column("category", in: csv) == ["Starters", "Mains"])
        #expect(try DishDataset.read(csv: csv).map { $0.dish } == ["Soup", "Pie"])
    }

    @Test func reportsCellsItCantRead() {
        let csv = """
        dish,Gluten
        Toast,perhaps
        """
        #expect(throws: DishDataset.ReadError(line: 2, message: "can't read 'perhaps' for Gluten; use Y, M or leave blank")) {
            try DishDataset.read(csv: csv)
        }
    }
}

@Suite("Scorecard")
struct ScorecardTests {
    @Test func countsCatchesMissesAndFalseAlarms() {
        let scorecard = Scorecard.evaluate([
            dish("Prawn cocktail", "", .crustaceans, .eggs),   // both caught
            dish("Blorvak stew", "", .mustard),                // mustard missed
            dish("Chicken salad", "", mayContain: [.mustard]),  // may contain: ignored
            dish("Grilled pesto chicken", ""),                 // nuts and milk false alarms
        ])
        let mustard = scorecard.scores.first { $0.allergen == .mustard }!
        #expect(mustard.containing == 1)
        #expect(mustard.missed.map(\.dish) == ["Blorvak stew"])
        #expect(mustard.mayContain == 1)

        let crustaceans = scorecard.scores.first { $0.allergen == .crustaceans }!
        #expect(crustaceans.caught == 1 && crustaceans.missed.isEmpty)

        let nuts = scorecard.scores.first { $0.allergen == .nuts }!
        #expect(nuts.falseAlarms.map(\.dish) == ["Grilled pesto chicken"])

        #expect(scorecard.report().contains("Blorvak stew"))
    }

    @Test func flagsRegressionsAgainstTheBaseline() {
        let scorecard = Scorecard.evaluate([dish("Blorvak stew", "", .mustard)])
        #expect(scorecard.regressions(against: ScoreBaseline(dishes: 1, missed: ["Mustard": 0])) == ["Mustard: 1 missed, baseline 0"])
        #expect(scorecard.regressions(against: scorecard.baseline).isEmpty)
    }
}

@Suite("Rule learner")
struct RuleLearnerTests {
    private let menus: [LabelledDish] = (1...6).map { dish("Blorvak sauce \($0)", "with grilled chicken", .mustard, restaurant: "Kitchen \($0 % 2)") }
        + (1...6).map { dish("Tomato sauce \($0)", "with grilled chicken", restaurant: "Kitchen \($0 % 2)") }

    @Test func proposesTheWordThatExplainsTheMisses() {
        let proposals = RuleLearner().propose(from: menus)
        #expect(proposals.count == 1)
        #expect(proposals.first?.term == "blorvak")
        #expect(proposals.first?.allergen == .mustard)
        #expect(proposals.first?.likelihood == .likely) // 6 of 6 isn't yet enough for "contains"
        #expect(proposals.first?.fixes == 6)
    }

    @Test func needsEnoughExamples() {
        #expect(RuleLearner(minimumSupport: 7).propose(from: menus).isEmpty)
    }

    @Test func ignoresOneKitchensHouseRecipes() {
        // Six dishes, all from one restaurant: its house style, not a rule for every menu.
        let oneKitchen = (1...6).map { dish("Blorvak sauce \($0)", "", .mustard, restaurant: "Only Kitchen") }
        #expect(RuleLearner().propose(from: oneKitchen).isEmpty)
        #expect(RuleLearner(minimumRestaurants: 1).propose(from: oneKitchen).map(\.term) == ["blorvak"])
    }

    @Test func learnedRulesParseAndCatchTheMisses() {
        let source = RuleLearner.rulesSource(for: RuleLearner().propose(from: menus))
        let parsed = AllergenRules.parse(source)
        #expect(parsed.problems.isEmpty)

        let predictor = AllergenPredictor(rules: AllergenRules.merge(AllergenRules.handWritten, learned: parsed.rules))
        let after = Scorecard.evaluate(menus, predictor: predictor).scores.first { $0.allergen == .mustard }!
        #expect(after.missed.isEmpty)
    }

    @Test func generatedFileHasTheSameRules() {
        let proposals = RuleLearner().propose(from: menus)
        let file = RuleLearner.learnedRulesFile(for: proposals, datasetDescription: "test dishes")
        #expect(file.contains("public static let source = \"\"\"\n    # 6 of 6 dishes mentioning \"blorvak\""))
        #expect(file.contains("    blorvak: mustard~\n    \"\"\""))
        #expect(RuleLearner.learnedRulesFile(for: [], datasetDescription: "x").contains("source = \"\"\"\n    \"\"\""))
    }

    @Test func mergingOnlyEverAddsWarnings() {
        let learned = AllergenRules.parse("""
        beef wellington: sesame?
        chicken: sulphites?
        pesto: nuts?
        """).rules
        let predictor = AllergenPredictor(rules: AllergenRules.merge(AllergenRules.handWritten, learned: learned))

        let wellington = predictor.assess("Beef wellington").evidence
        #expect(wellington.contains { $0.allergen == .gluten && $0.likelihood == .contains }) // kept from "wellington"
        #expect(wellington.contains { $0.allergen == .sesame })                              // added

        #expect(predictor.assess("Roast chicken").evidence.map(\.allergen) == [.sulphites])
        // "pesto" was already likely nuts; a weaker learned claim doesn't lower it.
        #expect(predictor.assess("Pesto").evidence.first { $0.allergen == .nuts }?.likelihood == .likely)
    }

    @Test func reportsRulesTheDataContradicts() {
        let rules = AllergenRules.parse("zorp: milk!").rules
        let dishes = (1...10).map { dish("Zorp \($0)", "", $0 == 1 ? .milk : .celery) }
        let disagreements = RuleLearner().disagreements(in: dishes, rules: rules)
        #expect(disagreements.map(\.term) == ["zorp"])
        #expect(disagreements.first?.actuallyContain == 1)
    }

    @Test func wilsonBound() {
        #expect(abs(RuleLearner.wilsonLowerBound(6, of: 6) - 0.61) < 0.01)
        #expect(abs(RuleLearner.wilsonLowerBound(20, of: 20) - 0.84) < 0.01)
        #expect(RuleLearner.wilsonLowerBound(0, of: 0) == 0)
    }
}

@Suite("Supabase export")
struct SupabaseExportTests {
    @Test func readsContainsAndMayContain() throws {
        let json = Data("""
        [{"name":"House sourdough","description":"Olive oil","restaurants":{"name":"Beresford House"},
          "menu_item_allergens":[{"level":"contains","allergens":{"name":"Gluten"}},
                                 {"level":"may_contain","allergens":{"name":"Soybeans"}},
                                 {"allergens":{"name":"Sulphur Dioxide"}}]}]
        """.utf8)
        let dishes = try SupabaseExport.dishes(fromJSON: json)
        #expect(dishes.first?.labels == [.gluten: .contains, .soybeans: .mayContain, .sulphites: .contains])
        #expect(dishes.first?.restaurant == "Beresford House")
    }

    @Test func rejectsAllergenNamesItDoesntKnow() {
        let json = Data(#"[{"name":"Toast","description":null,"restaurants":{"name":"X"},"menu_item_allergens":[{"allergens":{"name":"Gluten-ish"}}]}]"#.utf8)
        #expect(throws: SupabaseExport.ExportError.self) { try SupabaseExport.dishes(fromJSON: json) }
    }
}

@Suite("Real menu data")
struct RealDataTests {
    private static let root = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    @Test func committedDatasetReads() throws {
        _ = try DishDataset.load(Self.root.appendingPathComponent("Data"))
    }

    @Test func learnedRulesParse() {
        #expect(AllergenRules.parse(LearnedAllergenRules.source).problems.isEmpty)
    }

    /// Stops a rule change from making the app miss allergens it used to catch.
    @Test func noAllergenMissesMoreThanTheBaseline() throws {
        let dishes = try DishDataset.load(Self.root.appendingPathComponent("Data"))
        guard !dishes.isEmpty else { return }
        let baselineData = try Data(contentsOf: Self.root.appendingPathComponent("Data/baseline.json"))
        let baseline = try JSONDecoder().decode(ScoreBaseline.self, from: baselineData)
        let scorecard = Scorecard.evaluate(dishes)
        #expect(baseline.dishes == dishes.count, "The dataset changed since the baseline. Run `swift run allergy-tools score --write-baseline`.")
        #expect(scorecard.regressions(against: baseline).isEmpty, "\(scorecard.regressions(against: baseline).joined(separator: "; "))")
    }
}
