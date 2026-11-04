import SwiftUI

/// Darkens a menu except for the dishes that show no sign of the user's allergens.
///
/// Flagged dishes stay dark with a red outline and a badge naming the allergens.
/// Headings and notices stay dark with no outline.
struct AllergenOverlay: View {
    let dishes: [ScannedDish]
    let allergens: Set<UKAllergen>
    /// Converts a dish's box into this view's coordinates.
    let place: (CGRect) -> CGRect
    var onSelect: ((ScannedDish) -> Void)?

    private struct Item: Identifiable {
        let dish: ScannedDish
        let rect: CGRect
        let concerns: [AllergenEvidence]
        let isClear: Bool
        var id: Int { dish.id }
    }

    private var items: [Item] {
        dishes.map { dish in
            let verdict = dish.verdict(for: allergens)
            var concerns: [AllergenEvidence] = []
            if case .flagged(let found) = verdict { concerns = found }
            return Item(
                dish: dish,
                rect: place(dish.box).insetBy(dx: -6, dy: -3),
                concerns: concerns,
                isClear: verdict == .noIndicators
            )
        }
    }

    var body: some View {
        let items = self.items
        let shouldShade = !allergens.isEmpty && items.contains { $0.dish.isDish }

        ZStack(alignment: .topLeading) {
            Canvas { context, size in
                guard shouldShade else { return }
                // Shade everything, then punch the clear dishes out of the shade. Unlike an
                // even-odd fill, this keeps overlapping holes clear too.
                context.drawLayer { layer in
                    layer.fill(Path(CGRect(origin: .zero, size: size)), with: .color(.black.opacity(0.7)))
                    layer.blendMode = .destinationOut
                    for item in items where item.isClear {
                        layer.fill(Path(roundedRect: item.rect, cornerRadius: 6), with: .color(.black))
                    }
                }

                for item in items where item.isClear || !item.concerns.isEmpty {
                    let outline = Path(roundedRect: item.rect, cornerRadius: 6)
                    context.stroke(outline, with: .color(item.isClear ? .green : .red.opacity(0.85)), lineWidth: 2)
                }
            }
            .allowsHitTesting(false)

            if shouldShade {
                ForEach(items.filter { !$0.concerns.isEmpty }) { item in
                    Text(item.concerns.prefix(3).map(\.allergen.rawValue).joined(separator: " · "))
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.red.opacity(0.85), in: Capsule())
                        .fixedSize()
                        .offset(x: item.rect.minX, y: max(0, item.rect.minY - 18))
                        .allowsHitTesting(false)
                }
            }

            if let onSelect {
                ForEach(items.filter { $0.dish.isDish }) { item in
                    Color.clear
                        .frame(width: max(item.rect.width, 1), height: max(item.rect.height, 1))
                        .contentShape(Rectangle())
                        .offset(x: item.rect.minX, y: item.rect.minY)
                        .onTapGesture { onSelect(item.dish) }
                        .accessibilityElement()
                        .accessibilityLabel(item.dish.text)
                        .accessibilityAddTraits(.isButton)
                        .accessibilityAction { onSelect(item.dish) }
                }
            }
        }
    }
}
