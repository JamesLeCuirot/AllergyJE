import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
import MenuEngine

/// Reads the app's restaurant menus from Supabase as labelled dishes.
///
/// Uses the public REST API with the anon key, so it sees exactly what the app sees:
/// active restaurants and available dishes. Hidden (menu-only) restaurants are left out,
/// because their dishes have no allergen data and would look allergen-free.
public enum SupabaseExport {
    public struct ExportError: Error, CustomStringConvertible {
        public let description: String
    }

    public static let source = "Allergy.je database"

    /// PostgREST answers at most this many rows per request (Supabase's default `max-rows`).
    static let pageSize = 1000

    public static func fetchDishes(projectURL: String, anonKey: String) async throws -> [LabelledDish] {
        guard let endpoint = URL(string: projectURL.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/rest/v1/menu_items") else {
            throw ExportError(description: "'\(projectURL)' isn't a valid URL")
        }
        // Page through in a fixed order: a single request silently stops at the row limit.
        var rows: [Row] = []
        while true {
            var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)!
            components.queryItems = [
                URLQueryItem(name: "select", value: "name,description,restaurants!inner(name),menu_item_allergens(level,allergens(name))"),
                URLQueryItem(name: "is_available", value: "eq.true"),
                URLQueryItem(name: "order", value: "id"),
                URLQueryItem(name: "limit", value: String(pageSize)),
                URLQueryItem(name: "offset", value: String(rows.count)),
            ]
            guard let url = components.url else { throw ExportError(description: "couldn't build the request URL") }

            var request = URLRequest(url: url)
            request.setValue(anonKey, forHTTPHeaderField: "apikey")
            request.setValue("Bearer \(anonKey)", forHTTPHeaderField: "Authorization")

            let (data, response) = try await load(request)
            guard let status = (response as? HTTPURLResponse)?.statusCode, (200..<300).contains(status) else {
                let body = String(decoding: data.prefix(500), as: UTF8.self)
                throw ExportError(description: "Supabase returned \((response as? HTTPURLResponse)?.statusCode ?? 0): \(body)")
            }
            let page = try JSONDecoder().decode([Row].self, from: data)
            rows += page
            if page.count < pageSize { break }
        }
        return try dishes(from: rows)
    }

    /// Converts the REST response (menu items with embedded restaurant and allergen names).
    public static func dishes(fromJSON data: Data) throws -> [LabelledDish] {
        try dishes(from: JSONDecoder().decode([Row].self, from: data))
    }

    private static func dishes(from rows: [Row]) throws -> [LabelledDish] {
        var unknown = Set<String>()
        let dishes = rows.map { row in
            var labels: [UKAllergen: AllergenLabel] = [:]
            for link in row.menu_item_allergens ?? [] {
                guard let name = link.allergens?.name else { continue }
                if let allergen = UKAllergen(rawValue: name) {
                    let label: AllergenLabel = link.level == "may_contain" ? .mayContain : .contains
                    if labels[allergen] != .contains { labels[allergen] = label }
                } else {
                    unknown.insert(name)
                }
            }
            return LabelledDish(
                source: source,
                restaurant: row.restaurants?.name ?? "",
                dish: row.name,
                description: row.description ?? "",
                labels: labels
            )
        }
        if !unknown.isEmpty {
            throw ExportError(description: "unrecognised allergen names in the database: \(unknown.sorted().joined(separator: ", "))")
        }
        // Stable order, so re-exporting only shows real changes in a diff.
        return collapsingSharedMenus(dishes).sorted { ($0.restaurant, $0.dish, $0.description) < ($1.restaurant, $1.dish, $1.description) }
    }

    /// Keeps one copy of a menu that several restaurants share (a chain's branches).
    ///
    /// Two branches with the same dishes and allergens are one data point, not two.
    /// Counting them twice would skew the scorecard, and would let the learner treat one
    /// kitchen as "seen at two restaurants". The first restaurant by name is kept.
    public static func collapsingSharedMenus(_ dishes: [LabelledDish]) -> [LabelledDish] {
        let byRestaurant = Dictionary(grouping: dishes, by: \.restaurant)
        var seen = Set<[String]>()
        var kept: [LabelledDish] = []
        for name in byRestaurant.keys.sorted() {
            let menu = byRestaurant[name]!
            let fingerprint = menu.map { dish in
                let labels = dish.labels.map { "\($0.key.rawValue)=\($0.value)" }.sorted().joined(separator: ",")
                return [dish.dish, dish.description, labels].joined(separator: "\u{1}")
            }.sorted()
            if seen.insert(fingerprint).inserted { kept += menu }
        }
        return kept
    }

    private struct Row: Decodable {
        struct Named: Decodable { let name: String }
        struct Link: Decodable {
            let level: String?
            let allergens: Named?
        }
        let name: String
        let description: String?
        let restaurants: Named?
        let menu_item_allergens: [Link]?
    }

    private static func load(_ request: URLRequest) async throws -> (Data, URLResponse) {
        try await withCheckedThrowingContinuation { continuation in
            URLSession.shared.dataTask(with: request) { data, response, error in
                if let error {
                    continuation.resume(throwing: error)
                } else if let data, let response {
                    continuation.resume(returning: (data, response))
                } else {
                    continuation.resume(throwing: ExportError(description: "empty response"))
                }
            }.resume()
        }
    }
}
