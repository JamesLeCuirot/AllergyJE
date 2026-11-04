import Foundation
import Testing
@testable import MenuEngine

/// A line 10 points tall. Lines in the same dish sit 13 points apart (a 3 point gap).
private func line(_ text: String, x: CGFloat = 0, y: CGFloat, width: CGFloat = 120) -> RecognizedLine {
    RecognizedLine(text: text, box: CGRect(x: x, y: y, width: width, height: 10))
}

@Suite("Menu layout")
struct MenuLayoutTests {
    @Test func groupsNameWithDescriptionAndSeparatesDishes() {
        let blocks = MenuLayout.blocks(from: [
            line("Fish Pie", y: 0, width: 60),
            line("Cod, prawns, mash", y: 13, width: 150),
            line("Caesar Salad", y: 40, width: 90),
            line("Cos, croutons, parmesan", y: 53, width: 160),
        ])
        #expect(blocks.map(\.text) == ["Fish Pie Cod, prawns, mash", "Caesar Salad Cos, croutons, parmesan"])
    }

    @Test func keepsColumnsApart() {
        let blocks = MenuLayout.blocks(from: [
            line("Fish Pie", x: 0, y: 0),
            line("Cod, prawns, mash", x: 0, y: 13),
            line("Steak", x: 300, y: 0),
            line("Chips, peppercorn sauce", x: 300, y: 13),
        ])
        #expect(Set(blocks.map(\.text)) == ["Fish Pie Cod, prawns, mash", "Steak Chips, peppercorn sauce"])
    }

    @Test func attachesPricesOnTheSameRow() {
        let blocks = MenuLayout.blocks(from: [
            line("Fish Pie", y: 0, width: 60),
            line("14.50", x: 250, y: 0, width: 30),
        ])
        #expect(blocks.count == 1)
        #expect(blocks[0].hasPrice)
        #expect(blocks[0].box.maxX == 280)
    }

    @Test func splitsTightListsAtEachPrice() {
        let blocks = MenuLayout.blocks(from: [
            line("Chips", y: 0, width: 40),
            line("Onion rings", y: 13, width: 80),
            line("Side salad", y: 26, width: 70),
            line("£4", x: 200, y: 0, width: 20),
            line("£5", x: 200, y: 13, width: 20),
            line("£4", x: 200, y: 26, width: 20),
        ])
        #expect(blocks.map(\.text) == ["Chips", "Onion rings", "Side salad"])
        #expect(blocks.allSatisfy { $0.hasPrice })
    }

    @Test func splitsWhenPricesEndEachDescription() {
        let blocks = MenuLayout.blocks(from: [
            line("Fish Pie", y: 0),
            line("Cod, prawns, mash 14", y: 13),
            line("Steak", y: 26),
            line("Chips, peppercorn sauce 22", y: 39),
        ])
        #expect(blocks.map(\.text) == ["Fish Pie Cod, prawns, mash 14", "Steak Chips, peppercorn sauce 22"])
    }

    @Test func splitsWhenPricesFollowEachName() {
        let blocks = MenuLayout.blocks(from: [
            line("Fish Pie .... 14", y: 0),
            line("Cod, prawns, mash", y: 13),
            line("Steak .... 22", y: 26),
            line("Chips, peppercorn sauce", y: 39),
        ])
        #expect(blocks.map(\.text) == ["Fish Pie .... 14 Cod, prawns, mash", "Steak .... 22 Chips, peppercorn sauce"])
    }

    @Test func joinsFragmentsOfOneLine() {
        let blocks = MenuLayout.blocks(from: [
            line("Fish Pie", x: 0, y: 0, width: 60),
            line("– cod, prawns, mash", x: 70, y: 0, width: 140),
        ])
        #expect(blocks.map(\.text) == ["Fish Pie – cod, prawns, mash"])
    }

    @Test func worksInNormalisedImageCoordinates() {
        let blocks = MenuLayout.blocks(from: [
            RecognizedLine(text: "Fish Pie", box: CGRect(x: 0.1, y: 0.10, width: 0.2, height: 0.02)),
            RecognizedLine(text: "Cod, prawns, mash", box: CGRect(x: 0.1, y: 0.125, width: 0.4, height: 0.02)),
            RecognizedLine(text: "Steak", box: CGRect(x: 0.1, y: 0.18, width: 0.15, height: 0.02)),
        ])
        #expect(blocks.map(\.text) == ["Fish Pie Cod, prawns, mash", "Steak"])
    }

    @Test func recognisesPrices() {
        for price in ["£12.50", "9", "6.5 / 9", "........ 14", "€8,50"] {
            #expect(MenuLayout.isPriceOnly(price), "\(price)")
        }
        for text in ["Chips", "2024", "12.505", "Dover sole 500g"] {
            #expect(!MenuLayout.isPriceOnly(text), "\(text)")
        }
        #expect(MenuLayout.hasTrailingPrice("Fish pie ...... 14.50"))
        #expect(MenuLayout.hasTrailingPrice("Chips £4"))
        #expect(!MenuLayout.hasTrailingPrice("Dover sole 500g"))
        #expect(!MenuLayout.hasTrailingPrice("14"))
    }
}

@Suite("Menu analysis")
struct MenuAnalyzerTests {
    private let dishes = MenuAnalyzer.analyze([
        line("MAINS", y: 0, width: 50),
        line("Fish Pie", y: 30, width: 60),
        line("Cod, prawns, mash", y: 43, width: 150),
        line("£14", x: 250, y: 30, width: 25),
        line("Steak", y: 70, width: 40),
        line("Chips, rocket salad", y: 83, width: 150),
        line("£22", x: 250, y: 70, width: 25),
        line("Please tell us about any allergies", y: 120, width: 250),
    ])

    @Test func separatesDishesFromOtherText() {
        #expect(dishes.map(\.isDish) == [false, true, true, false])
    }

    @Test func verdictsDependOnTheUsersAllergens() {
        #expect(dishes[0].verdict(for: [.crustaceans]) == .notADish)
        #expect(dishes[2].verdict(for: [.crustaceans]) == .noIndicators)

        guard case .flagged(let concerns) = dishes[1].verdict(for: [.crustaceans]) else {
            Issue.record("Fish pie with prawns should be flagged for crustaceans")
            return
        }
        #expect(concerns.map(\.allergen) == [.crustaceans])
        #expect(dishes[1].verdict(for: []) == .noIndicators)
    }
}
