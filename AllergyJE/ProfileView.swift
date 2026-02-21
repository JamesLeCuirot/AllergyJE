import SwiftUI

struct ProfileView: View {
    @Binding var showEditAllergies: Bool
    @State private var subscriptionManager = SubscriptionManager.shared
    @State private var showPaywall = false
    @State private var showCustomerCenter = false
    @State private var appeared = false
    @State private var userAllergens: [String] = UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []

    var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {

                    SubscriptionCard(
                        isSubscribed: subscriptionManager.isSubscribed,
                        onUpgrade: { showPaywall = true },
                        onManage: { showCustomerCenter = true }
                    )
                    .offset(y: appeared ? 0 : 30)
                    .opacity(appeared ? 1 : 0)
                    .animation(.spring(duration: 0.5).delay(0.1), value: appeared)

                    AllergiesCard(
                        allergens: userAllergens,
                        onEdit: { showEditAllergies = true }
                    )
                    .offset(y: appeared ? 0 : 30)
                    .opacity(appeared ? 1 : 0)
                    .animation(.spring(duration: 0.5).delay(0.2), value: appeared)

                    AboutCard(appVersion: appVersion)
                        .offset(y: appeared ? 0 : 30)
                        .opacity(appeared ? 1 : 0)
                        .animation(.spring(duration: 0.5).delay(0.3), value: appeared)

                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange)
                            .font(.caption)
                        Text("Allergy.je is a guide only. Always inform restaurant staff of your allergies. We cannot guarantee accuracy of all information.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(14)
                    .background(Color.orange.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal, 16)
                    .offset(y: appeared ? 0 : 30)
                    .opacity(appeared ? 1 : 0)
                    .animation(.spring(duration: 0.5).delay(0.4), value: appeared)

                    Spacer(minLength: 32)
                }
                .padding(.top, 8)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.large)
            .onReceive(NotificationCenter.default.publisher(for: UserDefaults.didChangeNotification)) { _ in
                userAllergens = UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? []
            }
            .onAppear {
                withAnimation {
                    appeared = true
                }
            }
            .sheet(isPresented: $showPaywall) {
                PaywallView()
            }
            .sheet(isPresented: $showCustomerCenter) {
                CustomerCenterView()
            }
            .sheet(isPresented: $showEditAllergies) {
                EditAllergiesView()
            }
        }
    }
}

// MARK: - Subscription Card
struct SubscriptionCard: View {
    let isSubscribed: Bool
    let onUpgrade: () -> Void
    let onManage: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 14) {
                ZStack {
                    Circle()
                        .fill(isSubscribed ? Color.navy : Color(.tertiarySystemGroupedBackground))
                        .frame(width: 52, height: 52)
                    Image(systemName: isSubscribed ? "checkmark.circle.fill" : "person.circle.fill")
                        .font(.title2)
                        .foregroundStyle(isSubscribed ? .white : Color.navy)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(isSubscribed ? "Allergy.je Pro" : "Free Plan")
                        .font(.headline)
                    Text(isSubscribed ? "Full access to all restaurants" : "Limited to free restaurants")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if isSubscribed {
                    Text("PRO")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(Color.navy)
                        .clipShape(Capsule())
                }
            }
            .padding(18)

            Divider()
                .padding(.horizontal, 18)

            if isSubscribed {
                Button(action: onManage) {
                    HStack {
                        Image(systemName: "gear")
                            .foregroundStyle(Color.navy)
                        Text("Manage Subscription")
                            .foregroundStyle(.primary)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(18)
                }
            } else {
                Button(action: onUpgrade) {
                    HStack(spacing: 12) {
                        ZStack {
                            Circle()
                                .fill(.yellow.opacity(0.15))
                                .frame(width: 34, height: 34)
                            Image(systemName: "star.fill")
                                .font(.subheadline)
                                .foregroundStyle(.yellow)
                        }

                        VStack(alignment: .leading, spacing: 1) {
                            Text("Upgrade to Pro")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundStyle(Color.navy)
                            Text("Access all restaurants · £1.99/month")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(Color.navy.opacity(0.5))
                    }
                    .padding(18)
                    .background(Color.navy.opacity(0.05))
                }
            }
        }
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .shadow(color: .black.opacity(0.05), radius: 8, y: 2)
        .padding(.horizontal, 16)
    }
}

// MARK: - Allergies Card
struct AllergiesCard: View {
    let allergens: [String]
    let onEdit: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                HStack(spacing: 8) {
                    Image(systemName: "allergens")
                        .font(.subheadline)
                        .foregroundStyle(Color.navy)
                    Text("My Allergies")
                        .font(.headline)
                    if !allergens.isEmpty {
                        Text("\(allergens.count)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3)
                            .background(Color.navy)
                            .clipShape(Capsule())
                    }
                }
                Spacer()
                Button(action: onEdit) {
                    Text("Edit")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(Color.navy)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .background(Color.navy.opacity(0.1))
                        .clipShape(Capsule())
                }
            }
            .padding(18)
        }
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .shadow(color: .black.opacity(0.05), radius: 8, y: 2)
        .padding(.horizontal, 16)
    }
}

// MARK: - About Card
struct AboutCard: View {
    let appVersion: String

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("About")
                    .font(.headline)
                Spacer()
            }
            .padding(18)

            Divider()
                .padding(.horizontal, 18)

            VStack(spacing: 0) {
                AboutRow(icon: "info.circle", label: "Version", value: appVersion)

                Divider().padding(.leading, 52)

                Link(destination: URL(string: "https://allergy.je/privacy")!) {
                    AboutLinkRow(icon: "hand.raised.fill", label: "Privacy Policy")
                }

                Divider().padding(.leading, 52)

                Link(destination: URL(string: "https://allergy.je/terms")!) {
                    AboutLinkRow(icon: "doc.text.fill", label: "Terms of Use")
                }

                Divider().padding(.leading, 52)

                Link(destination: URL(string: "mailto:hello@allergy.je")!) {
                    AboutLinkRow(icon: "envelope.fill", label: "Contact Us")
                }
            }
        }
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .shadow(color: .black.opacity(0.05), radius: 8, y: 2)
        .padding(.horizontal, 16)
    }
}

struct AboutRow: View {
    let icon: String
    let label: String
    let value: String

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 7)
                    .fill(Color.navy.opacity(0.1))
                    .frame(width: 30, height: 30)
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(Color.navy)
            }
            Text(label)
                .font(.subheadline)
            Spacer()
            Text(value)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
    }
}

struct AboutLinkRow: View {
    let icon: String
    let label: String

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 7)
                    .fill(Color.navy.opacity(0.1))
                    .frame(width: 30, height: 30)
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(Color.navy)
            }
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.primary)
            Spacer()
            Image(systemName: "arrow.up.right")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
    }
}

#Preview {
    ProfileView(showEditAllergies: .constant(false))
}
