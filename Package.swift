// swift-tools-version: 6.2
//
// Test harness for the menu-scanning engine: plain Swift with no UIKit, so its logic can be
// unit-tested with `swift test` on a Mac or Linux, without Xcode or a simulator.
//
// The app doesn't use this package. The Xcode project compiles the same files from
// AllergyJE/MenuScan/Engine directly. The settings below mirror the app target's
// (MainActor default isolation, approachable concurrency), so code that passes here
// should also compile there.
import PackageDescription

let package = Package(
    name: "AllergyJEEngine",
    platforms: [.macOS(.v14)],
    targets: [
        .target(
            name: "MenuEngine",
            path: "AllergyJE/MenuScan/Engine",
            swiftSettings: [
                .defaultIsolation(MainActor.self),
                .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
                .enableUpcomingFeature("InferIsolatedConformances"),
                .enableUpcomingFeature("MemberImportVisibility"),
            ]
        ),
        .testTarget(
            name: "MenuEngineTests",
            dependencies: ["MenuEngine"],
            path: "Tests/MenuEngineTests"
        ),
        // Scoring and rule learning against menus with known allergens. Not part of the app.
        .target(
            name: "MenuEngineTraining",
            dependencies: ["MenuEngine"],
            path: "Tools/Training"
        ),
        .executableTarget(
            name: "allergy-tools",
            dependencies: ["MenuEngine", "MenuEngineTraining"],
            path: "Tools/allergy-tools"
        ),
        .testTarget(
            name: "MenuEngineTrainingTests",
            dependencies: ["MenuEngine", "MenuEngineTraining"],
            path: "Tests/MenuEngineTrainingTests"
        ),
    ]
)
