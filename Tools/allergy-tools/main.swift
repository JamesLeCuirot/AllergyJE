import Foundation
import MenuEngine
import MenuEngineTraining

let usage = """
Usage: swift run allergy-tools <command> [options]

Commands:
  score    Score the predictor against dishes whose allergens are known.
             --data <folder or file>   CSV dataset (default: Data)
             --examples <n>            missed and false-alarm dishes to list per allergen (default: 5)
             --write-baseline          save today's misses as the baseline `swift test` checks against
  learn    Propose rules that catch dishes the hand-written rules miss.
             --data <folder or file>   CSV dataset (default: Data)
             --min-support <n>         dishes a term must appear in with the allergen (default: 3)
             --write                   regenerate AllergyJE/MenuScan/Engine/LearnedAllergenRules.swift
  check    Read the dataset and report any problems.
             --data <folder or file>   CSV dataset (default: Data)
  fetch-supabase
           Export every dish and its allergens from the app's Supabase database.
             --url <project url>       or set SUPABASE_URL
             --key <anon key>          or set SUPABASE_ANON_KEY (the public key the app uses)
             --out <file.csv>          (default: Data/allergy-je-database.csv)

Run from the repository root.
"""

let baselineURL = URL(fileURLWithPath: "Data/baseline.json")
let learnedRulesURL = URL(fileURLWithPath: "AllergyJE/MenuScan/Engine/LearnedAllergenRules.swift")

var arguments = Array(CommandLine.arguments.dropFirst())
guard let command = arguments.first else {
    print(usage)
    exit(0)
}
arguments.removeFirst()

@MainActor
func option(_ name: String) -> String? {
    guard let index = arguments.firstIndex(of: name), index + 1 < arguments.count else { return nil }
    return arguments[index + 1]
}

@MainActor
func flag(_ name: String) -> Bool {
    arguments.contains(name)
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("error: \(message)\n".utf8))
    exit(1)
}

@MainActor
func loadDataset() -> (dishes: [LabelledDish], description: String) {
    let path = option("--data") ?? "Data"
    do {
        let dishes = try DishDataset.load(URL(fileURLWithPath: path))
        if dishes.isEmpty { fail("no dishes found in \(path). Add CSV files with a header like: \(DishDataset.header.joined(separator: ","))") }
        return (dishes, "the dishes in \(path)")
    } catch {
        fail("\(error)")
    }
}

switch command {
case "score":
    let (dishes, _) = loadDataset()
    let scorecard = Scorecard.evaluate(dishes)
    print(scorecard.report(examples: Int(option("--examples") ?? "") ?? 5))

    if flag("--write-baseline") {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        do {
            try encoder.encode(scorecard.baseline).write(to: baselineURL)
            print("\nSaved the baseline to \(baselineURL.relativePath).")
        } catch {
            fail("couldn't write \(baselineURL.relativePath): \(error)")
        }
    } else if let data = try? Data(contentsOf: baselineURL), let baseline = try? JSONDecoder().decode(ScoreBaseline.self, from: data) {
        let regressions = scorecard.regressions(against: baseline)
        print(regressions.isEmpty
              ? "\nNo allergen misses more dishes than the baseline."
              : "\nMisses more than the baseline:\n" + regressions.map { "  \($0)" }.joined(separator: "\n"))
    }

case "learn":
    let (dishes, description) = loadDataset()
    let learner = RuleLearner(minimumSupport: Int(option("--min-support") ?? "") ?? 3)
    let proposals = learner.propose(from: dishes)

    if proposals.isEmpty {
        print("No new rules: nothing the hand-written rules miss is common enough in the data to learn from.")
    } else {
        print("Proposed rules (\(proposals.count)):\n")
        print(RuleLearner.rulesSource(for: proposals))
    }

    let disagreements = learner.disagreements(in: dishes)
    if !disagreements.isEmpty {
        print("\nRules the data disagrees with (not changed automatically; review by hand):")
        for disagreement in disagreements { print("  \(disagreement.summary)") }
    }

    if flag("--write") {
        let file = RuleLearner.learnedRulesFile(for: proposals, datasetDescription: description)
        let problems = AllergenRules.parse(RuleLearner.rulesSource(for: proposals)).problems
        guard problems.isEmpty else { fail("generated rules don't parse:\n" + problems.joined(separator: "\n")) }
        do {
            try file.write(to: learnedRulesURL, atomically: true, encoding: .utf8)
            print("\nWrote \(learnedRulesURL.relativePath). Review the diff, then run `swift run allergy-tools score`.")
        } catch {
            fail("couldn't write \(learnedRulesURL.relativePath): \(error)")
        }
    }

case "check":
    let (dishes, description) = loadDataset()
    let sources = Set(dishes.map(\.source)).count
    let restaurants = Set(dishes.map(\.restaurant)).count
    print("Read \(dishes.count) dishes from \(description): \(sources) sources, \(restaurants) restaurants.")
    for allergen in UKAllergen.allCases {
        let count = dishes.filter { $0.labels[allergen] == .contains }.count
        print("  \(allergen.rawValue.padding(toLength: 16, withPad: " ", startingAt: 0))\(count) dishes")
    }

case "fetch-supabase":
    let environment = ProcessInfo.processInfo.environment
    guard let base = option("--url") ?? environment["SUPABASE_URL"],
          let key = option("--key") ?? environment["SUPABASE_ANON_KEY"] else {
        fail("give the project URL and anon key with --url and --key, or SUPABASE_URL and SUPABASE_ANON_KEY")
    }
    let output = URL(fileURLWithPath: option("--out") ?? "Data/allergy-je-database.csv")
    do {
        let dishes = try await SupabaseExport.fetchDishes(projectURL: base, anonKey: key)
        try FileManager.default.createDirectory(at: output.deletingLastPathComponent(), withIntermediateDirectories: true)
        try DishDataset.csv(from: dishes).write(to: output, atomically: true, encoding: .utf8)
        print("Wrote \(dishes.count) dishes from \(Set(dishes.map(\.restaurant)).count) restaurants to \(output.relativePath).")
    } catch {
        fail("\(error)")
    }

case "help", "-h", "--help":
    print(usage)

default:
    fail("unknown command '\(command)'\n\n\(usage)")
}
