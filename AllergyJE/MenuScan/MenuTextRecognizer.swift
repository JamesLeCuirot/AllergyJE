import UIKit
import Vision

/// A photo of a menu and the dishes read from it.
/// `@unchecked Sendable` because UIImage is immutable; it's created on a background task and shown on the main actor.
nonisolated struct ScannedMenu: Identifiable, Hashable, @unchecked Sendable {
    let id = UUID()
    /// Upright and downscaled. Dish boxes are normalised (0...1, origin top-left) to this image.
    let image: UIImage
    let dishes: [ScannedDish]

    static func == (lhs: ScannedMenu, rhs: ScannedMenu) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

/// Reads menu text from still photos with Vision.
nonisolated enum MenuTextRecognizer {
    /// OCRs the photo and predicts allergens for each dish, off the main thread.
    static func scan(_ photo: UIImage) async throws -> ScannedMenu {
        try await Task.detached(priority: .userInitiated) {
            let image = upright(photo)
            let lines = try recognizeLines(in: image)
            return ScannedMenu(image: image, dishes: MenuAnalyzer.analyze(lines))
        }.value
    }

    /// Lines of text in normalised coordinates with the origin at the top left.
    static func recognizeLines(in image: UIImage) throws -> [RecognizedLine] {
        guard let cgImage = image.cgImage else { return [] }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        // Jersey menus mix English with French dish names (marinière, crème brûlée).
        request.recognitionLanguages = ["en-US", "fr-FR"]
        try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])

        return (request.results ?? []).compactMap { observation in
            guard let text = observation.topCandidates(1).first?.string else { return nil }
            // Vision's boxes have their origin at the bottom left.
            let box = observation.boundingBox
            return RecognizedLine(text: text, box: CGRect(x: box.minX, y: 1 - box.maxY, width: box.width, height: box.height))
        }
    }

    /// Redraws the photo the right way up (camera photos are often stored rotated)
    /// and no larger than `maxDimension`, so Vision and the screen see the same pixels.
    static func upright(_ image: UIImage, maxDimension: CGFloat = 3000) -> UIImage {
        let scale = min(1, maxDimension / max(image.size.width, image.size.height))
        let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        return UIGraphicsImageRenderer(size: size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
    }
}
