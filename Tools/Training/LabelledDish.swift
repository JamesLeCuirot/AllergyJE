import Foundation
import MenuEngine

/// What a restaurant's allergen information says about one allergen in one dish.
public enum AllergenLabel: String, Sendable, Codable {
    case contains
    /// "May contain" / traces / cross-contact. Not something the menu wording can reveal,
    /// so it is neither a miss nor a false alarm when scoring.
    case mayContain
}

/// A dish with the allergen information its restaurant published. This is the ground
/// truth for scoring the predictor and learning new rules.
public struct LabelledDish: Equatable, Sendable {
    public var source: String
    public var restaurant: String
    public var dish: String
    public var description: String
    /// Allergens the restaurant lists. An allergen that isn't listed isn't in the dish.
    public var labels: [UKAllergen: AllergenLabel]

    public init(source: String = "", restaurant: String = "", dish: String, description: String = "", labels: [UKAllergen: AllergenLabel]) {
        self.source = source
        self.restaurant = restaurant
        self.dish = dish
        self.description = description
        self.labels = labels
    }

    /// The text a menu would show, as the predictor reads it.
    public var text: String {
        description.isEmpty ? dish : "\(dish) \(description)"
    }
}

/// Reads and writes dishes as CSV: one row per dish, one column per allergen.
///
///     source,restaurant,dish,description,Gluten,Crustaceans,Eggs,…
///     Example Café menu 2026,Example Café,Fish Pie,"Cod, prawns, mash",Y,Y,,Y,…
///
/// Allergen cells: `Y` contains, `M` may contain, blank or `N` doesn't contain. Column
/// names are matched loosely ("Soya", "Sulphites" and "Tree nuts" all work), so a
/// restaurant's own allergen chart can usually be saved as CSV and used as it is.
public enum DishDataset {
    public struct ReadError: Error, CustomStringConvertible, Equatable {
        public let line: Int
        public let message: String
        public var description: String { "line \(line): \(message)" }
    }

    public static var header: [String] {
        ["source", "restaurant", "dish", "description"] + UKAllergen.allCases.map(\.rawValue)
    }

    /// Loads every `.csv` file in a folder, or a single file.
    public static func load(_ url: URL) throws -> [LabelledDish] {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory) else { return [] }
        let files = isDirectory.boolValue
            ? try FileManager.default.contentsOfDirectory(at: url, includingPropertiesForKeys: nil)
                .filter { $0.pathExtension.lowercased() == "csv" }
                .sorted { $0.lastPathComponent < $1.lastPathComponent }
            : [url]
        return try files.flatMap { file in
            do {
                return try read(csv: String(contentsOf: file, encoding: .utf8))
            } catch let error as ReadError {
                throw ReadError(line: error.line, message: "\(file.lastPathComponent): \(error.message)")
            }
        }
    }

    public static func read(csv text: String) throws -> [LabelledDish] {
        let rows = rows(in: text)
        guard let headerRow = rows.first else { return [] }

        var fieldColumns: [String: Int] = [:]
        var allergenColumns: [(column: Int, allergen: UKAllergen)] = []
        for (column, name) in headerRow.enumerated() {
            let key = name.lowercased().filter(\.isLetter)
            if let field = fieldAliases[key] {
                fieldColumns[field] = column
            } else if let allergen = allergenAliases[key] {
                allergenColumns.append((column, allergen))
            }
        }
        guard fieldColumns["dish"] != nil else {
            throw ReadError(line: 1, message: "no 'dish' column in the header")
        }
        if allergenColumns.isEmpty {
            throw ReadError(line: 1, message: "no allergen columns in the header")
        }

        var dishes: [LabelledDish] = []
        for (offset, row) in rows.dropFirst().enumerated() {
            let line = offset + 2
            func field(_ name: String) -> String {
                guard let column = fieldColumns[name], column < row.count else { return "" }
                return row[column].trimmingCharacters(in: .whitespacesAndNewlines)
            }
            let name = field("dish")
            guard !name.isEmpty else { continue }

            var labels: [UKAllergen: AllergenLabel] = [:]
            for (column, allergen) in allergenColumns {
                let cell = column < row.count ? row[column] : ""
                guard let value = cellValues[cell.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()] else {
                    throw ReadError(line: line, message: "can't read '\(cell)' for \(allergen.rawValue); use Y, M or leave blank")
                }
                if let value {
                    // Two columns for one allergen (e.g. Gluten and Wheat): keep the stronger.
                    labels[allergen] = labels[allergen] == .contains ? .contains : value
                }
            }
            dishes.append(LabelledDish(source: field("source"), restaurant: field("restaurant"), dish: name, description: field("description"), labels: labels))
        }
        return dishes
    }

    public static func csv(from dishes: [LabelledDish]) -> String {
        var lines = [header.map(escape).joined(separator: ",")]
        for dish in dishes {
            let cells = [dish.source, dish.restaurant, dish.dish, dish.description] + UKAllergen.allCases.map { allergen in
                switch dish.labels[allergen] {
                case .contains: "Y"
                case .mayContain: "M"
                case nil: ""
                }
            }
            lines.append(cells.map(escape).joined(separator: ","))
        }
        return lines.joined(separator: "\n") + "\n"
    }

    // MARK: CSV

    /// Splits CSV text into rows of fields (RFC 4180: quoted fields, "" escapes, line breaks inside quotes).
    static func rows(in text: String) -> [[String]] {
        var rows: [[String]] = []
        var row: [String] = []
        var field = ""
        var inQuotes = false
        var characters = Array(text)
        if characters.first == "\u{FEFF}" { characters.removeFirst() } // Excel's byte-order mark

        var index = 0
        while index < characters.count {
            let character = characters[index]
            if inQuotes {
                if character == "\"" {
                    if index + 1 < characters.count, characters[index + 1] == "\"" {
                        field.append("\"")
                        index += 1
                    } else {
                        inQuotes = false
                    }
                } else {
                    field.append(character)
                }
            } else if character == "\"" {
                inQuotes = true
            } else if character == "," {
                row.append(field)
                field = ""
            } else if character.isNewline {
                row.append(field)
                rows.append(row)
                row = []
                field = ""
            } else {
                field.append(character)
            }
            index += 1
        }
        if !field.isEmpty || !row.isEmpty {
            row.append(field)
            rows.append(row)
        }
        return rows.filter { !($0.count == 1 && $0[0].trimmingCharacters(in: .whitespaces).isEmpty) }
    }

    private static func escape(_ value: String) -> String {
        guard value.contains(where: { $0 == "," || $0 == "\"" || $0.isNewline }) else { return value }
        return "\"" + value.replacingOccurrences(of: "\"", with: "\"\"") + "\""
    }

    private static let fieldAliases: [String: String] = [
        "source": "source",
        "restaurant": "restaurant", "venue": "restaurant",
        "dish": "dish", "name": "dish", "dishname": "dish", "item": "dish", "menuitem": "dish",
        "description": "description", "details": "description",
    ]

    private static let allergenAliases: [String: UKAllergen] = [
        "gluten": .gluten, "cerealscontaininggluten": .gluten, "wheat": .gluten,
        "crustaceans": .crustaceans, "crustacean": .crustaceans,
        "eggs": .eggs, "egg": .eggs,
        "fish": .fish,
        "peanuts": .peanuts, "peanut": .peanuts,
        "soybeans": .soybeans, "soybean": .soybeans, "soya": .soybeans, "soy": .soybeans, "soyabeans": .soybeans,
        "milk": .milk, "dairy": .milk,
        "nuts": .nuts, "nut": .nuts, "treenuts": .nuts, "treenut": .nuts,
        "celery": .celery, "celeriac": .celery,
        "mustard": .mustard,
        "sesame": .sesame, "sesameseeds": .sesame,
        "sulphurdioxide": .sulphites, "sulphites": .sulphites, "sulfites": .sulphites, "sulphurdioxidesulphites": .sulphites, "so": .sulphites,
        "lupin": .lupin, "lupine": .lupin,
        "molluscs": .molluscs, "mollusc": .molluscs, "mollusks": .molluscs,
    ]

    /// nil value means "doesn't contain"; a missing key means the cell couldn't be read.
    private static let cellValues: [String: AllergenLabel?] = [
        "": .none, "n": .none, "no": .none, "0": .none, "false": .none, "-": .none, "–": .none,
        "y": .contains, "yes": .contains, "x": .contains, "✓": .contains, "✔": .contains, "1": .contains, "true": .contains, "contains": .contains, "c": .contains,
        "m": .mayContain, "may": .mayContain, "may contain": .mayContain, "trace": .mayContain, "traces": .mayContain, "mc": .mayContain,
    ]
}
