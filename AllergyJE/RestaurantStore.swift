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
                .eq("is_active", value: true)
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
            
            // Fetch menu items
            let items: [MenuItem] = try await supabase
                .from("menu_items")
                .select()
                .eq("restaurant_id", value: restaurantId.uuidString)
                .eq("is_available", value: true)
                .execute()
                .value
            
            // Fetch allergens for each item
            var itemsWithAllergens: [MenuItem] = []
            for var item in items {
                let allergenLinks: [[String: String]] = try await supabase
                    .from("menu_item_allergens")
                    .select("allergen_id")
                    .eq("menu_item_id", value: item.id.uuidString)
                    .execute()
                    .value
                
                let allergenIds = allergenLinks.compactMap { $0["allergen_id"] }
                
                if !allergenIds.isEmpty {
                    let allergens: [Allergen] = try await supabase
                        .from("allergens")
                        .select()
                        .in("id", values: allergenIds)
                        .execute()
                        .value
                    item.allergens = allergens
                }
                
                itemsWithAllergens.append(item)
            }
            
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
