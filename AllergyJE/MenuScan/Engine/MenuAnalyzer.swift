#if canImport(CoreGraphics)
import CoreGraphics
#endif
import Foundation

/// A block of menu text with the predictor's reading of it.
nonisolated struct ScannedDish: Identifiable, Equatable, Sendable {
    let id: Int
    let text: String
    /// In the same coordinate space as the `RecognizedLine`s it came from.
    let box: CGRect
    /// False for headings, allergy notices and other text that isn't a dish.
    let isDish: Bool
    let assessment: DishAssessment

    func verdict(for allergens: Set<UKAllergen>, minimum: AllergenLikelihood = .possible) -> DishVerdict {
        guard isDish else { return .notADish }
        let concerns = assessment.concerns(for: allergens, minimum: minimum)
        return concerns.isEmpty ? .noIndicators : .flagged(concerns)
    }
}

nonisolated enum DishVerdict: Equatable, Sendable {
    /// Headings, notices, addresses. Shown dimmed, with no claim either way.
    case notADish
    /// Nothing in the text points to the user's allergens. This is NOT a promise the
    /// dish is safe: the menu may leave ingredients out, and kitchens cross-contaminate.
    case noIndicators
    /// The text suggests the dish contains one or more of the user's allergens.
    case flagged([AllergenEvidence])
}

/// Turns OCR lines from a menu into dishes with allergen predictions.
nonisolated enum MenuAnalyzer {
    static func analyze(_ lines: [RecognizedLine], predictor: AllergenPredictor = .standard) -> [ScannedDish] {
        MenuLayout.blocks(from: lines).enumerated().map { index, block in
            let assessment = predictor.assess(block.text)
            return ScannedDish(
                id: index,
                text: block.text,
                box: block.box,
                isDish: looksLikeDish(block, assessment),
                assessment: assessment
            )
        }
    }

    static func looksLikeDish(_ block: MenuBlock, _ assessment: DishAssessment) -> Bool {
        let tokens = MenuText.tokens(block.text)
        // "Please tell your server about any allergies or intolerances…"
        if tokens.contains(where: { $0.hasPrefix("allerg") || $0.hasPrefix("intoleran") }) {
            return false
        }
        if assessment.recognisesFood { return true }
        let words = tokens.filter { $0.contains(where: \.isLetter) }
        if block.hasPrice && !words.isEmpty { return true }
        // Unknown words with no price: a dish description if it runs over several lines.
        return block.lines.count >= 2 && words.count >= 4
    }
}
