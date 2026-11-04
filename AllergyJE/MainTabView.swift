import SwiftUI

struct MainTabView: View {
    @State private var selectedTab = 0
    @State private var showEditAllergies = false
    
    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView(selectedTab: $selectedTab, showEditAllergies: $showEditAllergies)
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(0)

            MenuScanView()
                .tabItem {
                    Label("Scan", systemImage: "camera.viewfinder")
                }
                .tag(2)

            ProfileView(showEditAllergies: $showEditAllergies)
                .tabItem {
                    Label("Profile", systemImage: "person.fill")
                }
                .tag(1)
        }
        .tint(Color.navy)
    }
}

#Preview {
    MainTabView()
}
