import SwiftUI

struct EditAllergiesView: View {
    @State private var selectedAllergens: Set<String> = []
    @Environment(\.dismiss) private var dismiss
    
    let allergens = [
        "Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts",
        "Soybeans", "Milk", "Nuts", "Celery", "Mustard",
        "Sesame", "Sulphur Dioxide", "Lupin", "Molluscs"
    ]
    
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Select all allergens that apply to you. This will be used to filter menus.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                
                Section {
                    ForEach(allergens, id: \.self) { allergen in
                        AllergenRow(
                            name: allergen,
                            isSelected: selectedAllergens.contains(allergen)
                        ) {
                            if selectedAllergens.contains(allergen) {
                                selectedAllergens.remove(allergen)
                            } else {
                                selectedAllergens.insert(allergen)
                            }
                        }
                    }
                } header: {
                    Text("Allergens")
                }
            }
            .navigationTitle("Edit Allergies")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") {
                        let allergenArray = Array(selectedAllergens)
                        UserDefaults.standard.set(allergenArray, forKey: "guestAllergens")
                        dismiss()
                    }
                    .fontWeight(.semibold)
                    .foregroundStyle(Color.navy)
                }
            }
            .onAppear {
                let saved = UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []
                selectedAllergens = Set(saved)
            }
        }
    }
}

#Preview {
    EditAllergiesView()
}
