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
            // Lay the menu out in pixels, where x and y share a scale (MenuLayout relies on that),
            // then normalise the boxes so the review screen can draw them at any size.
            let lines = try recognizeLines(in: image)
            let pixels = CGSize(width: image.size.width * image.scale, height: image.size.height * image.scale)
            let dishes = MenuAnalyzer.analyze(lines).map { normalized($0, to: pixels) }
            return ScannedMenu(image: image, dishes: dishes)
        }.value
    }

    private static func normalized(_ dish: ScannedDish, to size: CGSize) -> ScannedDish {
        let box = CGRect(
            x: dish.box.minX / size.width,
            y: dish.box.minY / size.height,
            width: dish.box.width / size.width,
            height: dish.box.height / size.height
        )
        return ScannedDish(id: dish.id, text: dish.text, box: box, isDish: dish.isDish, assessment: dish.assessment)
    }

    /// Lines of text in pixel coordinates with the origin at the top left.
    static func recognizeLines(in image: UIImage) throws -> [RecognizedLine] {
        guard let cgImage = image.cgImage else { return [] }
        let width = CGFloat(cgImage.width)
        let height = CGFloat(cgImage.height)
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        // Jersey menus mix English with French dish names (marinière, crème brûlée).
        request.recognitionLanguages = ["en-US", "fr-FR"]
        try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])

        return (request.results ?? []).compactMap { observation in
            guard let text = observation.topCandidates(1).first?.string else { return nil }
            // Vision's boxes are normalised with their origin at the bottom left.
            let box = observation.boundingBox
            return RecognizedLine(text: text, box: CGRect(
                x: box.minX * width,
                y: (1 - box.maxY) * height,
                width: box.width * width,
                height: box.height * height
            ))
        }
    }

    /// Redraws the photo the right way up (camera photos are often stored rotated)
    /// and no larger than `maxDimension`, so Vision and the screen see the same pixels.
    static func upright(_ image: UIImage, maxDimension: CGFloat = 3000) -> UIImage {
        let scale = min(1, maxDimension / max(image.size.width, image.size.height))
        let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.preferredRange = .standard // 8-bit is plenty for OCR, and half the memory of extended range
        return UIGraphicsImageRenderer(size: size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
    }
}
