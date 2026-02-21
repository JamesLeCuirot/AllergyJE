import SwiftUI

struct MenuView: View {
    let restaurant: Restaurant

    @State private var menuData: [MenuCategory: [MenuItem]] = [:]
    @State private var isLoading = true
    @State private var filterActive = false
    @State private var showReportSheet = false
    @State private var reportingItem: MenuItem?
    @State private var showPaywall = false
    @State private var appeared = false
    @State private var subscriptionManager = SubscriptionManager.shared

    var userAllergens: [String] {
        UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []
    }

    var hasAccess: Bool {
        restaurant.isFreeTier || subscriptionManager.isSubscribed
    }

    var sortedCategories: [MenuCategory] {
        menuData.keys.sorted { $0.displayOrder < $1.displayOrder }
    }

    var safeItemCount: Int {
        menuData.values.flatMap { $0 }.filter { item in
            !item.allergens.map { $0.name }.contains(where: { userAllergens.contains($0) })
        }.count
    }

    var totalItemCount: Int {
        menuData.values.flatMap { $0 }.count
    }

    var body: some View {
        Group {
            if hasAccess {
                menuContent
            } else {
                lockedContent
            }
        }
        .navigationTitle(restaurant.name)
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showPaywall) {
            PaywallView()
        }
        .sheet(isPresented: $showReportSheet) {
            ReportIssueSheet(restaurant: restaurant, menuItem: reportingItem)
        }
        .task {
            if hasAccess {
                menuData = await RestaurantStore.shared.fetchMenu(for: restaurant.id)
                isLoading = false
                withAnimation(.spring(duration: 0.5)) {
                    appeared = true
                }
            }
        }
    }

    // MARK: - Locked Content
    var lockedContent: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 28) {
                ZStack {
                    Circle()
                        .fill(Color.navy.opacity(0.08))
                        .frame(width: 130, height: 130)
                    Circle()
                        .fill(Color.navy.opacity(0.05))
                        .frame(width: 100, height: 100)
                    Image(systemName: "lock.fill")
                        .font(.system(size: 44))
                        .foregroundStyle(Color.navy)
                }

                VStack(spacing: 10) {
                    Text("Pro Restaurant")
                        .font(.title2)
                        .fontWeight(.bold)

                    Text("\(restaurant.name) is available on Allergy.je Pro. Upgrade to access all restaurants and menus across Jersey.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }

                VStack(spacing: 16) {
                    // Feature list
                    VStack(alignment: .leading, spacing: 12) {
                        ProFeatureRow(icon: "building.2.fill", text: "All restaurants in Jersey")
                        ProFeatureRow(icon: "menucard.fill", text: "Full menus with allergen filtering")
                        ProFeatureRow(icon: "checkmark.shield.fill", text: "Verified allergen information")
                    }
                    .padding(16)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .padding(.horizontal, 24)

                    Button {
                        showPaywall = true
                    } label: {
                        HStack(spacing: 10) {
                            Image(systemName: "star.fill")
                                .foregroundStyle(.yellow)
                            Text("Upgrade to Pro")
                                .fontWeight(.semibold)
                            Spacer()
                            Text("£1.99/mo")
                                .font(.subheadline)
                                .opacity(0.85)
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 16)
                        .background(
                            LinearGradient(
                                colors: [Color.navy, Color.navy.opacity(0.85)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                        .shadow(color: Color.navy.opacity(0.35), radius: 10, y: 5)
                        .padding(.horizontal, 24)
                    }

                    Text("Cancel anytime · Family sharing available")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()
        }
        .background(Color(.systemGroupedBackground))
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
                        // Safe items summary banner
                        if filterActive && !userAllergens.isEmpty {
                            HStack(spacing: 10) {
                                Image(systemName: "checkmark.shield.fill")
                                    .foregroundStyle(.green)
                                Text("\(safeItemCount) of \(totalItemCount) items are safe for you")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                Spacer()
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .background(Color.green.opacity(0.1))
                            .overlay(
                                Rectangle()
                                    .fill(Color.green.opacity(0.3))
                                    .frame(height: 1),
                                alignment: .bottom
                            )
                            .transition(.move(edge: .top).combined(with: .opacity))
                        }

                        ForEach(Array(sortedCategories.enumerated()), id: \.element.id) { index, category in
                            MenuCategorySection(
                                category: category,
                                items: menuData[category] ?? [],
                                userAllergens: userAllergens,
                                filterActive: filterActive,
                                onReport: { item in
                                    reportingItem = item
                                    showReportSheet = true
                                }
                            )
                            .offset(y: appeared ? 0 : 20)
                            .opacity(appeared ? 1 : 0)
                            .animation(.spring(duration: 0.5).delay(Double(index) * 0.08), value: appeared)
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

                    FilterButton(filterActive: $filterActive, userAllergens: userAllergens)
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
            }
        }
    }
}

// MARK: - Pro Feature Row
struct ProFeatureRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundStyle(Color.navy)
                .frame(width: 24)
            Text(text)
                .font(.subheadline)
            Spacer()
        }
    }
}

// MARK: - Menu Category Section
struct MenuCategorySection: View {
    let category: MenuCategory
    let items: [MenuItem]
    let userAllergens: [String]
    let filterActive: Bool
    let onReport: (MenuItem) -> Void

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
                        filterActive: filterActive,
                        onReport: { onReport(item) }
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
    let filterActive: Bool
    let onReport: () -> Void

    var isSafe: Bool {
        !item.allergens.map { $0.name }.contains(where: { userAllergens.contains($0) })
    }

    var shouldDim: Bool {
        filterActive && !isSafe && !userAllergens.isEmpty
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

                        if filterActive && !userAllergens.isEmpty {
                            Image(systemName: isSafe ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .foregroundStyle(isSafe ? .green : .red)
                                .transition(.scale.combined(with: .opacity))
                        }
                    }
                }

                // Allergen tags + report button
                HStack(alignment: .center) {
                    if !item.allergens.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach(item.allergens) { allergen in
                                    HStack(spacing: 4) {
                                        if userAllergens.contains(allergen.name) {
                                            Image(systemName: "exclamationmark")
                                                .font(.system(size: 8, weight: .bold))
                                        }
                                        Text(allergen.name)
                                            .font(.caption2)
                                            .fontWeight(.semibold)
                                    }
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(
                                        userAllergens.contains(allergen.name) ?
                                        Color.red.opacity(0.12) : Color(.tertiarySystemGroupedBackground)
                                    )
                                    .foregroundStyle(
                                        userAllergens.contains(allergen.name) ?
                                        Color.red : Color.secondary
                                    )
                                    .clipShape(Capsule())
                                    .overlay(
                                        Capsule()
                                            .stroke(
                                                userAllergens.contains(allergen.name) ?
                                                Color.red.opacity(0.3) : Color.clear,
                                                lineWidth: 1
                                            )
                                    )
                                }
                            }
                        }
                    } else {
                        Text("No allergens listed")
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                    }

                    Spacer()

                    Button(action: onReport) {
                        Image(systemName: "flag")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                }
            }
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .shadow(color: .black.opacity(0.04), radius: 4, y: 2)

            // Dim overlay for unsafe items
            if shouldDim {
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color(.systemGroupedBackground).opacity(0.72))
                    .allowsHitTesting(false)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: filterActive)
    }
}

// MARK: - Filter Button
struct FilterButton: View {
    @Binding var filterActive: Bool
    let userAllergens: [String]
    @State private var subscriptionManager = SubscriptionManager.shared
    @State private var showPaywall = false

    var body: some View {
        Button {
            if subscriptionManager.isSubscribed {
                withAnimation(.spring(duration: 0.4)) {
                    filterActive.toggle()
                }
            } else {
                showPaywall = true
            }
        } label: {
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(.white.opacity(0.2))
                        .frame(width: 34, height: 34)
                    Image(systemName: subscriptionManager.isSubscribed ? (filterActive ? "eye.fill" : "eye.slash.fill") : "lock.fill")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                }

                VStack(alignment: .leading, spacing: 1) {
                    Text(subscriptionManager.isSubscribed ? (filterActive ? "Showing what you can eat" : "Show me what I can eat") : "Show me what I can eat")
                        .font(.headline)
                        .foregroundStyle(.white)
                    if !subscriptionManager.isSubscribed {
                        Text("Pro feature — tap to upgrade")
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.8))
                    }
                }

                Spacer()

                if subscriptionManager.isSubscribed && filterActive {
                    Text("ON")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(.white.opacity(0.25))
                        .clipShape(Capsule())
                } else if !subscriptionManager.isSubscribed {
                    Text("PRO")
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
                    colors: subscriptionManager.isSubscribed && filterActive ?
                        [Color.green, Color.green.opacity(0.85)] :
                        [Color.navy, Color.navy.opacity(0.85)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(
                color: (subscriptionManager.isSubscribed && filterActive ? Color.green : Color.navy).opacity(0.4),
                radius: 12, y: 6
            )
        }
        .disabled(userAllergens.isEmpty)
        .opacity(userAllergens.isEmpty ? 0.5 : 1)
        .sheet(isPresented: $showPaywall) {
            PaywallView()
        }
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
