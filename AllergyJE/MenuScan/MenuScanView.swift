import AVFoundation
import PhotosUI
import SwiftUI
import VisionKit

extension UKAllergen {
    /// The allergens the user picked during onboarding or in Profile.
    static var saved: Set<UKAllergen> {
        set(from: UserDefaults.standard.stringArray(forKey: "guestAllergens") ?? [])
    }
}

/// Point the camera at any menu, or pick a photo of one, and see which dishes
/// show no sign of the user's allergens.
struct MenuScanView: View {
    private enum CameraState { case checking, ready, unavailable, denied }

    @State private var model = LiveScanModel()
    @State private var cameraState: CameraState = .checking
    @State private var isVisible = false
    @State private var allergens: Set<UKAllergen> = UKAllergen.saved
    @State private var pickerItem: PhotosPickerItem?
    @State private var reviewing: ScannedMenu?
    @State private var selectedDish: ScannedDish?
    @State private var isProcessing = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()
                camera
            }
            .safeAreaInset(edge: .top, spacing: 0) { statusBanner }
            .safeAreaInset(edge: .bottom, spacing: 0) { controls }
            .overlay { if isProcessing { processingOverlay } }
            .navigationTitle("Scan a Menu")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.black, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .navigationDestination(item: $reviewing) { menu in
                ScannedMenuReview(menu: menu, allergens: allergens)
            }
            .sheet(item: $selectedDish) { dish in
                DishDetailSheet(dish: dish, allergens: allergens)
            }
            .alert("Couldn't read the menu", isPresented: Binding(
                get: { errorMessage != nil },
                set: { if !$0 { errorMessage = nil } }
            )) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(errorMessage ?? "")
            }
            .onAppear {
                isVisible = true
                allergens = UKAllergen.saved
            }
            .onDisappear { isVisible = false }
            .onReceive(NotificationCenter.default.publisher(for: UserDefaults.didChangeNotification)) { _ in
                allergens = UKAllergen.saved
            }
            .onChange(of: pickerItem) { _, item in
                guard let item else { return }
                pickerItem = nil
                Task { await loadPhoto(item) }
            }
            .task { await checkCamera() }
        }
    }

    // MARK: Camera

    @ViewBuilder
    private var camera: some View {
        switch cameraState {
        case .checking:
            ProgressView().tint(.white)
        case .ready:
            // Only keep the camera running while this screen is on show.
            if isVisible && reviewing == nil {
                LiveMenuScanner(model: model)
                    .ignoresSafeArea()
                    .overlay {
                        AllergenOverlay(dishes: model.dishes, allergens: allergens, place: { $0 }) { dish in
                            selectedDish = dish
                        }
                        .ignoresSafeArea()
                    }
            }
        case .unavailable:
            CameraMessage(
                icon: "camera.metering.unknown",
                title: "Live scanning isn't available here",
                message: "It needs an iPhone or iPad camera. You can still choose a photo of a menu."
            )
        case .denied:
            CameraMessage(
                icon: "camera.fill",
                title: "Camera access is off",
                message: "Turn on camera access in Settings to scan menus live, or choose a photo instead.",
                showsSettingsLink: true
            )
        }
    }

    private func checkCamera() async {
        guard DataScannerViewController.isSupported else {
            cameraState = .unavailable
            return
        }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            cameraState = DataScannerViewController.isAvailable ? .ready : .unavailable
        case .notDetermined:
            cameraState = await AVCaptureDevice.requestAccess(for: .video) ? .ready : .denied
        default:
            cameraState = .denied
        }
    }

    // MARK: Banner and controls

    private var statusBanner: some View {
        VStack(spacing: 4) {
            Text(statusText)
                .font(.subheadline.weight(.semibold))
                .multilineTextAlignment(.center)
            Text("Predicted from the menu's wording. Always check with staff.")
                .font(.caption2)
                .opacity(0.75)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity)
        .background(.black.opacity(0.65))
    }

    private var statusText: String {
        if allergens.isEmpty {
            return "Add your allergies in Profile so we know what to look for"
        }
        guard cameraState == .ready else {
            return "Choose a photo of a menu to check it"
        }
        let dishes = model.dishes.filter(\.isDish)
        if dishes.isEmpty {
            return "Point your camera at a menu"
        }
        let clear = dishes.filter { $0.verdict(for: allergens) == .noIndicators }.count
        return "\(clear) of \(dishes.count) dishes show no sign of your allergens"
    }

    private var controls: some View {
        HStack(spacing: 36) {
            PhotosPicker(selection: $pickerItem, matching: .images) {
                Image(systemName: "photo.on.rectangle")
                    .font(.title2)
                    .foregroundStyle(.white)
                    .frame(width: 56, height: 56)
                    .background(.white.opacity(0.15), in: Circle())
            }
            .accessibilityLabel("Choose a photo of a menu")

            if cameraState == .ready {
                Button {
                    Task { await captureFromCamera() }
                } label: {
                    ZStack {
                        Circle().stroke(.white.opacity(0.6), lineWidth: 4).frame(width: 78, height: 78)
                        Circle().fill(.white).frame(width: 64, height: 64)
                    }
                }
                .accessibilityLabel("Capture the menu to review it")
                .disabled(isProcessing)
            }

            Color.clear.frame(width: 56, height: 56)
        }
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity)
        .background(.black.opacity(0.65))
    }

    private var processingOverlay: some View {
        ZStack {
            Color.black.opacity(0.55).ignoresSafeArea()
            VStack(spacing: 12) {
                ProgressView().tint(.white).scaleEffect(1.3)
                Text("Reading the menu…").foregroundStyle(.white)
            }
        }
    }

    // MARK: Photos

    private func captureFromCamera() async {
        do {
            guard let photo = try await model.capturePhoto() else { return }
            await review(photo)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func loadPhoto(_ item: PhotosPickerItem) async {
        do {
            guard let data = try await item.loadTransferable(type: Data.self), let photo = UIImage(data: data) else {
                errorMessage = "That photo couldn't be opened."
                return
            }
            await review(photo)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func review(_ photo: UIImage) async {
        isProcessing = true
        defer { isProcessing = false }
        do {
            let menu = try await MenuTextRecognizer.scan(photo)
            if menu.dishes.contains(where: \.isDish) {
                reviewing = menu
            } else {
                errorMessage = "No dishes were found in that photo. Try again closer to the menu, in good light."
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct CameraMessage: View {
    let icon: String
    let title: String
    let message: String
    var showsSettingsLink = false

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 44))
            Text(title)
                .font(.title3.weight(.semibold))
            Text(message)
                .font(.subheadline)
                .opacity(0.8)
                .multilineTextAlignment(.center)
            if showsSettingsLink, let url = URL(string: UIApplication.openSettingsURLString) {
                Link("Open Settings", destination: url)
                    .buttonStyle(.borderedProminent)
                    .tint(.white)
                    .foregroundStyle(Color.navy)
            }
        }
        .foregroundStyle(.white)
        .padding(32)
    }
}

#Preview {
    MenuScanView()
}
