import SwiftUI

struct OnboardingView: View {
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var currentPage = 0
    @State private var selectedAllergens: Set<String> = []
    
    var body: some View {
        TabView(selection: $currentPage) {
            WelcomeScreen(currentPage: $currentPage)
                .tag(0)
            
            AllergenSelectionScreen(
                selectedAllergens: $selectedAllergens,
                currentPage: $currentPage
            )
            .tag(1)
            
            OnboardingCompleteScreen(
                selectedAllergens: selectedAllergens,
                hasCompletedOnboarding: $hasCompletedOnboarding
            )
            .tag(2)
        }
        .tabViewStyle(.page(indexDisplayMode: .never))
        .animation(.easeInOut, value: currentPage)
        .ignoresSafeArea()
    }
}

#Preview {
    OnboardingView()
}
