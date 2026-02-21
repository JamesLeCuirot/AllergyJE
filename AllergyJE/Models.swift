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
    let isFreeTier: Bool
    let isActive: Bool
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, name, address, latitude, longitude, phone, website
        case isFreeTier = "is_free_tier"
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
    let createdAt: Date
    let updatedAt: Date
    var allergens: [Allergen] = []
    
    enum CodingKeys: String, CodingKey {
        case id, name, description, price
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
