import SwiftUI

struct OnboardingCompleteScreen: View {
    let selectedAllergens: Set<String>
    @Binding var hasCompletedOnboarding: Bool
    
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color.navy, Color.navy.opacity(0.8)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 0) {
                Spacer()
                
                // Checkmark animation
                ZStack {
                    Circle()
                        .fill(.white.opacity(0.15))
                        .frame(width: 120, height: 120)
                    
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 60))
                        .foregroundStyle(.white)
                }
                .padding(.bottom, 32)
                
                Text("You're all set!")
                    .font(.system(size: 36, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                
                if selectedAllergens.isEmpty {
                    Text("No allergies selected. You can update this anytime in settings.")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.8))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                        .padding(.top, 12)
                } else {
                    Text("We'll filter menus based on your \(selectedAllergens.count) allergen\(selectedAllergens.count == 1 ? "" : "s").")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.8))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                        .padding(.top, 12)
                    
                    // Selected allergens summary
                    FlowLayout(items: Array(selectedAllergens).sorted())
                        .padding(.horizontal, 24)
                        .padding(.top, 24)
                }
                
                Spacer()
                
                // Disclaimer
                Text("⚠️ Always inform restaurant staff of your allergies. This app is a guide only and does not replace professional advice.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.7))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
                    .padding(.bottom, 24)
                
                // Start button
                Button {
                    // Save allergens to UserDefaults for guest users
                    let allergenArray = Array(selectedAllergens)
                    UserDefaults.standard.set(allergenArray, forKey: "guestAllergens")
                    hasCompletedOnboarding = true
                } label: {
                    Text("Start Exploring")
                        .font(.headline)
                        .foregroundStyle(Color.navy)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                        .padding(.horizontal, 24)
                }
                .padding(.bottom, 48)
            }
        }
    }
}

// Simple flow layout for allergen tags
struct FlowLayout: View {
    let items: [String]
    
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100))], spacing: 8) {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(.white.opacity(0.2))
                    .clipShape(Capsule())
            }
        }
    }
}

#Preview {
    OnboardingCompleteScreen(
        selectedAllergens: ["Gluten", "Milk", "Eggs"],
        hasCompletedOnboarding: .constant(false)
    )
}
