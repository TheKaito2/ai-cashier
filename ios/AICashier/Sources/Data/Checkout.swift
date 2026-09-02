import Foundation

struct CheckoutError: LocalizedError {
    let status: Int
    let message: String
    var needsStaff = false
    var errorDescription: String? { message }
}

struct CartLine: Identifiable, Equatable {
    var product: Product
    var quantity: Int
    var id: String { product.id }
    var subtotal: Double { product.price * Double(quantity) }
}

/// Cart -> payment -> sale, as functions over the database
/// (`server/services/checkout.py`).  Stock is not taken down here; that
/// happens in `confirm`, in one transaction.
enum Checkout {
    static func createPayment(_ db: AppDatabase, items: [(productId: String, quantity: Int)],
                              staffConfirmed: Bool = false, now: Date = Date()) throws -> PendingPayment {
        var merged: [(String, Int)] = []
        for (pid, qty) in items {
            guard qty > 0 else { throw CheckoutError(status: 400, message: "\(pid): quantity must be positive") }
            if let i = merged.firstIndex(where: { $0.0 == pid }) { merged[i].1 += qty } else { merged.append((pid, qty)) }
        }
        var lines: [SaleLine] = []
        for (pid, qty) in merged {
            guard let p = try db.product(pid) else { throw CheckoutError(status: 404, message: "Product \(pid) not found") }
            guard p.stock >= qty else {
                throw CheckoutError(status: 400, message: "Not enough stock for \(p.name): \(p.stock) left")
            }
            let gate = Restrictions.saleGate(p.restricted, staffConfirmed: staffConfirmed, now: now)
            guard gate.ok else { throw CheckoutError(status: 403, message: gate.reason, needsStaff: gate.needsStaff) }
            if p.restricted != .none {
                try db.logEvent("override", ["kind": "restricted_sale", "product_id": pid, "restricted": p.restricted.rawValue])
            }
            lines.append(SaleLine(productId: pid, productName: p.name, quantity: qty, price: p.price, total: p.price * Double(qty)))
        }
        guard !lines.isEmpty else { throw CheckoutError(status: 400, message: "The cart is empty") }

        let settings = try db.settings()
        let subtotal = lines.reduce(0) { $0 + $1.total }
        let tax = subtotal * settings.taxRate
        let total = subtotal + tax
        let paymentId = UUID().uuidString.lowercased()

        var payload: String
        var payable: Bool
        if !settings.promptpayId.isEmpty, let p = try? PromptPay.buildPayload(target: settings.promptpayId, amount: (total * 100).rounded() / 100) {
            payload = p; payable = true
        } else {
            // never show a code that looks real but cannot be paid
            payload = "NOT-CONFIGURED|" + String(format: "%.2f", total) + "|" + paymentId; payable = false
        }
        let pending = PendingPayment(paymentId: paymentId, timestamp: now, items: lines, subtotal: subtotal,
                                     tax: tax, total: total, status: "pending", qrPayload: payload, payable: payable)
        try db.addPending(pending)
        return pending
    }

    static func confirm(_ db: AppDatabase, paymentId: String) throws -> Sale {
        guard let p = try db.pending(paymentId) else { throw CheckoutError(status: 404, message: "Payment not found") }
        guard p.status == "pending" else { throw CheckoutError(status: 400, message: "Payment already processed") }
        guard let sale = try db.processPending(paymentId) else { throw CheckoutError(status: 400, message: "Failed to process payment") }
        return sale
    }
}
