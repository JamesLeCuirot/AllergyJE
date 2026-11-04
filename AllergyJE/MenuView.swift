import SwiftUI

struct MenuView: View {
    let restaurant: Restaurant

    @State private var menuData: [MenuCategory: [MenuItem]] = [:]
    /// Allergens estimated from each dish's wording, for a restaurant that has no allergen
    /// information of its own. Empty otherwise.
    @State private var estimates: [UUID: DishAssessment] = [:]
    @State private var isLoading = true
    @State private var filterActive = false
    @State private var showReportSheet = false
    @State private var reportingItem: MenuItem?
    @State private var explainingItem: MenuItem?
    @State private var appeared = false

    var userAllergens: [String] {
        UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []
    }

    /// True when the allergens shown are the app's estimates, not the restaurant's.
    private var isEstimated: Bool {
        !restaurant.hasRestaurantAllergenData
    }

    var sortedCategories: [MenuCategory] {
        menuData.keys.sorted { $0.displayOrder < $1.displayOrder }
    }

    private var allItems: [MenuItem] {
        menuData.values.flatMap { $0 }
    }

    /// Dishes with none of the user's allergens: none listed by the restaurant or, for an
    /// estimated menu, none spotted in the wording.
    private var clearItemCount: Int {
        allItems.filter { item in
            DishAllergens(item: item, estimate: estimates[item.id]).conflicts(with: userAllergens).isEmpty
        }.count
    }

    var body: some View {
        menuContent
            .navigationTitle(restaurant.name)
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showReportSheet) {
                ReportIssueSheet(restaurant: restaurant, menuItem: reportingItem)
            }
            .sheet(item: $explainingItem) { item in
                DishDetailSheet(
                    dish: ScannedDish(
                        id: 0,
                        text: item.menuText,
                        box: .zero,
                        isDish: true,
                        assessment: estimates[item.id] ?? AllergenPredictor.standard.assess(item.menuText)
                    ),
                    allergens: UKAllergen.set(from: userAllergens)
                )
            }
            .task {
                let menu = await RestaurantStore.shared.fetchMenu(for: restaurant.id)
                if isEstimated {
                    var found: [UUID: DishAssessment] = [:]
                    for item in menu.values.joined() {
                        found[item.id] = AllergenPredictor.standard.assess(item.menuText)
                    }
                    estimates = found
                }
                menuData = menu
                isLoading = false
                withAnimation(.spring(duration: 0.5)) {
                    appeared = true
                }
            }
    }

    // MARK: - Menu Content
    var menuContent: some View {
        ZStack(alignment: .bottom) {
            ScrollView {
                VStack(spacing: 0) {
                    if isLoading {
                        VStack(spacing: 16) {
                            ProgressView()
                                .scaleEffect(1.2)
                            Text("Loading menu...")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.top, 80)

                    } else if menuData.isEmpty {
                        ContentUnavailableView(
                            "No Menu Available",
                            systemImage: "menucard",
                            description: Text("This restaurant hasn't uploaded their menu yet.")
                        )
                        .padding(.top, 60)

                    } else {
                        AllergenSourceBanner(restaurant: restaurant)
                            .padding(.horizontal, 16)
                            .padding(.top, 12)

                        if filterActive && !userAllergens.isEmpty {
                            FilterSummaryBanner(clear: clearItemCount, total: allItems.count, isEstimate: isEstimated)
                                .padding(.horizontal, 16)
                                .padding(.top, 10)
                                .transition(.move(edge: .top).combined(with: .opacity))
                        }

                        ForEach(Array(sortedCategories.enumerated()), id: \.element.id) { index, category in
                            MenuCategorySection(
                                category: category,
                                items: menuData[category] ?? [],
                                userAllergens: userAllergens,
                                estimates: estimates,
                                filterActive: filterActive,
                                onReport: { item in
                                    reportingItem = item
                                    showReportSheet = true
                                },
                                onExplain: { item in
                                    explainingItem = item
                                }
                            )
                            .offset(y: appeared ? 0 : 20)
                            .opacity(appeared ? 1 : 0)
                            .animation(.spring(duration: 0.5).delay(Double(min(index, 6)) * 0.08), value: appeared)
                        }

                        Color.clear.frame(height: 110)
                    }
                }
            }
            .background(Color(.systemGroupedBackground))

            // Filter button
            if !menuData.isEmpty && !isLoading {
                VStack(spacing: 0) {
                    LinearGradient(
                        colors: [Color(.systemGroupedBackground).opacity(0), Color(.systemGroupedBackground)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .frame(height: 20)

                    FilterButton(filterActive: $filterActive, userAllergens: userAllergens, isEstimate: isEstimated)
                        .padding(.horizontal, 20)
                        .padding(.bottom, 20)
                        .background(Color(.systemGroupedBackground))
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    reportingItem = nil
                    showReportSheet = true
                } label: {
                    Image(systemName: "exclamationmark.circle")
                        .foregroundStyle(Color.navy)
                }
                .accessibilityLabel("Report a problem with this menu")
            }
        }
    }
}

// MARK: - Dish allergens

extension MenuItem {
    /// Name and description, as the predictor reads them.
    var menuText: String {
        guard let description, !description.isEmpty else { return name }
        return "\(name) \(description)"
    }
}

/// One dish's allergens as the menu shows them: the restaurant's own, or estimated.
struct DishAllergens {
    struct Tag: Hashable {
        /// The allergen's stored name, e.g. "Milk", "Sulphur Dioxide".
        let allergen: String
        /// What the chip says, e.g. "Milk", "May contain tree nuts", "Likely contains egg".
        let text: String
    }

    let tags: [Tag]
    let isEstimate: Bool

    init(item: MenuItem, estimate: DishAssessment?) {
        if let estimate {
            isEstimate = true
            tags = estimate.evidence.map { evidence in
                Tag(allergen: evidence.allergen.rawValue, text: "\(evidence.likelihood.label) \(evidence.allergen.phrase)")
            }
        } else {
            isEstimate = false
            tags = item.allergens.map { allergen in
                guard item.mayContain.contains(allergen.name) else {
                    return Tag(allergen: allergen.name, text: allergen.name)
                }
                let phrase = UKAllergen(rawValue: allergen.name)?.phrase ?? allergen.name.lowercased()
                return Tag(allergen: allergen.name, text: "May contain \(phrase)")
            }
        }
    }

    /// The tags that are among the user's allergens.
    func conflicts(with userAllergens: [String]) -> [Tag] {
        tags.filter { userAllergens.contains($0.allergen) }
    }
}

// MARK: - Allergen Source Banner

/// Says where this menu's allergen information comes from.
struct AllergenSourceBanner: View {
    let restaurant: Restaurant

    var body: some View {
        if restaurant.hasRestaurantAllergenData {
            VStack(alignment: .leading, spacing: 6) {
                Label {
                    Text(sourceText)
                } icon: {
                    Image(systemName: "checkmark.shield.fill")
                        .foregroundStyle(.green)
                }
                .font(.subheadline)

                if let link = restaurant.allergenInfoURL.flatMap({ URL(string: $0) }) {
                    Link("View the restaurant's allergen information", destination: link)
                        .font(.caption)
                        .fontWeight(.semibold)
                }

                Text("Recipes change. Always tell staff about your allergies when you order.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color.green.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        } else {
            VStack(alignment: .leading, spacing: 6) {
                Label {
                    Text("Allergens on this menu are estimates")
                        .fontWeight(.semibold)
                } icon: {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                }
                .font(.subheadline)

                Text("We don't have allergen information from \(restaurant.name), so Allergy.je has estimated it from the dish names and descriptions. Estimates can miss hidden ingredients, and are least reliable for celery, mustard, sesame, soya and sulphites. Ask staff before you order.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color.orange.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
    }

    private var sourceText: String {
        if let date = restaurant.allergenInfoDateText {
            return "Allergens from \(restaurant.name)'s own allergen information, dated \(date)."
        }
        return "Allergens from \(restaurant.name)'s own allergen information."
    }
}

// MARK: - Filter Summary Banner

private struct FilterSummaryBanner: View {
    let clear: Int
    let total: Int
    let isEstimate: Bool

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: isEstimate ? "questionmark.circle.fill" : "checkmark.shield.fill")
                .foregroundStyle(isEstimate ? Color.orange : Color.green)
            Text(isEstimate
                 ? "\(clear) of \(total) dishes show no sign of your allergens. Ask staff to confirm."
                 : "\(clear) of \(total) dishes have none of your allergens, according to the restaurant.")
                .font(.subheadline)
                .fontWeight(.medium)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background((isEstimate ? Color.orange : Color.green).opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

// MARK: - Menu Category Section
struct MenuCategorySection: View {
    let category: MenuCategory
    let items: [MenuItem]
    let userAllergens: [String]
    let estimates: [UUID: DishAssessment]
    let filterActive: Bool
    let onReport: (MenuItem) -> Void
    let onExplain: (MenuItem) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(category.name)
                .font(.title3)
                .fontWeight(.bold)
                .padding(.horizontal, 16)
                .padding(.top, 28)
                .padding(.bottom, 10)

            VStack(spacing: 10) {
                ForEach(items) { item in
                    MenuItemRow(
                        item: item,
                        userAllergens: userAllergens,
                        estimate: estimates[item.id],
                        filterActive: filterActive,
                        onReport: { onReport(item) },
                        onExplain: { onExplain(item) }
                    )
                    .padding(.horizontal, 16)
                }
            }
            .padding(.bottom, 8)
        }
    }
}

// MARK: - Menu Item Row
struct MenuItemRow: View {
    let item: MenuItem
    let userAllergens: [String]
    /// The app's estimate, when the restaurant has no allergen information of its own.
    let estimate: DishAssessment?
    let filterActive: Bool
    let onReport: () -> Void
    let onExplain: () -> Void

    private var info: DishAllergens {
        DishAllergens(item: item, estimate: estimate)
    }

    private var conflicts: [DishAllergens.Tag] {
        info.conflicts(with: userAllergens)
    }

    private var showsVerdict: Bool {
        filterActive && !userAllergens.isEmpty
    }

    private var shouldDim: Bool {
        showsVerdict && !conflicts.isEmpty
    }

    var body: some View {
        ZStack {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(item.name)
                            .font(.body)
                            .fontWeight(.semibold)

                        if let description = item.description {
                            Text(description)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: 6) {
                        if let price = item.price {
                            Text("£\(price, specifier: "%.2f")")
                                .font(.subheadline)
                                .fontWeight(.bold)
                                .foregroundStyle(Color.navy)
                        }

                        if showsVerdict {
                            verdictIcon
                                .transition(.scale.combined(with: .opacity))
                        }
                    }
                }

                // Allergen tags, then the explain and report buttons
                HStack(alignment: .center) {
                    if !info.tags.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach(info.tags, id: \.self) { tag in
                                    AllergenChip(
                                        text: tag.text,
                                        isUserAllergen: userAllergens.contains(tag.allergen),
                                        isEstimate: info.isEstimate
                                    )
                                }
                            }
                        }
                    } else {
                        Text(info.isEstimate ? "No allergens spotted in the description" : "No allergens listed by the restaurant")
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                    }

                    Spacer()

                    if info.isEstimate {
                        Button(action: onExplain) {
                            Image(systemName: "info.circle")
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        }
                        .accessibilityLabel("Why this estimate")
                    }

                    Button(action: onReport) {
                        Image(systemName: "flag")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                    .accessibilityLabel("Report a problem with this dish")
                }
            }
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .shadow(color: .black.opacity(0.04), radius: 4, y: 2)

            // Dim overlay for dishes with the user's allergens
            if shouldDim {
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color(.systemGroupedBackground).opacity(0.72))
                    .allowsHitTesting(false)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: filterActive)
    }

    @ViewBuilder
    private var verdictIcon: some View {
        if !conflicts.isEmpty {
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(.red)
        } else if info.isEstimate {
            // No sign of the user's allergens in the wording isn't the same as safe.
            Image(systemName: "questionmark.circle.fill")
                .foregroundStyle(.orange)
        } else {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
        }
    }
}

// MARK: - Allergen Chip
private struct AllergenChip: View {
    let text: String
    let isUserAllergen: Bool
    /// Estimated allergens get a dashed outline.
    let isEstimate: Bool

    private var outline: Color {
        if isUserAllergen { return Color.red.opacity(0.3) }
        return isEstimate ? Color.secondary.opacity(0.35) : Color.clear
    }

    var body: some View {
        HStack(spacing: 4) {
            if isUserAllergen {
                Image(systemName: "exclamationmark")
                    .font(.system(size: 8, weight: .bold))
            }
            Text(text)
                .font(.caption2)
                .fontWeight(.semibold)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(isUserAllergen ? Color.red.opacity(0.12) : Color(.tertiarySystemGroupedBackground))
        .foregroundStyle(isUserAllergen ? Color.red : Color.secondary)
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .stroke(outline, style: StrokeStyle(lineWidth: 1, dash: isEstimate ? [3, 2] : []))
        )
    }
}

// MARK: - Filter Button
struct FilterButton: View {
    @Binding var filterActive: Bool
    let userAllergens: [String]
    /// True when the menu's allergens are estimates rather than the restaurant's own.
    let isEstimate: Bool

    private var title: String {
        if isEstimate {
            return filterActive ? "Dimming likely allergens" : "Dim likely allergens"
        }
        return filterActive ? "Showing what you can eat" : "Show me what I can eat"
    }

    private var subtitle: String? {
        if userAllergens.isEmpty { return "Add your allergies in Profile first" }
        return isEstimate ? "Estimates only. Ask staff to confirm" : nil
    }

    private var activeColor: Color {
        isEstimate ? .orange : .green
    }

    var body: some View {
        Button {
            withAnimation(.spring(duration: 0.4)) {
                filterActive.toggle()
            }
        } label: {
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(.white.opacity(0.2))
                        .frame(width: 34, height: 34)
                    Image(systemName: filterActive ? "eye.fill" : "eye.slash.fill")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                }

                VStack(alignment: .leading, spacing: 1) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.white)
                    if let subtitle {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.8))
                    }
                }

                Spacer()

                if filterActive {
                    Text("ON")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(.white.opacity(0.25))
                        .clipShape(Capsule())
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .background(
                LinearGradient(
                    colors: filterActive ?
                        [activeColor, activeColor.opacity(0.85)] :
                        [Color.navy, Color.navy.opacity(0.85)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(
                color: (filterActive ? activeColor : Color.navy).opacity(0.4),
                radius: 12, y: 6
            )
        }
        .disabled(userAllergens.isEmpty)
        .opacity(userAllergens.isEmpty ? 0.5 : 1)
    }
}

// MARK: - Report Issue Sheet
struct ReportIssueSheet: View {
    let restaurant: Restaurant
    let menuItem: MenuItem?

    @State private var description = ""
    @State private var isSubmitting = false
    @State private var submitted = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if submitted {
                    VStack(spacing: 20) {
                        Spacer()
                        ZStack {
                            Circle()
                                .fill(Color.green.opacity(0.1))
                                .frame(width: 100, height: 100)
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 50))
                                .foregroundStyle(.green)
                        }

                        VStack(spacing: 8) {
                            Text("Report Submitted")
                                .font(.title2)
                                .fontWeight(.bold)

                            Text("Thank you for helping keep our menu information accurate. We'll review your report shortly.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 32)
                        }

                        Button("Done") { dismiss() }
                            .buttonStyle(.borderedProminent)
                            .tint(Color.navy)
                            .padding(.top, 8)

                        Spacer()
                    }
                } else {
                    List {
                        if let item = menuItem {
                            Section {
                                HStack {
                                    Image(systemName: "menucard")
                                        .foregroundStyle(Color.navy)
                                    Text(item.name)
                                        .fontWeight(.medium)
                                }
                            } header: {
                                Text("Reporting issue with")
                            }
                        }

                        Section {
                            TextEditor(text: $description)
                                .frame(minHeight: 100)
                        } header: {
                            Text("Describe the issue")
                        } footer: {
                            Text("For example: 'This item contains nuts which are not listed' or 'The price is incorrect'")
                        }
                    }

                    Spacer()

                    Button {
                        Task {
                            isSubmitting = true
                            let success = await RestaurantStore.shared.submitReport(
                                restaurantId: restaurant.id,
                                menuItemId: menuItem?.id,
                                description: description
                            )
                            isSubmitting = false
                            if success { submitted = true }
                        }
                    } label: {
                        HStack {
                            if isSubmitting {
                                ProgressView().tint(.white)
                            }
                            Text("Submit Report")
                                .fontWeight(.semibold)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(description.isEmpty ? Color.secondary : Color.navy)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                        .padding(.horizontal, 20)
                        .padding(.bottom, 20)
                    }
                    .disabled(description.isEmpty || isSubmitting)
                }
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Report an Issue")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}
