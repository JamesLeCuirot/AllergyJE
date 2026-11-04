import Foundation

/// One allergen the predictor thinks a dish may contain, and why.
nonisolated struct AllergenEvidence: Hashable, Sendable {
    let allergen: UKAllergen
    /// The strongest likelihood among `terms`.
    let likelihood: AllergenLikelihood
    /// Menu terms that point to this allergen, strongest first ("pesto", "parmesan").
    let terms: [String]

    /// "Likely contains tree nuts (pesto)"
    var summary: String {
        "\(likelihood.label) \(allergen.phrase) (\(terms.joined(separator: ", ")))"
    }
}

/// What the predictor read from one dish's text.
nonisolated struct DishAssessment: Hashable, Sendable {
    /// Allergens the dish may contain, strongest first, after the menu's own
    /// free-from claims have been applied.
    let evidence: [AllergenEvidence]
    /// Evidence set aside because the menu says the dish is free from that allergen
    /// ("gluten-free bread"). Shown to the user so they can judge the claim.
    let overriddenByClaims: [AllergenEvidence]
    /// Allergens the menu says this dish is free from: "GF", "dairy free", "vegan".
    let claimedFreeFrom: Set<UKAllergen>
    /// Free-from versions the menu says can be requested ("GF option available").
    /// These don't change the prediction, because the dish as described still contains them.
    let freeFromOnRequest: Set<UKAllergen>
    /// True when the text contains at least one food word the rules know.
    let recognisesFood: Bool

    /// Evidence for the given allergens at or above `minimum`.
    func concerns(for allergens: Set<UKAllergen>, minimum: AllergenLikelihood = .possible) -> [AllergenEvidence] {
        evidence.filter { allergens.contains($0.allergen) && $0.likelihood >= minimum }
    }
}

/// Predicts which of the 14 allergens a dish is likely to contain from its menu text.
///
/// This is a rules-based first version: it knows which ingredients and classic dishes
/// carry which allergens. It can say a dish probably *contains* something; it can never
/// prove a dish is *free* of something. Text it doesn't recognise produces no evidence,
/// so "no evidence" means "ask the staff", not "safe".
nonisolated struct AllergenPredictor: Sendable {
    static let standard = AllergenPredictor(rules: AllergenRules.standard)

    /// Rules grouped by their first token, longest first.
    private let rulesByFirstToken: [String: [AllergenRule]]

    init(rules: [AllergenRule]) {
        var index: [String: [AllergenRule]] = [:]
        for rule in rules {
            index[rule.tokens[0], default: []].append(rule)
        }
        rulesByFirstToken = index.mapValues { $0.sorted { $0.tokens.count > $1.tokens.count } }
    }

    func assess(_ text: String) -> DishAssessment {
        let normalized = MenuText.normalize(text)
        let tokens = MenuText.tokens(normalized: normalized)

        var found: [UKAllergen: [(term: String, likelihood: AllergenLikelihood)]] = [:]
        var claims = Set<UKAllergen>()
        var onRequest = Set<UKAllergen>()
        var recognisesFood = false

        func record(_ allergen: UKAllergen, _ likelihood: AllergenLikelihood, _ term: String) {
            var entries = found[allergen, default: []]
            if let existing = entries.firstIndex(where: { $0.term == term }) {
                entries[existing].likelihood = max(entries[existing].likelihood, likelihood)
            } else {
                entries.append((term, likelihood))
            }
            found[allergen] = entries
        }

        func apply(_ claim: FreeFromClaims.Match) {
            if claim.onRequest {
                onRequest.formUnion(claim.allergens)
            } else {
                claims.formUnion(claim.allergens)
            }
        }

        // Menu key codes in brackets: "(V, GF)", "(VG)", "[N]".
        for group in MenuText.bracketedGroups(in: normalized) where !group.isEmpty && group.allSatisfy(FreeFromClaims.bracketCodes.contains) {
            for code in group {
                switch code {
                case "n": record(.nuts, .contains, "(N)")
                case "vg", "ve": claims.formUnion(FreeFromClaims.vegan)
                default: break // gf, df, gfo, v… are read from the token stream below.
                }
            }
        }

        var index = 0
        while index < tokens.count {
            let claim = FreeFromClaims.match(tokens, at: index)
            let rule = longestRule(in: tokens, at: index)

            if let rule, rule.tokens.count > (claim?.length ?? 0) {
                // A longer food term wins, e.g. "vegan cheese" (which may contain nuts).
                if let claim { apply(claim) }
                recognisesFood = true
                for (allergen, likelihood) in rule.effects {
                    record(allergen, likelihood, rule.term)
                }
                index += rule.tokens.count
            } else if let claim {
                apply(claim)
                index += claim.length
            } else {
                index += 1
            }
        }

        // "Gluten-free option available" describes a variant, not this dish.
        if tokens.contains(where: FreeFromClaims.availabilityWords.contains) {
            onRequest.formUnion(claims)
            claims.removeAll()
        }

        var all: [AllergenEvidence] = []
        for (allergen, entries) in found {
            // Strongest first; ties keep the order they appeared on the menu.
            let strongest: AllergenLikelihood = entries.map(\.likelihood).max() ?? .possible
            var terms: [String] = []
            for level in [AllergenLikelihood.contains, .likely, .possible] {
                terms += entries.filter { $0.likelihood == level }.map(\.term)
            }
            all.append(AllergenEvidence(allergen: allergen, likelihood: strongest, terms: terms))
        }
        all.sort { lhs, rhs in
            if lhs.likelihood != rhs.likelihood { return lhs.likelihood > rhs.likelihood }
            return lhs.allergen < rhs.allergen
        }

        return DishAssessment(
            evidence: all.filter { !claims.contains($0.allergen) },
            overriddenByClaims: all.filter { claims.contains($0.allergen) },
            claimedFreeFrom: claims,
            freeFromOnRequest: onRequest.subtracting(claims),
            recognisesFood: recognisesFood
        )
    }

    private func longestRule(in tokens: [String], at start: Int) -> AllergenRule? {
        var best: AllergenRule?
        for key in MenuText.singularCandidates(tokens[start]) {
            for rule in rulesByFirstToken[key] ?? [] {
                guard rule.tokens.count <= tokens.count - start,
                      rule.tokens.count > (best?.tokens.count ?? 0) else { continue }
                if zip(rule.tokens, tokens[start...]).allSatisfy({ MenuText.word($1, matches: $0) }) {
                    best = rule
                }
            }
        }
        return best
    }
}

// MARK: - Free-from claims

/// Reads a menu's own claims, e.g. "gluten free", "free from nuts", "GF", "vegan".
nonisolated enum FreeFromClaims {
    struct Match: Sendable {
        let length: Int
        let allergens: Set<UKAllergen>
        let onRequest: Bool
    }

    static let vegan: Set<UKAllergen> = [.milk, .eggs, .fish, .crustaceans, .molluscs]

    /// Words that can appear in "X free", "free from X", "no X".
    /// "wheat free" is deliberately absent: wheat-free food can still contain barley or rye.
    /// "lactose free" is absent too: lactose-free milk is still milk.
    private static let allergenWords: [String: Set<UKAllergen>] = [
        "gluten": [.gluten],
        "dairy": [.milk], "milk": [.milk],
        "egg": [.eggs],
        "nut": [.nuts], "peanut": [.peanuts],
        "soy": [.soybeans], "soya": [.soybeans],
        "sesame": [.sesame],
        "fish": [.fish],
        "shellfish": [.crustaceans, .molluscs], "crustacean": [.crustaceans], "mollusc": [.molluscs],
        "celery": [.celery], "mustard": [.mustard],
        "sulphite": [.sulphites], "sulfite": [.sulphites],
        "lupin": [.lupin],
    ]

    private static let standaloneClaims: [String: Set<UKAllergen>] = [
        "gf": [.gluten], "df": [.milk], "coeliac": [.gluten], "celiac": [.gluten], "vegan": vegan,
    ]

    /// UK menu shorthand for "gluten-free option" / "… available".
    private static let standaloneOnRequest: [String: Set<UKAllergen>] = [
        "gfo": [.gluten], "gfa": [.gluten], "dfo": [.milk], "dfa": [.milk], "vgo": vegan, "vga": vegan,
    ]

    /// Codes that may appear alone in brackets after a dish name.
    static let bracketCodes: Set<String> = ["v", "vg", "ve", "vegan", "gf", "df", "n", "gfo", "gfa", "dfo", "dfa", "vgo", "vga"]

    /// If any of these appear, free-from claims describe an alternative version.
    static let availabilityWords: Set<String> = [
        "option", "options", "available", "request", "alternative", "alternatives", "ask", "can", "substitute", "swap", "upon",
    ]

    static func match(_ tokens: [String], at index: Int) -> Match? {
        let token = tokens[index]
        if let allergens = standaloneClaims[token] {
            return Match(length: 1, allergens: allergens, onRequest: false)
        }
        if let allergens = standaloneOnRequest[token] {
            return Match(length: 1, allergens: allergens, onRequest: true)
        }
        let next = index + 1 < tokens.count ? tokens[index + 1] : nil
        if token == "plant", next == "based" {
            return Match(length: 2, allergens: vegan, onRequest: false)
        }
        if token == "free", next == "from", let list = allergenList(tokens, from: index + 2) {
            return Match(length: 2 + list.length, allergens: list.allergens, onRequest: false)
        }
        if token == "no" || token == "without", let list = allergenList(tokens, from: index + 1) {
            return Match(length: 1 + list.length, allergens: list.allergens, onRequest: false)
        }
        if let list = allergenList(tokens, from: index), index + list.length < tokens.count, tokens[index + list.length] == "free" {
            return Match(length: list.length + 1, allergens: list.allergens, onRequest: false)
        }
        return nil
    }

    /// Reads "gluten", "gluten and dairy", "nut or sesame" starting at `start`.
    private static func allergenList(_ tokens: [String], from start: Int) -> (length: Int, allergens: Set<UKAllergen>)? {
        var allergens = Set<UKAllergen>()
        var index = start
        var end = start
        while index < tokens.count, let found = allergenWord(tokens[index]) {
            allergens.formUnion(found)
            index += 1
            end = index
            guard index < tokens.count, tokens[index] == "and" || tokens[index] == "or" else { break }
            index += 1
        }
        return allergens.isEmpty ? nil : (end - start, allergens)
    }

    private static func allergenWord(_ token: String) -> Set<UKAllergen>? {
        for candidate in MenuText.singularCandidates(token) {
            if let allergens = allergenWords[candidate] { return allergens }
        }
        return nil
    }
}

// MARK: - Text normalisation

nonisolated enum MenuText {
    /// Lower-cases, removes accents and apostrophes, and spells out "&" as "and".
    static func normalize(_ text: String) -> String {
        var result = text
            .folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive], locale: Locale(identifier: "en_GB"))
            .lowercased()
        for (from, to) in [("œ", "oe"), ("æ", "ae"), ("ß", "ss"), ("&", " and ")] {
            result = result.replacingOccurrences(of: from, with: to)
        }
        for apostrophe in ["'", "’", "‘", "`", "´"] {
            result = result.replacingOccurrences(of: apostrophe, with: "")
        }
        return result
    }

    static func tokens(_ text: String) -> [String] {
        tokens(normalized: normalize(text))
    }

    static func tokens(normalized: String) -> [String] {
        normalized
            .split(whereSeparator: { !($0.isLetter || $0.isNumber) })
            .map(String.init)
    }

    /// Token lists inside (round) or [square] brackets.
    static func bracketedGroups(in normalized: String) -> [[String]] {
        var groups: [[String]] = []
        var current: String?
        for character in normalized {
            switch character {
            case "(", "[":
                current = ""
            case ")", "]":
                if let content = current { groups.append(tokens(normalized: content)) }
                current = nil
            default:
                current?.append(character)
            }
        }
        return groups
    }

    /// Whether a word from a menu matches a singular rule term, allowing plurals.
    static func word(_ word: String, matches term: String) -> Bool {
        word == term
            || word == term + "s"
            || word == term + "es"
            || (term.hasSuffix("y") && word == term.dropLast() + "ies")
    }

    /// Possible singular forms of a word, used to look rules up.
    static func singularCandidates(_ word: String) -> [String] {
        var candidates = [word]
        if word.hasSuffix("ies") { candidates.append(String(word.dropLast(3)) + "y") }
        if word.hasSuffix("es") { candidates.append(String(word.dropLast(2))) }
        if word.hasSuffix("s") { candidates.append(String(word.dropLast())) }
        return candidates
    }
}
