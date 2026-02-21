import SwiftUI
import RevenueCat

struct CustomerCenterView: View {
    @State private var subscriptionManager = SubscriptionManager.shared
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        Text("Status")
                        Spacer()
                        Text(subscriptionManager.isSubscribed ? "Pro" : "Free")
                            .foregroundStyle(subscriptionManager.isSubscribed ? .blue : .secondary)
                            .fontWeight(.semibold)
                    }
                } header: {
                    Text("Subscription")
                }
                
                Section {
                    Button("Restore Purchases") {
                        Task {
                            await subscriptionManager.restorePurchases()
                        }
                    }
                } header: {
                    Text("Manage")
                }
                
                Section {
                    Link("Manage in App Store", destination: URL(string: "https://apps.apple.com/account/subscriptions")!)
                }
            }
            .navigationTitle("Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

#Preview {
    CustomerCenterView()
}
