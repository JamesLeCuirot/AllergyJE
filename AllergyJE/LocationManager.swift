import CoreLocation
import SwiftUI

@Observable
class LocationManager: NSObject, CLLocationManagerDelegate {
    
    static let shared = LocationManager()
    
    private let manager = CLLocationManager()
    
    var userLocation: CLLocation?
    var authorizationStatus: CLAuthorizationStatus = .notDetermined
    var nearbyRestaurants: [Restaurant] = []
    var isSearching = false
    var errorMessage: String?
    
    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
    }
    
    func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }
    
    func startUpdating() {
        manager.startUpdatingLocation()
    }
    
    func stopUpdating() {
        manager.stopUpdatingLocation()
    }
    
    // MARK: - CLLocationManagerDelegate
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        userLocation = locations.last
    }
    
    func locationManager(_ manager: CLLocationManager, didChangeAuthorization status: CLAuthorizationStatus) {
        authorizationStatus = status
        if status == .authorizedWhenInUse || status == .authorizedAlways {
            startUpdating()
        }
    }
    
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        errorMessage = error.localizedDescription
    }
    
    // MARK: - Find nearby restaurants from our database
    func findNearbyRestaurants(allRestaurants: [Restaurant]) {
        guard let userLocation else { return }
        
        // Filter restaurants within 100 metres
        nearbyRestaurants = allRestaurants.filter { restaurant in
            guard let lat = restaurant.latitude, let lon = restaurant.longitude else { return false }
            let restaurantLocation = CLLocation(latitude: lat, longitude: lon)
            return restaurantLocation.distance(from: userLocation) < 100
        }.sorted { a, b in
            guard let aLat = a.latitude, let aLon = a.longitude,
                  let bLat = b.latitude, let bLon = b.longitude else { return false }
            let aLocation = CLLocation(latitude: aLat, longitude: aLon)
            let bLocation = CLLocation(latitude: bLat, longitude: bLon)
            return aLocation.distance(from: userLocation) < bLocation.distance(from: userLocation)
        }
    }
}
