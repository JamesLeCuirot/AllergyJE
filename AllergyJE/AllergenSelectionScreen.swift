import SwiftUI

struct AllergenSelectionScreen: View {
    @Binding var selectedAllergens: Set<String>
    @Binding var currentPage: Int
    
    let allergens = [
        ("Gluten", "wheat"),
        ("Crustaceans", "allergens"),
        ("Eggs", "allergens"),
        ("Fish", "fish"),
        ("Peanuts", "allergens"),
        ("Soybeans", "allergens"),
        ("Milk", "cup.and.saucer.fill"),
        ("Nuts", "allergens"),
        ("Celery", "leaf.fill"),
        ("Mustard", "allergens"),
        ("Sesame", "allergens"),
        ("Sulphur Dioxide", "aqi.medium"),
        ("Lupin", "allergens"),
        ("Molluscs", "allergens")
    ]
    
    var body: some View {
        NavigationStack {
            ZStack {
                Color(.systemBackground)
                    .ignoresSafeArea()
                
                VStack(spacing: 0) {
                    // Header
                    VStack(spacing: 8) {
                        Text("Your Allergies")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        Text("Select everything you're allergic or intolerant to. You can change this later in settings.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 24)
                    }
                    .padding(.top, 24)
                    .padding(.bottom, 16)
                    
                    // Allergen list
                    List {
                        ForEach(allergens, id: \.0) { allergen, icon in
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
                    }
                    .listStyle(.insetGrouped)
                    
                    // Continue button
                    VStack(spacing: 8) {
                        Button {
                            withAnimation {
                                currentPage = 2
                            }
                        } label: {
                            Text(selectedAllergens.isEmpty ? "I have no allergies" : "Continue")
                                .font(.headline)
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(Color.navy)
                                .clipShape(RoundedRectangle(cornerRadius: 14))
                                .padding(.horizontal, 24)
                        }
                        
                        if !selectedAllergens.isEmpty {
                            Text("\(selectedAllergens.count) selected")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 16)
                    .background(Color(.systemBackground))
                }
            }
        }
    }
}

struct AllergenRow: View {
    let name: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Text(name)
                    .font(.body)
                    .foregroundStyle(.primary)
                
                Spacer()
                
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(isSelected ? Color.navy : .secondary)
                    .animation(.spring(duration: 0.2), value: isSelected)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    AllergenSelectionScreen(
        selectedAllergens: .constant(["Gluten", "Milk"]),
        currentPage: .constant(1)
    )
}
