import Foundation

/// The 14 allergens that UK and EU food law require food businesses to declare.
/// Jersey's planned allergen regulations under the Food (Jersey) Law 2023 are expected
/// to use the same list.
///
/// Raw values match the strings the app already saves under the `guestAllergens`
/// UserDefaults key, so a saved selection converts with `UKAllergen(rawValue:)`.
nonisolated enum UKAllergen: String, CaseIterable, Codable, Hashable, Comparable, Sendable {
    case gluten = "Gluten"
    case crustaceans = "Crustaceans"
    case eggs = "Eggs"
    case fish = "Fish"
    case peanuts = "Peanuts"
    case soybeans = "Soybeans"
    case milk = "Milk"
    case nuts = "Nuts"
    case celery = "Celery"
    case mustard = "Mustard"
    case sesame = "Sesame"
    case sulphites = "Sulphur Dioxide"
    case lupin = "Lupin"
    case molluscs = "Molluscs"

    /// The identifier used for this allergen in `AllergenRules.source`.
    var ruleKey: String {
        switch self {
        case .soybeans: "soy"
        case .sulphites: "sulphites"
        default: rawValue.lowercased()
        }
    }

    /// Lower-case name for use inside a sentence, e.g. "may contain tree nuts".
    var phrase: String {
        switch self {
        case .eggs: "egg"
        case .soybeans: "soya"
        case .nuts: "tree nuts"
        case .sulphites: "sulphites"
        default: rawValue.lowercased()
        }
    }

    /// Converts saved allergen names, ignoring any this version doesn't recognise.
    static func set(from saved: [String]) -> Set<UKAllergen> {
        Set(saved.compactMap(UKAllergen.init(rawValue:)))
    }

    static func < (lhs: UKAllergen, rhs: UKAllergen) -> Bool {
        lhs.sortIndex < rhs.sortIndex
    }

    private var sortIndex: Int {
        Self.allCases.firstIndex(of: self) ?? 0
    }
}

/// How strongly a menu term suggests that a dish contains an allergen.
nonisolated enum AllergenLikelihood: Int, Comparable, Codable, Sendable {
    /// Often included, depending on the kitchen. "curry" → mustard.
    case possible = 1
    /// The classic recipe includes it. "pesto" → nuts.
    case likely = 2
    /// The named ingredient is, or is made from, the allergen. "prawns" → crustaceans.
    case contains = 3

    init?(marker: Character) {
        switch marker {
        case "?": self = .possible
        case "~": self = .likely
        case "!": self = .contains
        default: return nil
        }
    }

    /// Sentence opener, e.g. "Likely contains" + " tree nuts".
    var label: String {
        switch self {
        case .possible: "May contain"
        case .likely: "Likely contains"
        case .contains: "Contains"
        }
    }

    static func < (lhs: AllergenLikelihood, rhs: AllergenLikelihood) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}
