import Foundation
import GRDB

struct Product: Identifiable, Equatable, Codable {
    var id: String
    var name: String
    var price: Double
    var category: String
    var stock: Int
    var minStock: Int = 5
    var size: String? = nil
    var description: String? = nil
    var weightG: Double? = nil
    var restricted: Restriction = .none
}

struct SaleLine: Codable, Equatable {
    var productId: String
    var productName: String
    var quantity: Int
    var price: Double
    var total: Double
}

struct PendingPayment: Codable {
    var paymentId: String
    var timestamp: Date
    var items: [SaleLine]
    var subtotal: Double
    var tax: Double
    var total: Double
    var status: String
    var qrPayload: String
    var payable: Bool
}

struct Sale: Identifiable {
    var id: String
    var timestamp: Date
    var subtotal: Double
    var tax: Double
    var total: Double
    var paymentId: String?
    var items: [SaleLine]
}

struct ShopSettings: Codable, Equatable {
    var storeName = "AI Cashier"
    var storeAddress = ""
    var taxRate = 0.07
    var currency = "฿"
    var promptpayId = ""
    var vatRegistered = false
    var tin = ""
    var rejectBelowCosine: Double? = nil
}

struct Analytics {
    var totalSales = 0, todaySales = 0
    var totalRevenue = 0.0, todayRevenue = 0.0
    var topProducts: [(name: String, quantity: Int, revenue: Double)] = []
    var lowStockCount = 0
}

struct Event: Identifiable {
    var id: Int64
    var timestamp: Date
    var kind: String
    var payload: [String: String]
}

/// The shop's records, in SQLite through GRDB: the same tables as
/// `server/services/database.py`, so a phone and a till keep books the same
/// way.  A sale is one transaction: stock down, sale written, payment closed,
/// or none of it.
final class AppDatabase {
    let dbQueue: DatabaseQueue

    init(path: String?) throws {
        dbQueue = try path.map { try DatabaseQueue(path: $0) } ?? DatabaseQueue()
        try migrator.migrate(dbQueue)
    }

    static func onDisk() throws -> AppDatabase {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("AICashier", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return try AppDatabase(path: dir.appendingPathComponent("checkout.sqlite3").path)
    }

    private var migrator: DatabaseMigrator {
        var m = DatabaseMigrator()
        m.registerMigration("v1") { db in
            try db.execute(sql: """
                CREATE TABLE products (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, price REAL NOT NULL CHECK (price >= 0),
                    category TEXT NOT NULL, stock INTEGER NOT NULL CHECK (stock >= 0),
                    min_stock INTEGER NOT NULL DEFAULT 0, size TEXT, description TEXT, weight_g REAL,
                    restricted TEXT NOT NULL DEFAULT 'none');
                CREATE TABLE sales (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, subtotal REAL NOT NULL,
                    tax REAL NOT NULL, total REAL NOT NULL, payment_id TEXT);
                CREATE TABLE sale_items (sale_id TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                    product_id TEXT NOT NULL, product_name TEXT NOT NULL, quantity INTEGER NOT NULL,
                    price REAL NOT NULL, total REAL NOT NULL);
                CREATE TABLE pending_payments (payment_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', payload TEXT NOT NULL);
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE gallery (sku_id TEXT NOT NULL, vector BLOB NOT NULL);
                CREATE INDEX idx_events_kind ON events(kind, timestamp);
                CREATE INDEX idx_sales_time ON sales(timestamp);
                CREATE INDEX idx_items_sale ON sale_items(sale_id);
                CREATE INDEX idx_gallery_sku ON gallery(sku_id);
                """)
        }
        return m
    }

    // MARK: - products

    private func product(_ r: Row) -> Product {
        Product(id: r["id"], name: r["name"], price: r["price"], category: r["category"], stock: r["stock"],
                minStock: r["min_stock"], size: r["size"], description: r["description"], weightG: r["weight_g"],
                restricted: Restriction(rawValue: r["restricted"] ?? "none") ?? .none)
    }

    func products() throws -> [Product] {
        try dbQueue.read { db in try Row.fetchAll(db, sql: "SELECT * FROM products ORDER BY rowid").map(product) }
    }

    func product(_ id: String) throws -> Product? {
        try dbQueue.read { db in try Row.fetchOne(db, sql: "SELECT * FROM products WHERE id = ?", arguments: [id]).map(product) }
    }

    func upsert(_ p: Product) throws {
        try dbQueue.write { db in
            try db.execute(sql: """
                INSERT INTO products (id, name, price, category, stock, min_stock, size, description, weight_g, restricted)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, price=excluded.price, category=excluded.category,
                    stock=excluded.stock, min_stock=excluded.min_stock, size=excluded.size,
                    description=excluded.description, weight_g=excluded.weight_g, restricted=excluded.restricted
                """, arguments: [p.id, p.name, p.price, p.category, p.stock, p.minStock, p.size, p.description,
                                 p.weightG, p.restricted.rawValue])
        }
    }

    func delete(_ id: String) throws {
        try dbQueue.write { db in
            try db.execute(sql: "DELETE FROM products WHERE id = ?", arguments: [id])
            try db.execute(sql: "DELETE FROM gallery WHERE sku_id = ?", arguments: [id])
        }
    }

    /// Change stock in one statement, so two sales cannot lose an update.
    @discardableResult
    func updateStock(_ id: String, delta: Int) throws -> Bool {
        try dbQueue.write { db in
            try db.execute(sql: "UPDATE products SET stock = stock + ? WHERE id = ? AND stock + ? >= 0",
                           arguments: [delta, id, delta])
            return db.changesCount > 0
        }
    }

    // MARK: - payments and sales

    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    static func stamp(_ d: Date) -> String { iso.string(from: d) }
    static func date(_ s: String) -> Date { iso.date(from: s) ?? ISO8601DateFormatter().date(from: s) ?? Date() }

    func addPending(_ p: PendingPayment) throws {
        let json = try JSONEncoder().encode(p)
        try dbQueue.write { db in
            try db.execute(sql: "INSERT OR REPLACE INTO pending_payments (payment_id, timestamp, status, payload) VALUES (?,?,?,?)",
                           arguments: [p.paymentId, Self.stamp(p.timestamp), p.status, String(decoding: json, as: UTF8.self)])
        }
    }

    func pending(_ id: String) throws -> PendingPayment? {
        try dbQueue.read { db in
            guard let r = try Row.fetchOne(db, sql: "SELECT payload, status FROM pending_payments WHERE payment_id = ?", arguments: [id]) else { return nil }
            var p = try JSONDecoder().decode(PendingPayment.self, from: Data((r["payload"] as String).utf8))
            p.status = r["status"]
            return p
        }
    }

    /// Turn a pending payment into a sale: one transaction, or nothing.
    func processPending(_ id: String) throws -> Sale? {
        try dbQueue.write { db in
            guard let r = try Row.fetchOne(db, sql: "SELECT payload FROM pending_payments WHERE payment_id = ? AND status = 'pending'", arguments: [id]) else { return nil }
            let p = try JSONDecoder().decode(PendingPayment.self, from: Data((r["payload"] as String).utf8))
            for it in p.items {
                try db.execute(sql: "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                               arguments: [it.quantity, it.productId, it.quantity])
                if db.changesCount == 0 { throw CheckoutError(status: 409, message: "\(it.productName) sold out between checkout and payment") }
            }
            let now = Date()
            let f = DateFormatter(); f.dateFormat = "yyyyMMddHHmmss"
            let saleId = "SALE-\(f.string(from: now))-\(p.paymentId.prefix(8))"
            try db.execute(sql: "INSERT INTO sales (id, timestamp, subtotal, tax, total, payment_id) VALUES (?,?,?,?,?,?)",
                           arguments: [saleId, Self.stamp(now), p.subtotal, p.tax, p.total, p.paymentId])
            for it in p.items {
                try db.execute(sql: "INSERT INTO sale_items (sale_id, product_id, product_name, quantity, price, total) VALUES (?,?,?,?,?,?)",
                               arguments: [saleId, it.productId, it.productName, it.quantity, it.price, it.total])
            }
            try db.execute(sql: "UPDATE pending_payments SET status = 'completed' WHERE payment_id = ?", arguments: [id])
            return Sale(id: saleId, timestamp: now, subtotal: p.subtotal, tax: p.tax, total: p.total, paymentId: p.paymentId, items: p.items)
        }
    }

    private func sale(_ db: Database, _ r: Row) throws -> Sale {
        let items = try Row.fetchAll(db, sql: "SELECT * FROM sale_items WHERE sale_id = ?", arguments: [r["id"] as String]).map {
            SaleLine(productId: $0["product_id"], productName: $0["product_name"], quantity: $0["quantity"], price: $0["price"], total: $0["total"])
        }
        return Sale(id: r["id"], timestamp: Self.date(r["timestamp"]), subtotal: r["subtotal"], tax: r["tax"], total: r["total"],
                    paymentId: r["payment_id"], items: items)
    }

    func sale(_ id: String) throws -> Sale? {
        try dbQueue.read { db in
            guard let r = try Row.fetchOne(db, sql: "SELECT * FROM sales WHERE id = ?", arguments: [id]) else { return nil }
            return try sale(db, r)
        }
    }

    func sales(limit: Int = 50) throws -> [Sale] {
        try dbQueue.read { db in
            try Row.fetchAll(db, sql: "SELECT * FROM sales ORDER BY timestamp DESC LIMIT ?", arguments: [limit]).map { try sale(db, $0) }
        }
    }

    func analytics() throws -> Analytics {
        try dbQueue.read { db in
            var a = Analytics()
            let today = Self.stamp(Calendar.current.startOfDay(for: Date()))
            if let r = try Row.fetchOne(db, sql: "SELECT COUNT(*) n, COALESCE(SUM(total),0) rev FROM sales") {
                a.totalSales = r["n"]; a.totalRevenue = r["rev"]
            }
            if let r = try Row.fetchOne(db, sql: "SELECT COUNT(*) n, COALESCE(SUM(total),0) rev FROM sales WHERE timestamp >= ?", arguments: [today]) {
                a.todaySales = r["n"]; a.todayRevenue = r["rev"]
            }
            a.topProducts = try Row.fetchAll(db, sql: """
                SELECT COALESCE(p.name, i.product_name) name, SUM(i.quantity) q, SUM(i.total) rev
                FROM sale_items i LEFT JOIN products p ON p.id = i.product_id
                GROUP BY i.product_id ORDER BY rev DESC LIMIT 10
                """).map { ($0["name"], $0["q"], $0["rev"]) }
            a.lowStockCount = try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM products WHERE stock <= min_stock") ?? 0
            return a
        }
    }

    // MARK: - settings

    func settings() throws -> ShopSettings {
        try dbQueue.read { db in
            guard let json = try String.fetchOne(db, sql: "SELECT value FROM settings WHERE key = 'shop'") else { return ShopSettings() }
            return (try? JSONDecoder().decode(ShopSettings.self, from: Data(json.utf8))) ?? ShopSettings()
        }
    }

    func save(_ s: ShopSettings) throws {
        let json = String(decoding: try JSONEncoder().encode(s), as: UTF8.self)
        try dbQueue.write { db in
            try db.execute(sql: "INSERT OR REPLACE INTO settings (key, value) VALUES ('shop', ?)", arguments: [json])
        }
    }

    // MARK: - deployment log

    static let eventKinds: Set<String> = ["enrolment", "abstention", "override", "basket_check"]

    @discardableResult
    func logEvent(_ kind: String, _ payload: [String: String]) throws -> Int64 {
        precondition(Self.eventKinds.contains(kind), "unknown event kind \(kind)")
        let json = String(decoding: try JSONEncoder().encode(payload), as: UTF8.self)
        return try dbQueue.write { db in
            try db.execute(sql: "INSERT INTO events (timestamp, kind, payload) VALUES (?,?,?)",
                           arguments: [Self.stamp(Date()), kind, json])
            return db.lastInsertedRowID
        }
    }

    func events(kind: String? = nil, limit: Int = 200) throws -> [Event] {
        try dbQueue.read { db in
            let rows = kind == nil
                ? try Row.fetchAll(db, sql: "SELECT * FROM events ORDER BY id DESC LIMIT ?", arguments: [limit])
                : try Row.fetchAll(db, sql: "SELECT * FROM events WHERE kind = ? ORDER BY id DESC LIMIT ?", arguments: [kind!, limit])
            return rows.map {
                Event(id: $0["id"], timestamp: Self.date($0["timestamp"]), kind: $0["kind"],
                      payload: (try? JSONDecoder().decode([String: String].self, from: Data(($0["payload"] as String).utf8))) ?? [:])
            }
        }
    }

    // MARK: - gallery persistence (vectors only, never pixels)

    func loadGallery(dim: Int) throws -> SkuGallery {
        let g = SkuGallery(dim: dim)
        try dbQueue.read { db in
            for r in try Row.fetchAll(db, sql: "SELECT sku_id, vector FROM gallery ORDER BY rowid") {
                let data: Data = r["vector"]
                let v = data.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
                if v.count == dim { g.enrol(r["sku_id"], [v]) }
            }
            if let json = try String.fetchOne(db, sql: "SELECT value FROM settings WHERE key = 'gallery_centre'"),
               let c = try? JSONDecoder().decode([Float].self, from: Data(json.utf8)), c.count == dim {
                g.setCentre(c)
            }
        }
        return g
    }

    func saveGallery(_ g: SkuGallery) throws {
        try dbQueue.write { db in
            try db.execute(sql: "DELETE FROM gallery")
            for (sku, v) in zip(g.skuIds, g.vectors) {
                let data = v.withUnsafeBufferPointer { Data(buffer: $0) }
                try db.execute(sql: "INSERT INTO gallery (sku_id, vector) VALUES (?, ?)", arguments: [sku, data])
            }
            if let c = g.centre {
                let json = String(decoding: try JSONEncoder().encode(c), as: UTF8.self)
                try db.execute(sql: "INSERT OR REPLACE INTO settings (key, value) VALUES ('gallery_centre', ?)", arguments: [json])
            } else {
                try db.execute(sql: "DELETE FROM settings WHERE key = 'gallery_centre'")
            }
        }
    }
}
