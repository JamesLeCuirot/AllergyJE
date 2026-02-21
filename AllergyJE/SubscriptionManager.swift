import SwiftUI
import RevenueCat

@Observable
class SubscriptionManager {
    
    static let shared = SubscriptionManager()
    
    var isSubscribed: Bool = false
    var customerInfo: CustomerInfo?
    var currentOffering: Offering?
    var isLoading: Bool = false
    var errorMessage: String?
    
    private let entitlementID = "AllergyJE Pro"
    
    init() {
        Task {
            await fetchCustomerInfo()
            await fetchOfferings()
        }
    }
    
    // MARK: - Fetch Customer Info
    func fetchCustomerInfo() async {
        do {
            let info = try await Purchases.shared.customerInfo()
            await MainActor.run {
                self.customerInfo = info
                self.isSubscribed = info.entitlements[entitlementID]?.isActive == true
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    // MARK: - Fetch Offerings
    func fetchOfferings() async {
        do {
            let offerings = try await Purchases.shared.offerings()
            await MainActor.run {
                self.currentOffering = offerings.current
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    // MARK: - Purchase Package
    func purchase(package: Package) async -> Bool {
        await MainActor.run { isLoading = true }
        defer { Task { await MainActor.run { self.isLoading = false } } }
        
        do {
            let result = try await Purchases.shared.purchase(package: package)
            await MainActor.run {
                self.customerInfo = result.customerInfo
                self.isSubscribed = result.customerInfo.entitlements[entitlementID]?.isActive == true
            }
            return !result.userCancelled
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
            return false
        }
    }
    
    // MARK: - Restore Purchases
    func restorePurchases() async {
        await MainActor.run { isLoading = true }
        defer { Task { await MainActor.run { self.isLoading = false } } }
        
        do {
            let info = try await Purchases.shared.restorePurchases()
            await MainActor.run {
                self.customerInfo = info
                self.isSubscribed = info.entitlements[entitlementID]?.isActive == true
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
        }
    }
    
    // MARK: - Check Entitlement
    var hasProAccess: Bool {
        customerInfo?.entitlements[entitlementID]?.isActive == true
    }
}
