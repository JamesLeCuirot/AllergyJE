import SwiftUI
import Supabase
import PostgREST

@Observable
class RestaurantStore {
    
    static let shared = RestaurantStore()
    
    var restaurants: [Restaurant] = []
    var isLoading = false
    var errorMessage: String?
    
    // MARK: - Fetch all restaurants
    func fetchRestaurants() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            let response: [Restaurant] = try await supabase
                .from("restaurants")
                .select()
                // Listed restaurants include ones without allergen information from the
                // restaurant; MenuView shows those with estimates. (Older builds list only
                // is_active restaurants, which all have the restaurant's own data.)
                .eq("is_listed", value: true)
                .order("name")
                .execute()
                .value
            
            await MainActor.run {
                self.restaurants = response
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    // MARK: - Fetch menu for a restaurant
    func fetchMenu(for restaurantId: UUID) async -> [MenuCategory: [MenuItem]] {
        do {
            // Fetch categories
            let categories: [MenuCategory] = try await supabase
                .from("menu_categories")
                .select()
                .eq("restaurant_id", value: restaurantId.uuidString)
                .order("display_order")
                .execute()
                .value
            
            // Every dish with its allergens in one request, in the order the restaurant
            // prints them.
            let records: [MenuItemRecord] = try await supabase
                .from("menu_items")
                .select("*, menu_item_allergens(level, allergens(*))")
                .eq("restaurant_id", value: restaurantId.uuidString)
                .eq("is_available", value: true)
                .order("display_order")
                .execute()
                .value
            let itemsWithAllergens = records.map { $0.menuItem }

            // Group items by category
            var menuDict: [MenuCategory: [MenuItem]] = [:]
            for category in categories {
                menuDict[category] = itemsWithAllergens.filter { $0.categoryId == category.id }
            }
            
            return menuDict
            
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
            return [:]
        }
    }
    
    // MARK: - Submit a menu report
    func submitReport(restaurantId: UUID, menuItemId: UUID?, description: String) async -> Bool {
        do {
            let report = MenuReport(
                userId: nil,
                restaurantId: restaurantId,
                menuItemId: menuItemId,
                description: description
            )
            
            try await supabase
                .from("menu_reports")
                .insert(report)
                .execute()
            
            return true
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
            return false
        }
    }
}

// MARK: - Menu item as fetched

/// A menu item as the API returns it, with its allergen links embedded.
private struct MenuItemRecord: Decodable {
    let item: MenuItem
    let links: [AllergenLink]

    struct AllergenLink: Decodable {
        /// "contains" or "may_contain".
        let level: String?
        let allergen: Allergen?

        enum CodingKeys: String, CodingKey {
            case level
            case allergen = "allergens"
        }
    }

    private enum LinkKeys: String, CodingKey {
        case links = "menu_item_allergens"
    }

    init(from decoder: Decoder) throws {
        item = try MenuItem(from: decoder)
        links = try decoder.container(keyedBy: LinkKeys.self)
            .decodeIfPresent([AllergenLink].self, forKey: .links) ?? []
    }

    /// The item with its allergens attached: "contains" first, then "may contain".
    var menuItem: MenuItem {
        var result = item
        var contains: [Allergen] = []
        var mayContain: [Allergen] = []
        for link in links {
            guard let allergen = link.allergen else { continue }
            if link.level == "may_contain" {
                mayContain.append(allergen)
            } else {
                contains.append(allergen)
            }
        }
        result.allergens = contains + mayContain
        result.mayContain = Set(mayContain.map { $0.name })
        return result
    }
}
