import Foundation

// MARK: - Restaurant
struct Restaurant: Identifiable, Codable, Hashable {
    let id: UUID
    let name: String
    let address: String?
    let latitude: Double?
    let longitude: Double?
    let phone: String?
    let website: String?
    /// The restaurant's own menu page.
    let menuURL: String?
    /// Where the restaurant publishes its allergen information. Nil when we have none
    /// from the restaurant: the app then shows estimates from the dish names, never "safe".
    let allergenInfoURL: String?
    /// The date on that allergen information, e.g. "2026-08-12".
    let allergenInfoDate: String?
    let isActive: Bool
    let createdAt: Date
    let updatedAt: Date

    /// True when the dishes' allergens come from the restaurant itself.
    var hasRestaurantAllergenData: Bool {
        !(allergenInfoURL ?? "").isEmpty
    }

    /// "12 August 2026", from `allergenInfoDate`.
    var allergenInfoDateText: String? {
        guard let text = allergenInfoDate else { return nil }
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.dateFormat = "yyyy-MM-dd"
        guard let date = parser.date(from: text) else { return text }
        return date.formatted(.dateTime.day().month(.wide).year())
    }

    enum CodingKeys: String, CodingKey {
        case id, name, address, latitude, longitude, phone, website
        case menuURL = "menu_url"
        case allergenInfoURL = "allergen_info_url"
        case allergenInfoDate = "allergen_info_date"
        case isActive = "is_active"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - Menu Category
struct MenuCategory: Identifiable, Codable, Hashable {
    let id: UUID
    let restaurantId: UUID
    let name: String
    let displayOrder: Int
    let createdAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, name
        case restaurantId = "restaurant_id"
        case displayOrder = "display_order"
        case createdAt = "created_at"
    }
}

// MARK: - Menu Item
struct MenuItem: Identifiable, Codable, Hashable {
    let id: UUID
    let categoryId: UUID
    let restaurantId: UUID
    let name: String
    let description: String?
    let price: Double?
    let isAvailable: Bool
    /// Position within its category, as the restaurant prints the menu.
    var displayOrder: Int = 0
    let createdAt: Date
    let updatedAt: Date
    /// Allergens the restaurant lists for this dish, "contains" and "may contain" alike.
    var allergens: [Allergen] = []
    /// Names of the allergens in `allergens` that the restaurant lists only as "may contain".
    var mayContain: Set<String> = []
    
    enum CodingKeys: String, CodingKey {
        case id, name, description, price
        case displayOrder = "display_order"
        case categoryId = "category_id"
        case restaurantId = "restaurant_id"
        case isAvailable = "is_available"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - Allergen
struct Allergen: Identifiable, Codable, Hashable {
    let id: UUID
    let name: String
    let iconName: String?
    let createdAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, name
        case iconName = "icon_name"
        case createdAt = "created_at"
    }
}

// MARK: - Menu Report
struct MenuReport: Codable {
    let userId: UUID?
    let restaurantId: UUID
    let menuItemId: UUID?
    let description: String
    
    enum CodingKeys: String, CodingKey {
        case description
        case userId = "user_id"
        case restaurantId = "restaurant_id"
        case menuItemId = "menu_item_id"
    }
}
