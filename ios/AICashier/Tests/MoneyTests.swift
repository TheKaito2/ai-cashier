import XCTest
@testable import AICashier

final class PromptPayTests: XCTestCase {
    func testTheChecksumMatchesThePublishedCheckValue() throws {
        let f = try FX.load()
        XCTAssertEqual(Int(PromptPay.crc16(f.crc16_check.input)), f.crc16_check.value)
        XCTAssertEqual(PromptPay.crc16("123456789"), 0x29B1)
    }

    func testEveryPayloadIsByteEqualToPython() throws {
        for v in try FX.load().promptpay {
            XCTAssertEqual(try PromptPay.buildPayload(target: v.target, amount: v.amount), v.payload, v.target)
        }
    }

    func testEveryWayOfWritingOneMobileNumberGivesTheSameId() throws {
        for written in ["0812345678", "66812345678", "+66 81 234 5678", "0066812345678", "081 234 5678"] {
            let (tag, value) = try PromptPay.normaliseTarget(written)
            XCTAssertEqual(tag, "01"); XCTAssertEqual(value, "0066812345678")
        }
        XCTAssertThrowsError(try PromptPay.normaliseTarget("12345"))
        XCTAssertThrowsError(try PromptPay.buildPayload(target: "0812345678", amount: -5))
    }
}

final class CheckoutTests: XCTestCase {
    private func shop() throws -> AppDatabase {
        let db = try AppDatabase(path: nil)
        try db.upsert(Product(id: "pepsi", name: "Pepsi 325ml", price: 14, category: "drinks", stock: 10))
        try db.upsert(Product(id: "beer", name: "Beer 330ml", price: 45, category: "drinks", stock: 6, restricted: .alcohol))
        return db
    }

    private var noon: Date { Calendar.current.date(bySettingHour: 12, minute: 0, second: 0, of: Date())! }

    func testTotalIsSubtotalPlusSevenPercent() throws {
        let db = try shop()
        let p = try Checkout.createPayment(db, items: [("pepsi", 2)], now: noon)
        XCTAssertEqual(p.subtotal, 28, accuracy: 1e-9)
        XCTAssertEqual(p.tax, 1.96, accuracy: 1e-9)
        XCTAssertEqual(p.total, 29.96, accuracy: 1e-9)
        XCTAssertFalse(p.payable)                                  // no PromptPay id configured
        XCTAssertTrue(p.qrPayload.hasPrefix("NOT-CONFIGURED|"))
    }

    func testAConfiguredShopGetsAPayableCode() throws {
        let db = try shop()
        var s = try db.settings(); s.promptpayId = "0812345678"; try db.save(s)
        let p = try Checkout.createPayment(db, items: [("pepsi", 1)], now: noon)
        XCTAssertTrue(p.payable)
        XCTAssertEqual(p.qrPayload, try PromptPay.buildPayload(target: "0812345678", amount: 14.98))
    }

    func testConfirmingTakesTheStockDownOnce() throws {
        let db = try shop()
        let p = try Checkout.createPayment(db, items: [("pepsi", 2)], now: noon)
        XCTAssertEqual(try db.product("pepsi")?.stock, 10)
        let sale = try Checkout.confirm(db, paymentId: p.paymentId)
        XCTAssertEqual(try db.product("pepsi")?.stock, 8)
        XCTAssertEqual(sale.items.first?.quantity, 2)
        XCTAssertThrowsError(try Checkout.confirm(db, paymentId: p.paymentId)) { e in
            XCTAssertEqual((e as? CheckoutError)?.status, 400)
        }
        XCTAssertEqual(try db.analytics().totalSales, 1)
    }

    func testRefusals() throws {
        let db = try shop()
        XCTAssertThrowsError(try Checkout.createPayment(db, items: [], now: noon)) { XCTAssertEqual(($0 as? CheckoutError)?.status, 400) }
        XCTAssertThrowsError(try Checkout.createPayment(db, items: [("ghost", 1)], now: noon)) { XCTAssertEqual(($0 as? CheckoutError)?.status, 404) }
        XCTAssertThrowsError(try Checkout.createPayment(db, items: [("pepsi", 11)], now: noon)) { XCTAssertEqual(($0 as? CheckoutError)?.status, 400) }
        XCTAssertThrowsError(try Checkout.createPayment(db, items: [("beer", 1)], now: noon)) { e in
            XCTAssertEqual((e as? CheckoutError)?.status, 403)
            XCTAssertTrue((e as? CheckoutError)?.needsStaff ?? false)
        }
        XCTAssertNoThrow(try Checkout.createPayment(db, items: [("beer", 1)], staffConfirmed: true, now: noon))
        XCTAssertEqual(try db.events(kind: "override").count, 1)
    }

    func testTheReceiptComesInBothLegalForms() throws {
        let db = try shop()
        let p = try Checkout.createPayment(db, items: [("pepsi", 2)], now: noon)
        let sale = try Checkout.confirm(db, paymentId: p.paymentId)
        var s = ShopSettings(); s.storeName = "Krist Mart"
        let plain = Receipt.render(sale, settings: s)
        XCTAssertTrue(plain.contains("RECEIPT")); XCTAssertFalse(plain.contains("VAT"))
        s.vatRegistered = true; s.tin = "0123456789012"
        let abb = Receipt.render(sale, settings: s)
        XCTAssertTrue(abb.contains("TAX INVOICE (ABB)")); XCTAssertTrue(abb.contains("0123456789012")); XCTAssertTrue(abb.contains("VAT 7%"))
        for line in abb.split(separator: "\n") { XCTAssertLessThanOrEqual(line.count, Receipt.width, String(line)) }
    }

    func testTheGalleryRoundTripsThroughTheDatabase() throws {
        let f = try FX.load()
        let db = try AppDatabase(path: nil)
        let g = FX.gallery(from: f)
        try db.saveGallery(g)
        let back = try db.loadGallery(dim: f.embedder.dim)
        XCTAssertEqual(back.count, g.count)
        XCTAssertTrue(back.frozen)
        let q = f.embeddings[f.expected_matches.keys.sorted()[0]]!
        XCTAssertEqual(back.match(q)[0].score, g.match(q)[0].score, accuracy: 1e-6)
    }
}

final class RestrictionsTests: XCTestCase {
    private func at(_ h: Int, _ m: Int) -> Date { Calendar.current.date(bySettingHour: h, minute: m, second: 0, of: Date())! }

    func testAlcoholHours() {
        XCTAssertFalse(Restrictions.saleGate(.alcohol, staffConfirmed: true, now: at(10, 59)).ok)
        XCTAssertTrue(Restrictions.saleGate(.alcohol, staffConfirmed: true, now: at(11, 0)).ok)
        XCTAssertTrue(Restrictions.saleGate(.alcohol, staffConfirmed: true, now: at(23, 30)).ok)
        let g = Restrictions.saleGate(.alcohol, staffConfirmed: false, now: at(15, 0))
        XCTAssertFalse(g.ok); XCTAssertTrue(g.needsStaff)
    }

    func testTobaccoIsStaffOnlyAndNeverShown() {
        XCTAssertTrue(Restrictions.saleGate(.tobacco, staffConfirmed: false).needsStaff)
        XCTAssertTrue(Restrictions.saleGate(.tobacco, staffConfirmed: true).ok)
        XCTAssertFalse(Restrictions.customerVisible(.tobacco))
        XCTAssertTrue(Restrictions.customerVisible(.alcohol))
    }
}
