import SwiftUI
import CoreLocation

struct HomeView: View {
    @Binding var selectedTab: Int
    @Binding var showEditAllergies: Bool
    @State private var locationManager = LocationManager.shared
    @State private var restaurantStore = RestaurantStore.shared
    @State private var selectedRestaurant: Restaurant?
    @State private var showRestaurantSearch = false
    @State private var appeared = false
    @State private var userAllergens: [String] = UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {

                    AllergenSummaryCard(allergens: userAllergens) {
                        selectedTab = 1
                        showEditAllergies = true
                    }
                    .offset(y: appeared ? 0 : 30)
                    .opacity(appeared ? 1 : 0)
                    .animation(.spring(duration: 0.5).delay(0.1), value: appeared)

                    ScanMenuCard {
                        selectedTab = 2
                    }
                    .offset(y: appeared ? 0 : 30)
                    .opacity(appeared ? 1 : 0)
                    .animation(.spring(duration: 0.5).delay(0.15), value: appeared)

                    RestaurantDetectionCard(
                        locationManager: locationManager,
                        restaurantStore: restaurantStore,
                        selectedRestaurant: $selectedRestaurant,
                        showRestaurantSearch: $showRestaurantSearch
                    )
                    .offset(y: appeared ? 0 : 30)
                    .opacity(appeared ? 1 : 0)
                    .animation(.spring(duration: 0.5).delay(0.2), value: appeared)

                    if let restaurant = selectedRestaurant {
                        NavigationLink(destination: MenuView(restaurant: restaurant)) {
                            HStack(spacing: 12) {
                                Image(systemName: "menucard.fill")
                                    .font(.title3)
                                Text("View Menu")
                                    .font(.headline)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.subheadline)
                                    .opacity(0.7)
                            }
                            .foregroundStyle(.white)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 18)
                            .background(
                                LinearGradient(
                                    colors: [Color.navy, Color.navy.opacity(0.85)],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                            .shadow(color: Color.navy.opacity(0.4), radius: 12, y: 6)
                            .padding(.horizontal, 16)
                        }
                        .transition(.scale(scale: 0.95).combined(with: .opacity))
                    }
                }
                .padding(.top, 8)
                .padding(.bottom, 32)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Allergy.je")
            .navigationBarTitleDisplayMode(.large)
            .onReceive(NotificationCenter.default.publisher(for: UserDefaults.didChangeNotification)) { _ in
                userAllergens = UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []
            }
            .task {
                await restaurantStore.fetchRestaurants()
                locationManager.requestPermission()
                withAnimation {
                    appeared = true
                }
            }
            .onChange(of: locationManager.userLocation) { _, _ in
                locationManager.findNearbyRestaurants(allRestaurants: restaurantStore.restaurants)
            }
            .sheet(isPresented: $showRestaurantSearch) {
                RestaurantSearchSheet(
                    restaurants: restaurantStore.restaurants,
                    selectedRestaurant: $selectedRestaurant
                )
            }
        }
    }
}

// MARK: - Allergen Summary Card
struct AllergenSummaryCard: View {
    let allergens: [String]
    let onEdit: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 8) {
                    Image(systemName: "person.fill")
                        .font(.subheadline)
                        .foregroundStyle(Color.navy)
                    Text("Your Allergies")
                        .font(.headline)
                }
                Spacer()
                Button(action: onEdit) {
                    Text("Edit")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(Color.navy)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .background(Color.navy.opacity(0.1))
                        .clipShape(Capsule())
                }
            }

            if allergens.isEmpty {
                HStack(spacing: 10) {
                    Image(systemName: "exclamationmark.circle")
                        .foregroundStyle(.orange)
                    Text("No allergies selected — tap Edit to add them")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(12)
                .background(Color.orange.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 95))], spacing: 8) {
                    ForEach(allergens, id: \.self) { allergen in
                        Text(allergen)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.navy.opacity(0.1))
                            .foregroundStyle(Color.navy)
                            .clipShape(Capsule())
                    }
                }
            }
        }
        .padding(18)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .shadow(color: .black.opacity(0.05), radius: 8, y: 2)
        .padding(.horizontal, 16)
    }
}

// MARK: - Scan Menu Card
struct ScanMenuCard: View {
    let onScan: () -> Void

    var body: some View {
        Button(action: onScan) {
            HStack(spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.white.opacity(0.15))
                        .frame(width: 48, height: 48)
                    Image(systemName: "camera.viewfinder")
                        .font(.title2)
                        .foregroundStyle(.white)
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text("Scan any menu")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text("Point your camera at a menu and we'll dim the dishes that look risky for you")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.85))
                        .multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right")
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.7))
            }
            .padding(18)
            .background(
                LinearGradient(
                    colors: [Color.navy, Color.navy.opacity(0.85)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: 18))
            .shadow(color: Color.navy.opacity(0.3), radius: 10, y: 4)
            .padding(.horizontal, 16)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Restaurant Detection Card
struct RestaurantDetectionCard: View {
    var locationManager: LocationManager
    var restaurantStore: RestaurantStore
    @Binding var selectedRestaurant: Restaurant?
    @Binding var showRestaurantSearch: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 8) {
                Image(systemName: "location.fill")
                    .font(.subheadline)
                    .foregroundStyle(Color.navy)
                Text("Where are you eating?")
                    .font(.headline)
            }

            if locationManager.authorizationStatus == .notDetermined {
                Button {
                    locationManager.requestPermission()
                } label: {
                    HStack {
                        Image(systemName: "location.fill")
                        Text("Enable Location Detection")
                            .fontWeight(.medium)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .opacity(0.7)
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)
                    .background(Color.navy)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

            } else if locationManager.authorizationStatus == .denied {
                HStack(spacing: 12) {
                    Image(systemName: "location.slash.fill")
                        .foregroundStyle(.red.opacity(0.8))
                    Text("Location access denied. Please search manually.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(12)
                .background(Color.red.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 10))

            } else if !locationManager.nearbyRestaurants.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Detected nearby")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(.secondary)
                        .textCase(.uppercase)
                        .tracking(0.5)

                    ForEach(locationManager.nearbyRestaurants.prefix(3)) { restaurant in
                        Button {
                            withAnimation(.spring(duration: 0.3)) {
                                selectedRestaurant = restaurant
                            }
                        } label: {
                            HStack(spacing: 12) {
                                ZStack {
                                    Circle()
                                        .fill(selectedRestaurant?.id == restaurant.id ? Color.navy : Color(.tertiarySystemGroupedBackground))
                                        .frame(width: 36, height: 36)
                                    Image(systemName: "fork.knife")
                                        .font(.caption)
                                        .foregroundStyle(selectedRestaurant?.id == restaurant.id ? .white : Color.navy)
                                }

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(restaurant.name)
                                        .font(.subheadline)
                                        .fontWeight(.semibold)
                                        .foregroundStyle(.primary)
                                    if let address = restaurant.address {
                                        Text(address)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                Spacer()
                                Image(systemName: selectedRestaurant?.id == restaurant.id ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(selectedRestaurant?.id == restaurant.id ? Color.navy : Color(.tertiaryLabel))
                                    .animation(.spring(duration: 0.2), value: selectedRestaurant?.id)
                            }
                            .padding(12)
                            .background(
                                selectedRestaurant?.id == restaurant.id ?
                                Color.navy.opacity(0.08) : Color(.tertiarySystemGroupedBackground)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(selectedRestaurant?.id == restaurant.id ? Color.navy.opacity(0.3) : Color.clear, lineWidth: 1.5)
                            )
                        }
                    }
                }
            } else {
                HStack(spacing: 12) {
                    Image(systemName: "location.magnifyingglass")
                        .foregroundStyle(.secondary)
                    Text("No restaurants detected nearby")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(12)
                .background(Color(.tertiarySystemGroupedBackground))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            Rectangle()
                .fill(Color(.separator).opacity(0.5))
                .frame(height: 1)

            Button {
                showRestaurantSearch = true
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(Color.navy)
                    Text(selectedRestaurant == nil ? "Search for a restaurant" : "Change restaurant")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(Color.navy)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(Color.navy.opacity(0.5))
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .background(Color.navy.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            if let restaurant = selectedRestaurant {
                HStack(spacing: 10) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Selected")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(restaurant.name)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                    }
                    Spacer()
                }
                .padding(12)
                .background(Color.green.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.green.opacity(0.3), lineWidth: 1)
                )
                .transition(.scale(scale: 0.95).combined(with: .opacity))
            }
        }
        .padding(18)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .shadow(color: .black.opacity(0.05), radius: 8, y: 2)
        .padding(.horizontal, 16)
    }
}

// MARK: - Restaurant Search Sheet
struct RestaurantSearchSheet: View {
    let restaurants: [Restaurant]
    @Binding var selectedRestaurant: Restaurant?
    @State private var searchText = ""
    @Environment(\.dismiss) private var dismiss

    var filtered: [Restaurant] {
        if searchText.isEmpty { return restaurants }
        return restaurants.filter {
            $0.name.localizedCaseInsensitiveContains(searchText)
        }
    }

    var freeTier: [Restaurant] { filtered.filter { $0.isFreeTier } }
    var premium: [Restaurant] { filtered.filter { !$0.isFreeTier } }

    var body: some View {
        NavigationStack {
            List {
                if !freeTier.isEmpty {
                    Section("Free") {
                        ForEach(freeTier) { restaurant in
                            RestaurantRow(restaurant: restaurant) {
                                selectedRestaurant = restaurant
                                dismiss()
                            }
                        }
                    }
                }

                if !premium.isEmpty {
                    Section("Pro") {
                        ForEach(premium) { restaurant in
                            RestaurantRow(restaurant: restaurant) {
                                selectedRestaurant = restaurant
                                dismiss()
                            }
                        }
                    }
                }
            }
            .searchable(text: $searchText, prompt: "Search restaurants")
            .navigationTitle("Select Restaurant")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct RestaurantRow: View {
    let restaurant: Restaurant
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.navy.opacity(0.1))
                        .frame(width: 36, height: 36)
                    Image(systemName: "fork.knife")
                        .font(.caption)
                        .foregroundStyle(Color.navy)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(restaurant.name)
                        .font(.body)
                        .foregroundStyle(.primary)
                    if let address = restaurant.address {
                        Text(address)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                if !restaurant.isFreeTier {
                    Image(systemName: "lock.fill")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

#Preview {
    HomeView(selectedTab: .constant(0), showEditAllergies: .constant(false))
}
