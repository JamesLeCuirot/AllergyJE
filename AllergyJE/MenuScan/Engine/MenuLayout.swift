#if canImport(CoreGraphics)
import CoreGraphics
#endif
import Foundation

/// A line of text read from a menu by OCR.
nonisolated struct RecognizedLine: Equatable, Sendable {
    var text: String
    /// Where the line is. Any coordinate space works (normalised image coordinates or
    /// on-screen points) as long as y grows downwards and all lines share it.
    var box: CGRect
}

/// Lines that belong together on the menu, usually one dish: its name, description and price.
nonisolated struct MenuBlock: Equatable, Sendable {
    /// Text lines, top to bottom.
    let lines: [RecognizedLine]
    /// Lines that hold nothing but a price, attached to this block.
    let prices: [RecognizedLine]
    let box: CGRect
    let hasPrice: Bool

    var text: String { lines.map(\.text).joined(separator: " ") }
}

/// Groups OCR lines into dishes.
///
/// Lines are joined when they sit close together vertically in the same column. When a
/// group holds several prices, it is split so that each dish keeps one price. That works
/// both for menus that print the price beside the name and for menus that print it at the
/// end of the description.
nonisolated enum MenuLayout {
    /// The largest vertical gap between lines of the same dish, as a multiple of the
    /// typical line height. Gaps between dishes are usually a full line or more.
    static let maxLineGap: CGFloat = 0.65

    static func blocks(from input: [RecognizedLine]) -> [MenuBlock] {
        var content: [RecognizedLine] = []
        var priceOnly: [RecognizedLine] = []
        for line in input {
            let text = line.text.trimmingCharacters(in: .whitespacesAndNewlines)
            let box = line.box.standardized
            guard !text.isEmpty, box.width > 0, box.height > 0 else { continue }
            let clean = RecognizedLine(text: text, box: box)
            if isPriceOnly(text) { priceOnly.append(clean) } else { content.append(clean) }
        }
        guard !content.isEmpty else { return [] }

        let lineHeight = median(content.map(\.box.height))

        // 1. Join each line to the nearest group above it in the same column.
        let ordered = content.sorted { $0.box.minY != $1.box.minY ? $0.box.minY < $1.box.minY : $0.box.minX < $1.box.minX }
        var groups: [Group] = []
        for line in ordered {
            var best: (index: Int, score: CGFloat)?
            for (index, group) in groups.enumerated() {
                guard let score = joinScore(group, line, lineHeight) else { continue }
                if best == nil || score < best!.score { best = (index, score) }
            }
            if let best {
                groups[best.index].append(line)
            } else {
                groups.append(Group(line))
            }
        }

        // 2. Attach price-only lines to the text on the same row, or the group just above.
        for price in priceOnly {
            var sameRowMatch: (group: Int, line: Int, distance: CGFloat)?
            for (groupIndex, group) in groups.enumerated() {
                for (lineIndex, line) in group.lines.enumerated() where sameRow(line.box, price.box) {
                    let distance = price.box.minX - line.box.maxX
                    guard distance > -0.5 * lineHeight else { continue }
                    if sameRowMatch == nil || distance < sameRowMatch!.distance {
                        sameRowMatch = (groupIndex, lineIndex, distance)
                    }
                }
            }
            if let match = sameRowMatch {
                groups[match.group].attach(price, toLine: match.line)
                continue
            }

            var below: (group: Int, gap: CGFloat)?
            for (groupIndex, group) in groups.enumerated() {
                let gap = price.box.minY - group.box.maxY
                guard gap > -0.35 * lineHeight, gap < maxLineGap * lineHeight,
                      horizontallyAligned(group.box, price.box, lineHeight) else { continue }
                if below == nil || gap < below!.gap { below = (groupIndex, gap) }
            }
            if let below {
                groups[below.group].attach(price, toLine: groups[below.group].lines.count - 1)
            }
        }

        // 3. Split groups that turned out to hold more than one priced dish.
        return groups
            .flatMap(split)
            .map(\.block)
            .sorted { $0.box.minY != $1.box.minY ? $0.box.minY < $1.box.minY : $0.box.minX < $1.box.minX }
    }

    // MARK: Prices

    /// "£12.50", "9", "6.5 / 9", "........ 14"
    static func isPriceOnly(_ text: String) -> Bool {
        let parts = text
            .split(whereSeparator: { $0.isWhitespace || "/|".contains($0) })
            .map { $0.trimmingCharacters(in: leaders) }
            .filter { !$0.isEmpty }
        return !parts.isEmpty && parts.allSatisfy { isPrice($0[...]) }
    }

    /// "Fish pie ...... 14.50", "Chips £4"
    static func hasTrailingPrice(_ text: String) -> Bool {
        let parts = text.split(whereSeparator: \.isWhitespace)
        guard parts.count >= 2, let last = parts.last else { return false }
        let trimmed = last.trimmingCharacters(in: leaders)
        return !trimmed.isEmpty && isPrice(trimmed[...])
    }

    private static let leaders = CharacterSet(charactersIn: ".·…_-–—")

    private static func isPrice(_ token: Substring) -> Bool {
        var rest = token
        if let first = rest.first, "£$€".contains(first) { rest = rest.dropFirst() }
        let whole = rest.prefix { $0.isASCII && $0.isNumber }
        guard (1...3).contains(whole.count) else { return false }
        rest = rest.dropFirst(whole.count)
        if rest.isEmpty { return true }
        guard rest.first == "." || rest.first == "," else { return false }
        rest = rest.dropFirst()
        let fraction = rest.prefix { $0.isASCII && $0.isNumber }
        return (1...2).contains(fraction.count) && fraction.count == rest.count
    }

    // MARK: Geometry

    private static func joinScore(_ group: Group, _ line: RecognizedLine, _ lineHeight: CGFloat) -> CGFloat? {
        let bottom = group.lines[group.lines.count - 1]
        if sameRow(bottom.box, line.box) {
            // Another fragment of the same printed line, e.g. OCR split it around a dash.
            let distance = line.box.minX - bottom.box.maxX
            return distance > -lineHeight && distance < 2.5 * lineHeight ? 0 : nil
        }
        let gap = line.box.minY - group.box.maxY
        guard gap > -0.35 * lineHeight, gap < maxLineGap * lineHeight,
              horizontallyAligned(group.box, line.box, lineHeight) else { return nil }
        return max(gap, 0) + 0.001
    }

    private static func sameRow(_ a: CGRect, _ b: CGRect) -> Bool {
        let overlap = min(a.maxY, b.maxY) - max(a.minY, b.minY)
        return overlap > 0.5 * min(a.height, b.height)
    }

    private static func horizontallyAligned(_ a: CGRect, _ b: CGRect, _ lineHeight: CGFloat) -> Bool {
        let overlap = min(a.maxX, b.maxX) - max(a.minX, b.minX)
        return overlap > 0.25 * min(a.width, b.width) || abs(a.minX - b.minX) < lineHeight
    }

    private static func median(_ values: [CGFloat]) -> CGFloat {
        let sorted = values.sorted()
        return sorted[sorted.count / 2]
    }

    // MARK: Splitting

    private struct Group {
        var lines: [RecognizedLine]
        var box: CGRect
        var prices: [(line: Int, price: RecognizedLine)] = []

        init(_ line: RecognizedLine) {
            lines = [line]
            box = line.box
        }

        init(lines: [RecognizedLine], prices: [(line: Int, price: RecognizedLine)]) {
            self.lines = lines
            self.prices = prices
            box = lines.dropFirst().reduce(lines[0].box) { $0.union($1.box) }
        }

        mutating func append(_ line: RecognizedLine) {
            lines.append(line)
            box = box.union(line.box)
        }

        mutating func attach(_ price: RecognizedLine, toLine index: Int) {
            prices.append((index, price))
        }

        var block: MenuBlock {
            let fullBox = prices.reduce(box) { $0.union($1.price.box) }
            return MenuBlock(
                lines: lines,
                prices: prices.map(\.price),
                box: fullBox,
                hasPrice: !prices.isEmpty || lines.contains { MenuLayout.hasTrailingPrice($0.text) }
            )
        }
    }

    private static func split(_ group: Group) -> [Group] {
        let lines = group.lines
        let pricedLines = Set(group.prices.map(\.line))
            .union(lines.indices.filter { hasTrailingPrice(lines[$0].text) })
            .sorted()

        func rowStart(_ index: Int) -> Int {
            var start = index
            while start > 0, sameRow(lines[start - 1].box, lines[index].box) { start -= 1 }
            return start
        }
        func rowEnd(_ index: Int) -> Int {
            var end = index
            while end < lines.count - 1, sameRow(lines[end + 1].box, lines[index].box) { end += 1 }
            return end
        }

        var rows: [(start: Int, end: Int)] = []
        for index in pricedLines {
            let row = (start: rowStart(index), end: rowEnd(index))
            if rows.last?.start != row.start { rows.append(row) }
        }
        guard rows.count >= 2, let first = rows.first, let last = rows.last else { return [group] }

        // Prices mark the end of each dish when the first price isn't on the top line but
        // the last one is on the bottom line. Otherwise they mark the start of each dish.
        let cuts: [Int] = first.start != 0 && last.end == lines.count - 1
            ? rows.dropLast().map { $0.end + 1 }
            : rows.dropFirst().map(\.start)

        let bounds = [0] + cuts + [lines.count]
        return zip(bounds, bounds.dropFirst()).compactMap { start, end in
            guard start < end else { return nil }
            let prices = group.prices
                .filter { (start..<end).contains($0.line) }
                .map { (line: $0.line - start, price: $0.price) }
            return Group(lines: Array(lines[start..<end]), prices: prices)
        }
    }
}
