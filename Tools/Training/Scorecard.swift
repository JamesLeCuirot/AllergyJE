import Foundation
import MenuEngine

/// How the predictor did on one allergen.
public struct AllergenScore: Sendable {
    public let allergen: UKAllergen
    /// Dishes the restaurant says contain the allergen.
    public internal(set) var containing = 0
    /// Of those, dishes the predictor flagged.
    public internal(set) var caught = 0
    /// Dishes that contain the allergen but weren't flagged. The app would show these
    /// bright to someone with this allergy: the number that matters most.
    public internal(set) var missed: [LabelledDish] = []
    /// Dishes the restaurant says don't contain the allergen.
    public internal(set) var notContaining = 0
    /// Of those, dishes the predictor flagged anyway.
    public internal(set) var falseAlarms: [LabelledDish] = []
    /// "May contain" dishes, which count neither way.
    public internal(set) var mayContain = 0

    public var missRate: Double? {
        containing == 0 ? nil : Double(missed.count) / Double(containing)
    }

    public var falseAlarmRate: Double? {
        notContaining == 0 ? nil : Double(falseAlarms.count) / Double(notContaining)
    }
}

/// The misses per allergen at one point in time, saved so tests can stop changes that
/// make the predictor miss more.
public struct ScoreBaseline: Codable, Equatable, Sendable {
    public var dishes: Int
    /// Missed dishes per allergen, keyed by `UKAllergen.rawValue`.
    public var missed: [String: Int]
}

/// Scores the predictor against dishes whose allergens are known.
public struct Scorecard: Sendable {
    public let dishCount: Int
    public let sourceCount: Int
    public let scores: [AllergenScore]

    public static func evaluate(
        _ dishes: [LabelledDish],
        predictor: AllergenPredictor = .standard,
        minimum: AllergenLikelihood = .possible
    ) -> Scorecard {
        var scores = UKAllergen.allCases.map { AllergenScore(allergen: $0) }
        for dish in dishes {
            let flagged = Set(predictor.assess(dish.text).evidence.filter { $0.likelihood >= minimum }.map(\.allergen))
            for index in scores.indices {
                let allergen = scores[index].allergen
                switch dish.labels[allergen] {
                case .contains:
                    scores[index].containing += 1
                    if flagged.contains(allergen) {
                        scores[index].caught += 1
                    } else {
                        scores[index].missed.append(dish)
                    }
                case .mayContain:
                    scores[index].mayContain += 1
                case nil:
                    scores[index].notContaining += 1
                    if flagged.contains(allergen) { scores[index].falseAlarms.append(dish) }
                }
            }
        }
        return Scorecard(dishCount: dishes.count, sourceCount: Set(dishes.map(\.source)).count, scores: scores)
    }

    public var baseline: ScoreBaseline {
        ScoreBaseline(dishes: dishCount, missed: Dictionary(uniqueKeysWithValues: scores.map { ($0.allergen.rawValue, $0.missed.count) }))
    }

    /// Allergens that miss more dishes than the baseline did, e.g. "Gluten: 3 missed, baseline 2".
    public func regressions(against baseline: ScoreBaseline) -> [String] {
        scores.compactMap { score in
            let before = baseline.missed[score.allergen.rawValue] ?? 0
            return score.missed.count > before ? "\(score.allergen.rawValue): \(score.missed.count) missed, baseline \(before)" : nil
        }
    }

    /// A plain-text report for the terminal.
    public func report(examples: Int = 5) -> String {
        var lines = ["Scorecard: \(dishCount) dishes from \(sourceCount) source\(sourceCount == 1 ? "" : "s")", ""]
        lines.append(row("Allergen", "Dishes", "Caught", "Missed", "Miss rate", "False alarms"))
        for score in scores {
            let falseAlarms = score.notContaining == 0
                ? "–"
                : "\(score.falseAlarms.count) of \(score.notContaining) (\(percent(score.falseAlarmRate)))"
            lines.append(row(score.allergen.rawValue, "\(score.containing)", "\(score.caught)", "\(score.missed.count)", percent(score.missRate), falseAlarms))
        }

        let totalContaining = scores.map(\.containing).reduce(0, +)
        let totalMissed = scores.map(\.missed.count).reduce(0, +)
        lines.append("")
        lines.append("Overall: \(totalMissed) of \(totalContaining) allergen-containing dish entries missed (\(percent(totalContaining == 0 ? nil : Double(totalMissed) / Double(totalContaining)))).")

        if examples > 0 {
            let missed = scores.filter { !$0.missed.isEmpty }
            if !missed.isEmpty {
                lines.append("")
                lines.append("Missed (shown bright to someone with that allergy):")
                for score in missed {
                    lines.append("  \(score.allergen.rawValue):")
                    for dish in score.missed.prefix(examples) { lines.append("    - \(describe(dish))") }
                    if score.missed.count > examples { lines.append("    … and \(score.missed.count - examples) more") }
                }
            }
            let alarms = scores.filter { !$0.falseAlarms.isEmpty }
            if !alarms.isEmpty {
                lines.append("")
                lines.append("False alarms (dimmed although the restaurant says they're fine):")
                for score in alarms {
                    lines.append("  \(score.allergen.rawValue):")
                    for dish in score.falseAlarms.prefix(examples) { lines.append("    - \(describe(dish))") }
                    if score.falseAlarms.count > examples { lines.append("    … and \(score.falseAlarms.count - examples) more") }
                }
            }
        }
        return lines.joined(separator: "\n")
    }

    private func describe(_ dish: LabelledDish) -> String {
        let place = dish.restaurant.isEmpty ? "" : " — \(dish.restaurant)"
        return "\(dish.text)\(place)"
    }

    private func row(_ cells: String...) -> String {
        let widths = [16, 7, 7, 7, 10, 0]
        return zip(cells, widths).map { cell, width in
            width == 0 ? cell : cell.padding(toLength: max(width, cell.count + 1), withPad: " ", startingAt: 0)
        }.joined()
    }

    private func percent(_ value: Double?) -> String {
        guard let value else { return "–" }
        return "\(Int((value * 100).rounded()))%"
    }
}
