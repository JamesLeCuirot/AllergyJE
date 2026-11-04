import SwiftUI

/// A captured or chosen menu photo with the overlay, and the dishes listed below in readable text.
struct ScannedMenuReview: View {
    let menu: ScannedMenu
    let allergens: Set<UKAllergen>
    @State private var selectedDish: ScannedDish?

    private var dishes: [ScannedDish] { menu.dishes.filter(\.isDish) }
    private var clear: [ScannedDish] { dishes.filter { $0.verdict(for: allergens) == .noIndicators } }
    private var flagged: [ScannedDish] { dishes.filter { $0.verdict(for: allergens) != .noIndicators } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Image(uiImage: menu.image)
                    .resizable()
                    .scaledToFit()
                    .overlay {
                        GeometryReader { geometry in
                            AllergenOverlay(dishes: menu.dishes, allergens: allergens, place: { box in
                                CGRect(
                                    x: box.minX * geometry.size.width,
                                    y: box.minY * geometry.size.height,
                                    width: box.width * geometry.size.width,
                                    height: box.height * geometry.size.height
                                )
                            }) { dish in
                                selectedDish = dish
                            }
                        }
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 14))

                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text(DishDetailSheet.disclaimer)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(14)
                .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))

                if allergens.isEmpty {
                    Text("You haven't added any allergies yet. Add them in Profile and scan again.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    dishSection("No sign of your allergens", dishes: clear)
                    dishSection("Flagged", dishes: flagged)
                }
            }
            .padding(16)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Scanned Menu")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $selectedDish) { dish in
            DishDetailSheet(dish: dish, allergens: allergens)
        }
    }

    @ViewBuilder
    private func dishSection(_ title: String, dishes: [ScannedDish]) -> some View {
        if !dishes.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Text("\(title) (\(dishes.count))")
                    .font(.headline)
                ForEach(dishes) { dish in
                    Button {
                        selectedDish = dish
                    } label: {
                        ScannedDishRow(dish: dish, allergens: allergens)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

private struct ScannedDishRow: View {
    let dish: ScannedDish
    let allergens: Set<UKAllergen>

    private var concerns: [AllergenEvidence] {
        if case .flagged(let found) = dish.verdict(for: allergens) { return found }
        return []
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: concerns.isEmpty ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundStyle(concerns.isEmpty ? .green : .red)
            VStack(alignment: .leading, spacing: 4) {
                Text(dish.text)
                    .font(.subheadline)
                    .foregroundStyle(.primary)
                    .lineLimit(3)
                Text(concerns.isEmpty
                     ? "No sign of your allergens. Check with staff."
                     : concerns.map { "\($0.likelihood.label) \($0.allergen.phrase)" }.joined(separator: " · "))
                    .font(.caption)
                    .foregroundStyle(concerns.isEmpty ? Color.secondary : Color.red)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(14)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
    }
}

/// Explains why a dish was flagged or left clear.
struct DishDetailSheet: View {
    static let disclaimer = "Allergy.je predicts allergens from the words on the menu. It can't see recipes, hidden ingredients or cross-contamination in the kitchen. Always tell staff about your allergies before you order."

    let dish: ScannedDish
    let allergens: Set<UKAllergen>
    @Environment(\.dismiss) private var dismiss

    private var concerns: [AllergenEvidence] {
        dish.assessment.concerns(for: allergens)
    }

    private var otherEvidence: [AllergenEvidence] {
        dish.assessment.evidence.filter { !allergens.contains($0.allergen) }
    }

    private func names(_ set: Set<UKAllergen>) -> String {
        set.sorted().map(\.phrase).joined(separator: ", ")
    }

    var body: some View {
        NavigationStack {
            List {
                Section("On the menu") {
                    Text(dish.text)
                }

                Section("Your allergens") {
                    if allergens.isEmpty {
                        Text("Add your allergies in Profile to check dishes against them.")
                            .foregroundStyle(.secondary)
                    } else if concerns.isEmpty {
                        Label("Nothing in the description points to your allergens.", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                    ForEach(concerns, id: \.allergen) { evidence in
                        EvidenceRow(evidence: evidence, tint: .red)
                    }
                }

                if !dish.assessment.claimedFreeFrom.isEmpty {
                    Section("What the menu claims") {
                        Text("The menu marks this as free from \(names(dish.assessment.claimedFreeFrom)). We can't check that claim, so confirm it with staff.")
                        ForEach(dish.assessment.overriddenByClaims, id: \.allergen) { evidence in
                            Text("Set aside because of the claim: \(evidence.summary)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                if !dish.assessment.freeFromOnRequest.isEmpty {
                    Section {
                        Text("The menu says a version free from \(names(dish.assessment.freeFromOnRequest)) can be made. Ask for it when you order.")
                    }
                }

                if !otherEvidence.isEmpty {
                    Section("Other allergens it may contain") {
                        ForEach(otherEvidence, id: \.allergen) { evidence in
                            EvidenceRow(evidence: evidence, tint: .secondary)
                        }
                    }
                }

                Section {
                    Text(Self.disclaimer)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Why this result")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

private struct EvidenceRow: View {
    let evidence: AllergenEvidence
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(evidence.likelihood.label) \(evidence.allergen.phrase)")
                .fontWeight(.semibold)
                .foregroundStyle(tint)
            Text("Because the menu mentions \(evidence.terms.joined(separator: ", "))")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
