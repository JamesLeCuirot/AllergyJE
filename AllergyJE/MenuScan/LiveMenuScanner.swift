import SwiftUI
import VisionKit

/// Holds what the live camera currently reads.
@Observable
final class LiveScanModel {
    /// Boxes are in the scanner view's coordinates (points).
    private(set) var dishes: [ScannedDish] = []
    @ObservationIgnored weak var scanner: DataScannerViewController?

    func update(from items: [RecognizedItem]) {
        var lines: [RecognizedLine] = []
        for item in items {
            guard case .text(let text) = item else { continue }
            let corners = [text.bounds.topLeft, text.bounds.topRight, text.bounds.bottomLeft, text.bounds.bottomRight]
            guard let minX = corners.map(\.x).min(), let maxX = corners.map(\.x).max(),
                  let minY = corners.map(\.y).min(), let maxY = corners.map(\.y).max() else { continue }

            // The scanner sometimes returns a paragraph as one item; split it into lines.
            let parts = text.transcript.split(whereSeparator: \.isNewline).map(String.init)
            guard !parts.isEmpty else { continue }
            let lineHeight = (maxY - minY) / CGFloat(parts.count)
            for (index, part) in parts.enumerated() {
                let box = CGRect(x: minX, y: minY + CGFloat(index) * lineHeight, width: maxX - minX, height: lineHeight)
                lines.append(RecognizedLine(text: part, box: box))
            }
        }
        dishes = MenuAnalyzer.analyze(lines)
    }

    func capturePhoto() async throws -> UIImage? {
        guard let scanner else { return nil }
        return try await scanner.capturePhoto()
    }
}

/// The live camera, reading text with VisionKit's DataScanner.
struct LiveMenuScanner: UIViewControllerRepresentable {
    let model: LiveScanModel

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.text()],
            qualityLevel: .accurate,
            recognizesMultipleItems: true,
            isHighFrameRateTrackingEnabled: true,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: false,
            isHighlightingEnabled: false
        )
        scanner.delegate = context.coordinator
        model.scanner = scanner
        return scanner
    }

    func updateUIViewController(_ scanner: DataScannerViewController, context: Context) {
        if !scanner.isScanning {
            try? scanner.startScanning()
        }
    }

    static func dismantleUIViewController(_ scanner: DataScannerViewController, coordinator: Coordinator) {
        scanner.stopScanning()
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(model: model)
    }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let model: LiveScanModel

        init(model: LiveScanModel) {
            self.model = model
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            model.update(from: allItems)
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didUpdate updatedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            model.update(from: allItems)
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didRemove removedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            model.update(from: allItems)
        }
    }
}
