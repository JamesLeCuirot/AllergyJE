import Foundation

/// One entry from the rules table: a menu term and what it implies.
public nonisolated struct AllergenRule: Hashable, Sendable {
    /// The term as written in the table, used when explaining a prediction.
    public let term: String
    /// The term after `MenuText` normalisation, matched against menu text.
    public let tokens: [String]
    /// Allergens the term implies. Empty for food words that carry no allergen;
    /// those still mark text as food, and as longer matches they override shorter
    /// ones ("coconut milk" stops "milk" from flagging dairy).
    public let effects: [UKAllergen: AllergenLikelihood]
}

/// The knowledge base behind `AllergenPredictor`.
///
/// Each line of `source` reads `term, other term: allergen!, allergen~, allergen?`
///
/// - `!` contains: the term is the allergen ("prawn" → crustaceans)
/// - `~` likely: the classic recipe includes it ("pesto" → nuts)
/// - `?` possible: often included, depends on the kitchen ("curry" → mustard)
/// - `-` on its own: food with no allergen. It still counts as food, and it overrides
///   shorter terms inside it.
///
/// Allergen keys are `UKAllergen.ruleKey`: gluten, crustaceans, eggs, fish, peanuts, soy,
/// milk, nuts, celery, mustard, sesame, sulphites, lupin, molluscs.
///
/// Matching ignores case, accents and punctuation, picks the longest term that fits,
/// and accepts plurals ("prawn" also matches "prawns", "anchovy" matches "anchovies"),
/// so write terms in the singular. `MenuEngineTests` fails on any line that doesn't
/// parse or repeats a term.
///
/// This is a cautious starting point. It is meant to be replaced or backed up by
/// statistics learned from menus with verified allergen data.
public nonisolated enum AllergenRules {
    /// The rules the app uses: the hand-written table plus anything learned from real menus.
    public static let standard: [AllergenRule] = merge(handWritten, learned: parse(LearnedAllergenRules.source).rules)

    /// The hand-written table in `source` alone.
    public static let handWritten: [AllergenRule] = parse(source).rules

    public struct ParseResult: Sendable {
        public var rules: [AllergenRule] = []
        public var problems: [String] = []
    }

    /// Adds learned rules to the base rules. A learned rule can add allergens or raise a
    /// likelihood, but never lower or remove one. Where a learned term spans words the base
    /// rules already understand (e.g. "beef wellington"), it keeps their warnings too,
    /// because the longer match replaces the shorter ones when a menu is read.
    public static func merge(_ base: [AllergenRule], learned: [AllergenRule]) -> [AllergenRule] {
        let basePredictor = AllergenPredictor(rules: base)
        var rules = base
        var indexByTokens = Dictionary(base.enumerated().map { ($1.tokens, $0) }, uniquingKeysWith: { first, _ in first })

        func strongest(_ a: [UKAllergen: AllergenLikelihood], _ b: [UKAllergen: AllergenLikelihood]) -> [UKAllergen: AllergenLikelihood] {
            a.merging(b) { max($0, $1) }
        }

        for rule in learned {
            if let index = indexByTokens[rule.tokens] {
                let existing = rules[index]
                rules[index] = AllergenRule(term: existing.term, tokens: existing.tokens, effects: strongest(existing.effects, rule.effects))
            } else {
                var inherited: [UKAllergen: AllergenLikelihood] = [:]
                for evidence in basePredictor.assess(rule.term).evidence {
                    inherited[evidence.allergen] = evidence.likelihood
                }
                indexByTokens[rule.tokens] = rules.count
                rules.append(AllergenRule(term: rule.term, tokens: rule.tokens, effects: strongest(inherited, rule.effects)))
            }
        }
        return rules
    }

    public static func parse(_ text: String) -> ParseResult {
        var result = ParseResult()
        var firstDefinedOn: [[String]: Int] = [:]
        let allergensByKey = Dictionary(uniqueKeysWithValues: UKAllergen.allCases.map { ($0.ruleKey, $0) })

        for (offset, rawLine) in text.split(separator: "\n", omittingEmptySubsequences: false).enumerated() {
            let lineNumber = offset + 1
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.isEmpty || line.hasPrefix("#") { continue }

            guard let colon = line.firstIndex(of: ":") else {
                result.problems.append("line \(lineNumber): missing ':'")
                continue
            }

            var effects: [UKAllergen: AllergenLikelihood] = [:]
            let effectsText = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
            if effectsText != "-" {
                var unreadable = false
                for item in effectsText.split(separator: ",") {
                    let item = item.trimmingCharacters(in: .whitespaces)
                    guard let marker = item.last, let likelihood = AllergenLikelihood(marker: marker),
                          let allergen = allergensByKey[String(item.dropLast())] else {
                        result.problems.append("line \(lineNumber): can't read '\(item)'")
                        unreadable = true
                        continue
                    }
                    if effects[allergen] != nil {
                        result.problems.append("line \(lineNumber): \(allergen.ruleKey) listed twice")
                    }
                    effects[allergen] = likelihood
                }
                if effects.isEmpty {
                    if !unreadable {
                        result.problems.append("line \(lineNumber): no allergens (use '-' for none)")
                    }
                    continue
                }
            }

            for term in line[..<colon].split(separator: ",") {
                let display = term.trimmingCharacters(in: .whitespaces)
                let tokens = MenuText.tokens(display)
                guard !tokens.isEmpty else {
                    result.problems.append("line \(lineNumber): empty term")
                    continue
                }
                if let earlier = firstDefinedOn[tokens] {
                    result.problems.append("line \(lineNumber): '\(display)' is already defined on line \(earlier)")
                    continue
                }
                firstDefinedOn[tokens] = lineNumber
                result.rules.append(AllergenRule(term: display, tokens: tokens, effects: effects))
            }
        }
        return result
    }

    public static let source = """
    # ── Allergen names written on the menu itself ────────────────────────────────
    gluten: gluten!
    dairy, lactose, whey, casein: milk!
    crustacean: crustaceans!
    mollusc: molluscs!
    sulphite, sulfite, sulphur dioxide, sulfur dioxide: sulphites!
    shellfish: crustaceans~, molluscs~
    seafood, fruits de mer, frutti di mare: crustaceans~, molluscs~, fish~

    # ── Cereals containing gluten ─────────────────────────────────────────────────
    wheat, flour, rye, barley, spelt, kamut, semolina, durum, bulgur, bulgar, freekeh, seitan, couscous, cous cous, tabbouleh, oat, oatmeal, haggis, malt, malted: gluten!
    rice flour, gram flour, chickpea flour, cornflour, corn flour, potato flour, tapioca flour, buckwheat, buckwheat flour, coconut flour: -
    almond flour, ground almond: nuts!
    lupin flour: lupin!
    porridge: gluten!, milk~
    granola, muesli: gluten!, nuts~, milk?
    flapjack: gluten!, milk~, nuts?
    oat milk, oat cream: gluten~
    malt vinegar: gluten?, sulphites?

    # ── Bread, pastry and baking ──────────────────────────────────────────────────
    bread, breadcrumb, breaded, crumbed, panko, toast, crouton, crostini, bruschetta, sandwich, toastie, panini, baguette, ciabatta, focaccia, sourdough, crumpet, pitta, pita, chapati, roti, flatbread, breadstick, grissini, cracker, crispbread, pastry, filo, phyllo, shortcrust, samosa, dough, udon, summer pudding: gluten!
    garlic bread: gluten!, milk~
    brioche: gluten!, eggs~, milk~
    bagel: gluten!, sesame?
    bun: gluten~, sesame?
    roll: gluten?
    naan: gluten!, milk~, eggs?
    paratha: gluten!, milk?
    croissant, pain au chocolat: gluten!, milk~, eggs?
    danish, strudel: gluten!, milk~, eggs~, nuts?
    muffin: gluten!, eggs?, milk?
    scone: gluten!, milk~, eggs?
    cream tea: milk!, gluten!
    afternoon tea: gluten~, milk~, eggs~
    cake, sponge, gateau, cupcake: gluten~, eggs~, milk~
    carrot cake: gluten~, eggs~, milk~, nuts~
    banana bread: gluten!, eggs~, milk?, nuts?
    choux, eclair, profiterole: gluten!, eggs!, milk~
    pie: gluten~, milk?, celery?
    cottage pie, shepherds pie: gluten?, milk~, celery?
    fish pie: fish!, milk~, gluten?, celery?
    tart, tartlet: gluten~, milk?, eggs?
    tarte tatin: gluten!, milk~
    quiche: gluten!, eggs!, milk~
    custard tart, pastel de nata: gluten!, eggs!, milk!
    wellington, en croute: gluten!, eggs~, milk?, mustard?
    sausage roll: gluten!, sulphites~, milk?, eggs?
    pasty: gluten!, milk?
    spring roll: gluten!, soy?
    wonton: gluten!, eggs~, crustaceans?, soy?
    gyoza, dumpling, potsticker: gluten~, soy~, sesame?, eggs?
    dim sum: gluten~, soy~, crustaceans?, sesame?
    bao: gluten!, soy?, milk?
    pizza, calzone, stromboli: gluten!, milk~
    margherita: gluten~, milk!
    capricciosa, diavola, diavolo, quattro stagioni, napoletana: gluten!, milk~
    quattro formaggi, formaggi: milk!
    caprese: milk~
    biscuit, cookie, wafer, cone: gluten!, milk?, eggs?
    shortbread: gluten!, milk!
    biscotti: gluten!, nuts~, eggs~
    amaretti: nuts!, eggs~, gluten?
    crumble: gluten!, milk~
    churro: gluten!, milk?, eggs?
    doughnut, donut, jersey wonder: gluten!, eggs~, milk~
    crepe, pancake, waffle, blini: gluten!, eggs~, milk~
    galette: gluten?, eggs~, milk~
    french toast: gluten!, eggs!, milk~
    yorkshire pudding: gluten!, eggs!, milk!
    stuffing: gluten~, celery?, sulphites?
    croquette, arancini: gluten!, eggs~, milk~
    goujon, nugget, kiev, schnitzel, katsu, tonkatsu: gluten!, eggs~
    meatball: gluten~, eggs?, milk?
    batter, battered, tempura: gluten!, eggs?
    crispy, crust, crusted: gluten?
    salt and pepper: gluten?
    tortilla: gluten~, eggs?
    corn tortilla, tortilla chip, lettuce wrap: -
    wrap: gluten~
    burrito, fajita, enchilada: gluten~, milk~
    quesadilla: gluten~, milk!
    taco: gluten?, milk?
    nacho: milk~
    noodle: gluten~, eggs?
    rice noodle, glass noodle, rice vermicelli, rice paper, courgetti, zoodle: -
    vermicelli: gluten?
    egg noodle: gluten!, eggs!
    soba: gluten~
    ramen: gluten!, soy~, eggs?, sesame?
    chow mein, lo mein: gluten!, soy~, eggs?
    pasta, spaghetti, linguine, linguini, tagliatelle, tagliolini, fettuccine, fettuccelle, pappardelle, penne, rigatoni, fusilli, farfalle, orzo, macaroni, cannelloni, orecchiette, conchiglie, paccheri, bucatini, trofie, casarecce, panuozzo, panuozzi: gluten!, eggs?
    ravioli, tortellini, agnolotti: gluten!, eggs~, milk?
    gnocchi: gluten~, eggs?, milk?
    lasagne, lasagna: gluten!, milk!, eggs?, celery?
    mac and cheese, macaroni cheese: gluten!, milk!, mustard?
    beer, ale, lager, stout: gluten!, sulphites?
    ginger ale, ginger beer, root beer: -
    gravy: gluten~, celery?, sulphites?
    roux: gluten!, milk~
    bechamel, white sauce: gluten~, milk!
    veloute: gluten~, milk~, celery?
    cheese sauce: milk!, gluten~, mustard?
    sausage, banger, chipolata: gluten~, sulphites~, mustard?, celery?
    black pudding, white pudding: gluten~
    pudding: gluten?, milk?, eggs?
    bread and butter pudding: gluten!, milk!, eggs!
    rice pudding: milk!
    christmas pudding: gluten~, eggs~, sulphites~, nuts?
    sticky toffee: gluten~, eggs~, milk~
    full english, full breakfast: gluten~, eggs~, sulphites~, mustard?
    burger, hamburger: gluten~, sesame?, sulphites?, mustard?, eggs?
    cheeseburger: gluten~, milk!, sesame?, sulphites?, mustard?, eggs?
    hot dog: gluten~, sulphites~, mustard~

    # ── Crustaceans ───────────────────────────────────────────────────────────────
    prawn, shrimp, crab, lobster, langoustine, crayfish, krill, chancre, belacan, gambas, gamba, gamberi, gamberoni, camarones, crevette: crustaceans!
    scampi: crustaceans!, gluten~
    prawn cocktail: crustaceans!, eggs!, mustard?, gluten?
    marie rose: eggs!, mustard?
    prawn cracker: crustaceans!, gluten?
    prawn toast: crustaceans!, gluten!, sesame~
    bisque: crustaceans~, milk~, celery?, sulphites?
    thermidor: crustaceans~, milk!, mustard~, gluten~, eggs?
    surf and turf: crustaceans~
    paella: crustaceans~, molluscs~, fish?, celery?
    jambalaya, gumbo: crustaceans~, celery~, gluten?
    tom yum: crustaceans~, fish~
    laksa: crustaceans~, fish~, soy?, nuts?
    xo sauce: crustaceans~, molluscs~, soy?
    cioppino: fish!, crustaceans~, molluscs~
    crab stick, surimi: fish!, crustaceans?, eggs?

    # ── Molluscs ──────────────────────────────────────────────────────────────────
    mussel, oyster, clam, scallop, squid, octopus, cuttlefish, whelk, winkle, cockle, snail, escargot, abalone, ormer, vongole, moules, palourde: molluscs!
    calamari, fried squid, salt and pepper squid: molluscs!, gluten~
    oyster sauce: molluscs!, soy?, gluten?
    mariniere: molluscs~, milk~, sulphites~, celery?
    moules mariniere: molluscs!, milk~, sulphites~, celery?
    fritto misto: molluscs~, crustaceans~, fish~, gluten!

    # ── Fish ──────────────────────────────────────────────────────────────────────
    fish, salmon, tuna, cod, haddock, hake, pollock, pollack, coley, plaice, sole, bass, seabass, bream, mackerel, sardine, pilchard, anchovy, herring, kipper, trout, halibut, turbot, monkfish, mullet, snapper, swordfish, tilapia, skate, brill, gurnard, john dory, catfish, carp, eel, conger, pike, perch, arctic char, barramundi, sprat, whiting, roe, caviar, taramasalata, gravadlax, gravlax, lox, fish sauce, nam pla, bonito, katsuobushi, bouillabaisse, sashimi, ceviche: fish!
    whitebait, fish finger, fish and chips: fish!, gluten~
    fishcake, fish cake: fish!, gluten~, eggs?, milk?
    kedgeree: fish!, eggs~, milk?
    sushi, nigiri, maki, uramaki, temaki: fish~, soy~, sesame?, gluten?, crustaceans?
    poke: fish~, soy~, sesame~
    dashi: fish~
    furikake: sesame~, fish?
    caesar: eggs~, fish~, milk~, gluten~, mustard?
    nicoise: fish~, eggs~, mustard?
    puttanesca: fish~
    tonnato: fish!, eggs!
    poisson: fish!
    salsa verde: fish?, mustard?
    tapenade: fish?
    worcestershire, worcester sauce: fish~, gluten~, sulphites?
    bloody mary: celery~, fish~, sulphites?
    pho: fish~

    # ── East and South-East Asian dishes ──────────────────────────────────────────
    thai: fish?, crustaceans?, peanuts?
    green curry, red curry, yellow curry, jungle curry: fish~, crustaceans?, peanuts?, nuts?, celery?
    panang: fish~, peanuts~, crustaceans?
    pad thai: peanuts~, eggs~, fish~, crustaceans?, soy?
    massaman: peanuts~, fish~, nuts?
    satay: peanuts!, soy~, fish?
    gado gado: peanuts!, eggs~, soy~
    kung pao: peanuts~, soy~, gluten?
    nasi goreng: soy~, eggs~, crustaceans?, fish?
    kimchi: fish?, crustaceans?
    bulgogi: soy~, sesame~
    bibimbap: sesame~, soy~, eggs~
    gochujang: soy~, gluten~
    katsu curry: gluten!, eggs~, soy?, celery?
    yakitori: soy~, gluten?
    teriyaki: soy!, gluten~, sesame?
    hoisin: soy~, gluten?, sesame?
    peking, crispy duck: gluten~, soy~
    char siu: soy~, gluten?, sesame?
    fried rice: soy~, eggs?
    egg fried rice: eggs!, soy~
    stir fry, stir fried: soy~, gluten?, sesame?
    sweet and sour: gluten?, soy?
    szechuan, sichuan: soy~, gluten?, sesame?, peanuts?
    chilli crisp, chili crisp, chilli oil, chili oil: soy?, sesame?, peanuts?

    # ── Soya ──────────────────────────────────────────────────────────────────────
    soy, soya, soybean, soya bean, soy bean, tofu, beancurd, bean curd, tempeh, natto, edamame, tvp, soy milk, soya milk, soy yoghurt, soya yoghurt, soy yogurt, soya yogurt, soy cream, soya cream, tamari: soy!
    soy sauce, shoyu: soy!, gluten~
    lecithin: soy~
    miso: soy!, gluten?
    ponzu: soy!, fish?
    black bean sauce: soy~, gluten?
    black bean, turtle bean: -

    # ── Eggs ──────────────────────────────────────────────────────────────────────
    egg, yolk, omelette, omelet, frittata, shakshuka, huevos, meringue: eggs!
    scotch egg: eggs!, gluten!, sulphites~
    mayonnaise, mayo, aioli: eggs!, mustard?
    hollandaise: eggs!, milk!
    bearnaise: eggs!, milk!, sulphites?
    benedict: eggs!, milk!, gluten!
    egg florentine: eggs!, milk!, gluten~
    florentine: eggs?, milk?, nuts?
    tartare sauce, tartar sauce: eggs!, mustard?
    tartare: eggs~, mustard~
    remoulade: eggs!, mustard~
    celeriac remoulade: celery!, eggs!, mustard~
    coleslaw: eggs~, mustard?
    slaw: eggs?, mustard?
    potato salad: eggs?, mustard?
    salad cream: eggs!, mustard~
    thousand island: eggs!
    ranch: milk!, eggs~
    custard: milk!, eggs~
    creme anglaise, creme brulee, brulee, creme caramel: milk!, eggs!
    panna cotta: milk!
    mousse: milk~, eggs~
    tiramisu: eggs!, milk!, gluten~, sulphites?
    pavlova: eggs!, milk~
    eton mess: eggs!, milk!
    macaron: nuts!, eggs!
    macaroon: eggs~, nuts?
    souffle: eggs!, milk~, gluten?
    carbonara: eggs!, milk~, gluten~
    lemon curd: eggs!, milk~
    zabaglione: eggs!, sulphites~
    fondant: eggs~, milk~, gluten?
    brownie: gluten~, eggs~, milk~, nuts?
    cheesecake: milk!, gluten~, eggs?
    ice cream: milk!, eggs?
    gelato: milk~, eggs?
    semifreddo: milk!, eggs~
    parfait: milk~, eggs~, sulphites?
    pate: milk~, eggs?, sulphites?
    terrine: eggs?, sulphites?

    # ── Milk ──────────────────────────────────────────────────────────────────────
    milk, cheese, cheesy, cheddar, mozzarella, parmesan, parmigiano, pecorino, grana padano, feta, halloumi, brie, camembert, gorgonzola, stilton, roquefort, dolcelatte, ricotta, mascarpone, burrata, emmental, gruyere, manchego, comte, raclette, fontina, provolone, taleggio, paneer, labneh, quark, kefir, skyr, cream, creme fraiche, butter, buttered, buttery, beurre, ghee, yoghurt, yogurt, yoghourt, buttermilk, dulce de leche, fudge, raita, tzatziki, lassi, latte, cappuccino, flat white, mocha, macchiato, milkshake, affogato, sundae, knickerbocker glory, alfredo, gratin, dauphinoise, makhani, queso, fondue, baileys, white russian, irish coffee, white chocolate: milk!
    creamy, creamed, creme, frappe, hot chocolate, chai, mash, mashed, champ, colcannon, toffee, butterscotch, salted caramel, tikka, saag, pomme puree: milk~
    chocolate, caramel, smoothie: milk?
    coconut milk, coconut cream, creamed coconut, coconut yoghurt, coconut yogurt, rice milk, plant milk, cocoa butter, butter bean: -
    almond milk, almond butter, cashew milk, cashew cheese, cashew cream, nut butter, nut milk: nuts!
    peanut butter: peanuts!
    vegan cheese: nuts?, soy?
    vegan butter, plant butter: soy?
    korma, pasanda: nuts~, milk~
    tikka masala: milk~, nuts?, mustard?
    masala: milk?, nuts?, mustard?
    butter chicken: milk!, nuts?
    kulfi: milk!, nuts~
    risotto: milk~, celery?, sulphites?
    moussaka: milk!, gluten~, eggs~
    rarebit: milk!, gluten!, mustard~
    diane: milk~, mustard~
    peppercorn sauce: milk~, sulphites?
    beurre blanc: milk!, sulphites~
    puree: milk?
    posset, syllabub: milk!, sulphites?
    horseradish: milk?, mustard?

    # ── Tree nuts ─────────────────────────────────────────────────────────────────
    almond, hazelnut, walnut, cashew, pecan, brazil nut, pistachio, macadamia, praline, marzipan, romesco, muhammara: nuts!
    nut: nuts!, peanuts?
    mixed nut: nuts!, peanuts~
    pine nut, chestnut: nuts?
    coconut, nutmeg, water chestnut, tiger nut, butternut: -
    gianduja, nutella: nuts!, milk!
    nougat: nuts~, eggs~
    torrone, torroncino: nuts~, eggs~
    pistacchio, pistache: nuts!
    goma: sesame!
    amaretto, disaronno: nuts?
    frangelico: nuts~
    baklava: nuts!, gluten!, milk~
    pesto: nuts~, milk~
    waldorf: nuts!, celery!, eggs~
    dukkah, dukka: nuts~, sesame~
    rocky road: nuts?, milk~, gluten~
    brittle: nuts~, peanuts~
    bakewell: nuts!, gluten!, eggs~, milk~
    frangipane: nuts!, eggs!, milk~, gluten?
    financier: nuts~, eggs~, milk~

    # ── Peanuts ───────────────────────────────────────────────────────────────────
    peanut, groundnut, monkey nut, arachis: peanuts!

    # ── Celery ────────────────────────────────────────────────────────────────────
    celery, celeriac: celery!
    mirepoix, soffritto, sofrito, consomme: celery~
    bolognese, ragu, ragout: celery~, sulphites?
    minestrone: celery~, gluten?
    stock, broth, stew, casserole, hotpot, goulash, braised, braise, pot roast, chilli con carne, chili con carne, bean crock: celery?
    soup: celery?, gluten?, milk?
    chowder: milk!, fish~, molluscs~, celery?, gluten?
    osso buco: celery~, sulphites~, gluten?
    coq au vin, bourguignon: sulphites~, celery~, gluten?
    jus: celery?, sulphites?
    curry, curried, madras, vindaloo, jalfrezi, bhuna, rogan josh, balti, dopiaza, dhansak: mustard?, celery?, nuts?, milk?
    dal, dhal, daal, tarka: mustard?, milk?
    biryani: nuts?, milk?
    bhaji, bhajee, pakora: gluten?, mustard?
    poppadom, poppadum, papadum, chutney: -

    # ── Mustard ───────────────────────────────────────────────────────────────────
    mustard, dijon, piccalilli, dijonnaise, kasundi: mustard!
    vinaigrette, french dressing, house dressing: mustard~, sulphites?
    dressing: mustard?
    devilled, deviled: mustard~
    bbq, barbecue, barbeque: mustard?, gluten?

    # ── Sesame ────────────────────────────────────────────────────────────────────
    sesame, tahini, tahina, gomasio: sesame!
    hummus, houmous, hummous, baba ganoush, baba ghanoush, zaatar, zatar: sesame~
    halva, halwa: sesame~, nuts?
    seed, seeded: sesame?
    falafel: sesame?, gluten?
    kebab, doner, shawarma, shish: gluten~, sesame?, milk?
    souvlaki, gyro: gluten~, milk?

    # ── Sulphites ─────────────────────────────────────────────────────────────────
    wine, prosecco, champagne, cava, sherry, madeira, marsala, vermouth, sangria, cider, balsamic, dried fruit, dried apricot, raisin, sultana, currant, glace cherry, mixed peel, cordial: sulphites~
    vinegar, pickled, pickle, gherkin, cornichon, prune: sulphites?
    rice vinegar: -

    # ── Lupin ─────────────────────────────────────────────────────────────────────
    lupin, lupini: lupin!

    # ── Food with no allergen (marks text as a dish) ──────────────────────────────
    chicken, beef, steak, sirloin, ribeye, rib eye, fillet, rump, brisket, lamb, pork, belly, ham, gammon, bacon, pancetta, prosciutto, chorizo, salami, duck, venison, turkey, rabbit, pigeon, quail, liver, mince, rib, wing, chop, cutlet, loin, shank, oxtail: -
    potato, sweet potato, jersey royal, chip, fries, frites, wedge, hash brown, rice, quinoa, polenta, lentil, chickpea, bean, pea, salad, rocket, spinach, kale, cabbage, broccoli, tenderstem, cauliflower, carrot, parsnip, beetroot, squash, pumpkin, courgette, zucchini, aubergine, eggplant, pepper, chilli, chili, jalapeno, onion, shallot, leek, garlic, tomato, mushroom, asparagus, avocado, olive, sweetcorn, corn, lettuce, cucumber, radish, fennel, artichoke, samphire, pomegranate, truffle, basil, herb, ginger: -
    apple, pear, strawberry, raspberry, blueberry, berry, cherry, lemon, lime, orange, mango, pineapple, banana, fruit, honey, maple, sorbet, salsa, guacamole, espresso, coffee, tea, americano, juice, lemonade: -
    grilled, chargrilled, char grilled, roasted, roast, pan fried, seared, slow cooked, smoked, fried, baked, poached, steamed, charred, confit, served, garnish: -
    """
}
