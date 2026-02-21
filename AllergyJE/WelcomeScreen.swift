import SwiftUI

struct WelcomeScreen: View {
    @Binding var currentPage: Int
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color.navy, Color.navy.opacity(0.8)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 0) {
                Spacer()
                
                // Icon
                ZStack {
                    Circle()
                        .fill(.white.opacity(0.15))
                        .frame(width: 120, height: 120)
                    
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 60))
                        .foregroundStyle(.white)
                }
                .padding(.bottom, 40)
                
                // Title
                Text("Allergy.je")
                    .font(.system(size: 42, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                
                Text("Eat safely across Jersey")
                    .font(.title3)
                    .foregroundStyle(.white.opacity(0.8))
                    .padding(.top, 8)
                
                // Features
                VStack(alignment: .leading, spacing: 16) {
                    WelcomeFeatureRow(icon: "location.fill", text: "Detects which restaurant you're in")
                    WelcomeFeatureRow(icon: "menucard.fill", text: "Shows menus filtered for your allergies")
                    WelcomeFeatureRow(icon: "checkmark.shield.fill", text: "Based on verified allergen data")
                }
                .padding(24)
                .background(.white.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .padding(.horizontal, 24)
                .padding(.top, 48)
                
                Spacer()
                
                // Get started button
                Button {
                    withAnimation {
                        currentPage = 1
                    }
                } label: {
                    Text("Get Started")
                        .font(.headline)
                        .foregroundStyle(Color.navy)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                        .padding(.horizontal, 24)
                }
                
                Text("No account required")
                    .font(.footnote)
                    .foregroundStyle(.white.opacity(0.6))
                    .padding(.top, 12)
                    .padding(.bottom, 48)
            }
        }
    }
}

struct WelcomeFeatureRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(.white)
                .frame(width: 28)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.9))
            Spacer()
        }
    }
}

#Preview {
    WelcomeScreen(currentPage: .constant(0))
}
