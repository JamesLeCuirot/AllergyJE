import SwiftUI
import Supabase
import RevenueCat

let supabase = SupabaseClient(
    supabaseURL: URL(string: "https://jyreijzgwjwgztfuswzu.supabase.co")!,
    supabaseKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5cmVpanpnd2p3Z3p0ZnVzd3p1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2ODUyNzMsImV4cCI6MjA4NzI2MTI3M30.N4_T0BpHPRutn17J7nlbkkSczrYn3sht6Jke5yQMtWE"
)

@main
struct AllergyJEApp: App {
    
    @State private var subscriptionManager = SubscriptionManager.shared
    
    init() {
        Purchases.configure(withAPIKey: "test_XRSxSvaRiDnyBJDqqsgGQXvfhUm")
        Purchases.logLevel = .debug
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.light)
                .environment(subscriptionManager)
        }
    }
}
