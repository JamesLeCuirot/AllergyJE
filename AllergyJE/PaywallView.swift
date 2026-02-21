import SwiftUI
import RevenueCat

struct PaywallView: View {
    @State private var subscriptionManager = SubscriptionManager.shared
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        ZStack {
            Color(.systemGroupedBackground)
                .ignoresSafeArea()
            
            if let offering = subscriptionManager.currentOffering {
                ScrollView {
                    VStack(spacing: 24) {
                        
                        // Header
                        VStack(spacing: 16) {
                            ZStack {
                                Circle()
                                    .fill(Color.navy.opacity(0.1))
                                    .frame(width: 100, height: 100)
                                Circle()
                                    .fill(Color.navy.opacity(0.07))
                                    .frame(width: 76, height: 76)
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 44))
                                    .foregroundStyle(Color.navy)
                            }
                            .padding(.top, 40)
                            
                            VStack(spacing: 8) {
                                Text("Allergy.je Pro")
                                    .font(.largeTitle)
                                    .fontWeight(.bold)
                                
                                Text("Filter menus and eat safely across all of Jersey")
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal, 32)
                            }
                        }
                        
                        // Features
                        VStack(alignment: .leading, spacing: 0) {
                            FeatureRow(
                                icon: "eye.fill",
                                iconColor: Color.navy,
                                title: "Filter menus",
                                subtitle: "See exactly what you can safely eat"
                            )
                            Divider().padding(.leading, 56)
                            FeatureRow(
                                icon: "building.2.fill",
                                iconColor: Color.navy,
                                title: "All restaurants",
                                subtitle: "Access every restaurant in Jersey"
                            )
                            Divider().padding(.leading, 56)
                            FeatureRow(
                                icon: "menucard.fill",
                                iconColor: Color.navy,
                                title: "Full menus",
                                subtitle: "Complete menus with allergen detail"
                            )
                            Divider().padding(.leading, 56)
                            FeatureRow(
                                icon: "checkmark.shield.fill",
                                iconColor: Color.navy,
                                title: "Verified allergen data",
                                subtitle: "Information verified with restaurants"
                            )
                        }
                        .background(Color(.secondarySystemGroupedBackground))
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .padding(.horizontal, 20)
                        
                        // Packages
                        VStack(spacing: 12) {
                            ForEach(offering.availablePackages, id: \.identifier) { package in
                                PackageButton(package: package)
                            }
                        }
                        .padding(.horizontal, 20)
                        
                        // Restore purchases
                        Button("Restore Purchases") {
                            Task {
                                await subscriptionManager.restorePurchases()
                                if subscriptionManager.isSubscribed {
                                    dismiss()
                                }
                            }
                        }
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        
                        Text("Subscriptions auto-renew unless cancelled. Manage in App Store settings.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 32)
                            .padding(.bottom, 40)
                    }
                }
            } else {
                VStack(spacing: 16) {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Loading plans...")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            
            if subscriptionManager.isLoading {
                Color.black.opacity(0.4)
                    .ignoresSafeArea()
                ProgressView()
                    .tint(.white)
                    .scaleEffect(1.5)
            }
        }
        .overlay(alignment: .topTrailing) {
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.title2)
                    .foregroundStyle(.secondary)
                    .padding()
            }
        }
        .alert("Error", isPresented: .constant(subscriptionManager.errorMessage != nil)) {
            Button("OK") { subscriptionManager.errorMessage = nil }
        } message: {
            Text(subscriptionManager.errorMessage ?? "")
        }
    }
}

// MARK: - Feature Row
struct FeatureRow: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
    
    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(iconColor.opacity(0.1))
                    .frame(width: 36, height: 36)
                Image(systemName: icon)
                    .font(.subheadline)
                    .foregroundStyle(iconColor)
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

// MARK: - Package Button
struct PackageButton: View {
    let package: Package
    @State private var subscriptionManager = SubscriptionManager.shared
    @Environment(\.dismiss) private var dismiss
    
    var packageLabel: String {
        switch package.identifier {
        case "$rc_monthly": return "Monthly"
        case "$rc_annual": return "Annual"
        case "monthly": return "Monthly"
        case "annual": return "Annual"
        case "yearly": return "Yearly"
        default: return "Monthly"
        }
    }
    
    var isAnnual: Bool {
        package.identifier.contains("annual") || package.identifier.contains("yearly")
    }
    
    var body: some View {
        Button {
            Task {
                let success = await subscriptionManager.purchase(package: package)
                if success {
                    dismiss()
                }
            }
        } label: {
            HStack(spacing: 14) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(packageLabel)
                            .font(.headline)
                            .foregroundStyle(.primary)
                        
                        if isAnnual {
                            Text("Best Value")
                                .font(.caption2)
                                .fontWeight(.bold)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 7)
                                .padding(.vertical, 3)
                                .background(Color.navy)
                                .clipShape(Capsule())
                        }
                    }
                    
                    Text(package.storeProduct.localizedPriceString + (isAnnual ? " / year" : " / month"))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(16)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(isAnnual ? Color.navy.opacity(0.4) : Color(.separator), lineWidth: isAnnual ? 1.5 : 1)
            )
        }
    }
}

#Preview {
    PaywallView()
}
