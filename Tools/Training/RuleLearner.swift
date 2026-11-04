import Foundation
import MenuEngine

/// A new rule the data supports: menus that mention `term` usually contain `allergen`.
public struct RuleProposal: Equatable, Sendable {
    public let term: String
    public let allergen: UKAllergen
    public let likelihood: AllergenLikelihood
    /// Dishes mentioning the term that contain the allergen.
    public let containing: Int
    /// Dishes mentioning the term that don't (ignoring "may contain").
    public let notContaining: Int
    /// Missed dishes this rule would catch.
    public let fixes: Int

    public var evidence: String {
        "\(containing) of \(containing + notContaining) dishes mentioning \"\(term)\" contain \(allergen.phrase); catches \(fixes) missed"
    }
}

/// An existing rule that real menus disagree with, for a person to look at.
public struct RuleDisagreement: Equatable, Sendable {
    public let term: String
    public let allergen: UKAllergen
    public let likelihood: AllergenLikelihood
    public let flagged: Int
    public let actuallyContain: Int

    public var summary: String {
        "\"\(term)\" → \(allergen.phrase) (\(likelihood.label.lowercased())): only \(actuallyContain) of \(flagged) dishes it flagged contain it"
    }
}

/// Learns allergen rules from dishes whose allergens are known.
///
/// For each allergen, it takes the dishes the current rules miss and finds the words or
/// short phrases (up to `maxWords`) that most reliably go with that allergen across the whole
/// dataset. It then picks the fewest of them that catch the most misses. Reliability is the
/// Wilson lower bound of the share of dishes with the term that contain the allergen,
/// so a handful of examples isn't enough to claim "contains".
public struct RuleLearner: Sendable {
    /// Dishes that must mention the term and contain the allergen before it's proposed.
    public var minimumSupport: Int
    /// Different restaurants those dishes must come from, so one kitchen's house recipes
    /// (or its name, or a typo on its menu) don't become rules for every menu.
    public var minimumRestaurants: Int
    public var maxWords: Int

    public init(minimumSupport: Int = 3, minimumRestaurants: Int = 2, maxWords: Int = 3) {
        self.minimumSupport = minimumSupport
        self.minimumRestaurants = minimumRestaurants
        self.maxWords = maxWords
    }

    /// Lower bounds for each likelihood. A rule needs at least `possible` to be proposed.
    static let thresholds: [(AllergenLikelihood, Double)] = [(.contains, 0.8), (.likely, 0.45), (.possible, 0.2)]

    /// Words that don't say anything about ingredients on their own.
    static let stopwords: Set<String> = [
        "a", "an", "and", "or", "of", "the", "with", "in", "on", "our", "your", "to", "for", "from", "by", "as", "at",
        "served", "serve", "fresh", "side", "sides", "choice", "house", "homemade", "home", "made", "style", "day",
        "topped", "finished", "selection", "add", "extra", "large", "small", "regular", "per", "each", "plus", "local",
        "free", "vegan", "vegetarian", "gf", "df", "vg", "ve", "v", "contains", "contain", "may", "option", "available",
    ]

    public func propose(from dishes: [LabelledDish], predictor: AllergenPredictor = AllergenPredictor(rules: AllergenRules.handWritten)) -> [RuleProposal] {
        let grams = dishes.map { phrases(in: MenuText.tokens($0.text)) }
        let flagged = dishes.map { Set(predictor.assess($0.text).evidence.map(\.allergen)) }

        var proposals: [RuleProposal] = []
        for allergen in UKAllergen.allCases {
            var containing: [String: Int] = [:]
            var notContaining: [String: Int] = [:]
            var restaurants: [String: Set<String>] = [:]
            for (index, dish) in dishes.enumerated() {
                switch dish.labels[allergen] {
                case .contains:
                    for gram in grams[index] {
                        containing[gram, default: 0] += 1
                        restaurants[gram, default: []].insert(dish.restaurant)
                    }
                case nil: for gram in grams[index] { notContaining[gram, default: 0] += 1 }
                case .mayContain: break
                }
            }

            var missed = dishes.indices.filter { dishes[$0].labels[allergen] == .contains && !flagged[$0].contains(allergen) }
            while !missed.isEmpty {
                var best: (gram: String, bound: Double, fixes: Int)?
                for gram in Set(missed.flatMap { grams[$0] }).sorted() {
                    let yes = containing[gram] ?? 0
                    guard yes >= minimumSupport, (restaurants[gram]?.count ?? 0) >= minimumRestaurants else { continue }
                    let bound = Self.wilsonLowerBound(yes, of: yes + (notContaining[gram] ?? 0))
                    guard bound >= Self.thresholds.last!.1 else { continue }
                    let fixes = missed.filter { grams[$0].contains(gram) }.count
                    if let current = best, (current.fixes, current.bound, -wordCount(current.gram)) >= (fixes, bound, -wordCount(gram)) { continue }
                    best = (gram, bound, fixes)
                }
                guard let best else { break }
                let likelihood = Self.thresholds.first { best.bound >= $0.1 }!.0
                proposals.append(RuleProposal(
                    term: best.gram,
                    allergen: allergen,
                    likelihood: likelihood,
                    containing: containing[best.gram] ?? 0,
                    notContaining: notContaining[best.gram] ?? 0,
                    fixes: best.fixes
                ))
                missed.removeAll { grams[$0].contains(best.gram) }
            }
        }
        return proposals
    }

    /// Rules whose strongest claims the data contradicts: they said "contains" or "likely"
    /// for dishes that mostly turned out not to.
    public func disagreements(in dishes: [LabelledDish], rules: [AllergenRule] = AllergenRules.standard) -> [RuleDisagreement] {
        let predictor = AllergenPredictor(rules: rules)
        let rulesByTerm = Dictionary(rules.map { ($0.term, $0) }, uniquingKeysWith: { first, _ in first })
        var counts: [String: (flagged: Int, actual: Int)] = [:]
        func key(_ term: String, _ allergen: UKAllergen) -> String { "\(term)\u{1F}\(allergen.rawValue)" }

        for dish in dishes {
            for evidence in predictor.assess(dish.text).evidence {
                for term in evidence.terms {
                    guard let likelihood = rulesByTerm[term]?.effects[evidence.allergen], likelihood >= .likely else { continue }
                    var count = counts[key(term, evidence.allergen), default: (0, 0)]
                    count.flagged += 1
                    if dish.labels[evidence.allergen] != nil { count.actual += 1 }
                    counts[key(term, evidence.allergen)] = count
                }
            }
        }

        return counts.compactMap { key, count -> RuleDisagreement? in
            let parts = key.split(separator: "\u{1F}").map(String.init)
            guard parts.count == 2, let allergen = UKAllergen(rawValue: parts[1]),
                  let likelihood = rulesByTerm[parts[0]]?.effects[allergen],
                  count.flagged >= minimumSupport else { return nil }
            // Upper bound below the claim: even optimistically, the term rarely means the allergen.
            let upper = 1 - Self.wilsonLowerBound(count.flagged - count.actual, of: count.flagged)
            let needed = likelihood == .contains ? 0.8 : 0.45
            guard upper < needed else { return nil }
            return RuleDisagreement(term: parts[0], allergen: allergen, likelihood: likelihood, flagged: count.flagged, actuallyContain: count.actual)
        }
        .sorted { ($0.flagged - $0.actuallyContain, $0.term) > ($1.flagged - $1.actuallyContain, $1.term) }
    }

    /// The body of `LearnedAllergenRules.source` for these proposals.
    public static func rulesSource(for proposals: [RuleProposal]) -> String {
        var byTerm: [String: [RuleProposal]] = [:]
        for proposal in proposals { byTerm[proposal.term, default: []].append(proposal) }
        var lines: [String] = []
        for term in byTerm.keys.sorted() {
            let group = byTerm[term]!.sorted { $0.allergen < $1.allergen }
            for proposal in group { lines.append("# \(proposal.evidence)") }
            let effects = group.map { "\($0.allergen.ruleKey)\(marker($0.likelihood))" }.joined(separator: ", ")
            lines.append("\(term): \(effects)")
        }
        return lines.joined(separator: "\n")
    }

    /// The whole generated Swift file.
    public static func learnedRulesFile(for proposals: [RuleProposal], datasetDescription: String) -> String {
        let rules = rulesSource(for: proposals)
        let body = rules.isEmpty ? "" : rules
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map { "    \($0)" }
            .joined(separator: "\n")
        return """
        // Generated by `swift run allergy-tools learn --write` from \(datasetDescription).
        // Don't edit by hand: change the data or AllergenRules.source, then regenerate.
        // AllergenRules.merge adds these to the hand-written rules. They can only add or
        // strengthen warnings, never remove one.

        public nonisolated enum LearnedAllergenRules {
            public static let source = \"\"\"
        \(body.isEmpty ? "" : body + "\n")    \"\"\"
        }

        """
    }

    /// Lower end of the 95% Wilson score interval for `successes` out of `total`.
    public static func wilsonLowerBound(_ successes: Int, of total: Int) -> Double {
        guard total > 0 else { return 0 }
        let z = 1.96
        let n = Double(total)
        let p = Double(successes) / n
        let centre = p + z * z / (2 * n)
        let margin = z * ((p * (1 - p) + z * z / (4 * n)) / n).squareRoot()
        return max(0, (centre - margin) / (1 + z * z / n))
    }

    private static func marker(_ likelihood: AllergenLikelihood) -> String {
        switch likelihood {
        case .contains: "!"
        case .likely: "~"
        case .possible: "?"
        }
    }

    /// Every phrase of 1…maxWords tokens that starts and ends with a meaningful word.
    func phrases(in tokens: [String]) -> Set<String> {
        var result = Set<String>()
        for start in tokens.indices {
            for length in 1...maxWords where start + length <= tokens.count {
                let words = tokens[start..<start + length]
                guard let first = words.first, let last = words.last,
                      useful(first), useful(last),
                      words.allSatisfy({ !$0.allSatisfy(\.isNumber) }) else { continue }
                result.insert(words.joined(separator: " "))
            }
        }
        return result
    }

    private func useful(_ word: String) -> Bool {
        word.count >= 3 && !Self.stopwords.contains(word) && !word.allSatisfy(\.isNumber)
    }

    private func wordCount(_ gram: String) -> Int {
        gram.split(separator: " ").count
    }
}
