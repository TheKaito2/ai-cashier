import CoreGraphics
import Foundation
import SwiftUI
import UIKit

/// Everything the screens share: the pipeline, the camera, the cart, the
/// database.  The till in `scanner/ui/main_window.py`, minus the scale.
@MainActor
final class Store: ObservableObject {
    @Published var preview: CGImage?
    @Published var detected: [RecognisedItem] = []
    @Published var cart: [CartLine] = []
    @Published var status = "Ready"
    @Published var scanning = false
    @Published var products: [Product] = []
    @Published var settings = ShopSettings()
    @Published var pendingPayment: PendingPayment?
    @Published var lastSale: Sale?
    @Published var matCalibrated = false
    @Published var useDemoCamera: Bool { didSet { switchCamera() } }
    @Published var exposureLocked = false { didSet { camera.setLocked(exposureLocked) } }
    @Published var errorText: String?

    let db: AppDatabase
    let pipeline: RecognitionPipeline
    private(set) var camera: FrameSource
    private var previewTimer: Timer?
    static let scanFrames = 5

    init(db: AppDatabase? = nil) {
        do {
            let database = try db ?? AppDatabase.onDisk()
            self.db = database
            let embedder = try CoreMLEmbedder()
            let gallery = try database.loadGallery(dim: embedder.dim)
            var cfg = FusionConfig()
            let s = (try? database.settings()) ?? ShopSettings()
            if let t = s.rejectBelowCosine { cfg.rejectBelowCosine = Float(t) }
            pipeline = RecognitionPipeline(proposer: BackgroundSubtractionProposer(), embedder: embedder, gallery: gallery, cfg: cfg)
            settings = s
        } catch {
            fatalError("AI Cashier cannot start: \(error)")
        }
        let demo = !CameraSession.isAvailable
        camera = demo ? DemoCamera() : CameraSession()
        _useDemoCamera = Published(initialValue: demo)
        if let mat = Self.loadMat() { pipeline.calibrate(mat); matCalibrated = true }
        reloadProducts()
        camera.start()
        previewTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshPreview() }
        }
    }

    private func switchCamera() {
        camera.stop()
        camera = useDemoCamera ? DemoCamera() : CameraSession()
        camera.start()
    }

    private func refreshPreview() {
        if let f = camera.latest() { preview = f.cgImage() }
    }

    func reloadProducts() {
        products = (try? db.products()) ?? []
        settings = (try? db.settings()) ?? ShopSettings()
    }

    // MARK: - mat

    private static var matURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("AICashier/mat_background.png")
    }

    private static func loadMat() -> Frame? {
        guard let ui = UIImage(contentsOfFile: matURL.path), let cg = ui.cgImage else { return nil }
        return Frame(cgImage: cg)
    }

    /// Photograph the empty mat.  This is the one picture the app keeps, taken
    /// by staff with nobody in shot.
    func calibrateMat() {
        guard let frame = camera.latest() else { status = "No camera frame"; return }
        pipeline.calibrate(frame)
        matCalibrated = true
        if let cg = frame.cgImage() {
            try? FileManager.default.createDirectory(at: Self.matURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? UIImage(cgImage: cg).pngData()?.write(to: Self.matURL)
        }
        status = "Mat calibrated"
    }

    // MARK: - scan

    func scan() {
        guard pipeline.proposer.isCalibrated else { errorText = "Calibrate the mat first: clear it and press Calibrate."; return }
        guard !scanning else { return }
        scanning = true
        status = "Scanning..."
        let pipeline = self.pipeline
        let camera = self.camera
        Task.detached(priority: .userInitiated) {
            var items: [RecognisedItem] = []
            var error: String?
            do {
                pipeline.reset()
                for _ in 0..<Store.scanFrames {
                    guard let frame = camera.latest() else { error = "No camera frame"; break }
                    items = try pipeline.process(frame)
                }
            } catch let e { error = "Scan failed: \(e.localizedDescription)" }
            let result = items, failure = error
            await MainActor.run { self.finishScan(result, failure) }
        }
    }

    private func finishScan(_ items: [RecognisedItem], _ error: String?) {
        scanning = false
        if let e = error { status = e; return }
        detected = items
        for item in items where item.status != .accepted {
            try? db.logEvent("abstention", ["status": item.status.rawValue, "top_sku": item.decision.top?.skuId ?? "",
                                            "score": String(format: "%.3f", (item.decision.top?.appearance ?? 0) * pipeline.cfg.appearanceTemperature)])
        }
        let unknown = items.filter { $0.status == .unknown }.count
        status = items.isEmpty ? "Nothing on the mat - place the products and scan again"
            : unknown > 0 ? "\(items.count - unknown) recognised, \(unknown) not in the gallery"
            : "Recognised \(items.count) product(s)"
    }

    func product(for item: RecognisedItem) -> Product? {
        item.skuId.flatMap { id in products.first { $0.id == id } }
    }

    /// Recognised, priced, legal to sell right now.
    var sellable: [(RecognisedItem, Product)] {
        detected.compactMap { item in
            guard item.status != .unknown, let p = product(for: item) else { return nil }
            return Restrictions.saleGate(p.restricted, staffConfirmed: true).ok ? (item, p) : nil
        }
    }

    var restrictedInDetected: [Product] { sellable.map(\.1).filter { $0.restricted != .none } }

    func dismiss(_ item: RecognisedItem) { detected.removeAll { $0.id == item.id } }

    func choose(_ item: RecognisedItem, sku: String) {
        guard let i = detected.firstIndex(where: { $0.id == item.id }) else { return }
        let d = item.decision
        let decision = Decision(status: .accepted, skuId: sku, candidates: d.candidates, margin: d.margin)
        detected[i] = RecognisedItem(trackId: item.trackId, box: item.box, decision: decision, agreement: item.agreement, hits: item.hits)
        try? db.logEvent("override", ["kind": "disambiguate", "chosen": sku])
        status = "Operator chose the product by hand"
    }

    // MARK: - cart

    func addToCart(staffConfirmed: Bool) {
        let lines = sellable
        guard !lines.isEmpty else { return }
        if !restrictedInDetected.isEmpty {
            try? db.logEvent("override", ["kind": "restricted_confirm", "confirmed": staffConfirmed ? "true" : "false"])
            guard staffConfirmed else { status = "Restricted items not added - ID check not confirmed"; return }
        }
        var short: [String] = []
        for (_, p) in lines {
            let have = cart.first { $0.product.id == p.id }?.quantity ?? 0
            guard have + 1 <= p.stock else { short.append("\(p.name): only \(p.stock) left"); continue }
            if let i = cart.firstIndex(where: { $0.product.id == p.id }) { cart[i].quantity += 1 } else { cart.append(CartLine(product: p, quantity: 1)) }
        }
        if !short.isEmpty { errorText = short.joined(separator: "\n") }
        detected = []
        status = "Added \(lines.count - short.count) item(s) to the cart"
    }

    func setQuantity(_ id: String, _ q: Int) {
        if q <= 0 { cart.removeAll { $0.id == id } }
        else if let i = cart.firstIndex(where: { $0.id == id }), q <= cart[i].product.stock { cart[i].quantity = q }
    }

    func clearCart() { cart = []; status = "Cart cleared" }

    var subtotal: Double { cart.reduce(0) { $0 + $1.subtotal } }
    var tax: Double { subtotal * settings.taxRate }
    var total: Double { subtotal + tax }

    // MARK: - pay

    func checkout() {
        do {
            let restricted = cart.contains { $0.product.restricted != .none }
            pendingPayment = try Checkout.createPayment(db, items: cart.map { ($0.product.id, $0.quantity) }, staffConfirmed: restricted)
        } catch {
            errorText = error.localizedDescription
        }
    }

    func confirmPayment() {
        guard let p = pendingPayment else { return }
        do {
            lastSale = try Checkout.confirm(db, paymentId: p.paymentId)
            cart = []
            pendingPayment = nil
            reloadProducts()
            status = "Paid " + settings.currency + String(format: "%.2f", p.total) + " - stock updated"
        } catch {
            errorText = error.localizedDescription
        }
    }

    func cancelPayment() { pendingPayment = nil; status = "Payment cancelled - nothing was charged" }

    // MARK: - teach

    func enrol(name: String, price: Double, category: String, stock: Int, restricted: Restriction, frames: [Frame]) throws {
        let sku = Self.slug(name)
        let views = try pipeline.enrol(sku, frames: frames)
        if !pipeline.gallery.frozen && pipeline.gallery.skus.count >= SkuGallery.minSkusToFreeze {
            pipeline.gallery.freezeCentre()
        }
        try db.saveGallery(pipeline.gallery)
        try db.upsert(Product(id: sku, name: name, price: price, category: category, stock: stock, restricted: restricted))
        try db.logEvent("enrolment", ["sku_id": sku, "views": String(views), "restricted": restricted.rawValue])
        reloadProducts()
        detected = []
        status = "\(name) enrolled from \(views) views - on sale at " + settings.currency + String(format: "%.2f", price)
    }

    func removeProduct(_ id: String) {
        pipeline.gallery.remove(id)
        try? db.saveGallery(pipeline.gallery)
        try? db.delete(id)
        reloadProducts()
    }

    func saveSettings() {
        try? db.save(settings)
        if let t = settings.rejectBelowCosine { pipeline.cfg.rejectBelowCosine = Float(t) }
    }

    static func slug(_ name: String) -> String {
        let lowered = name.lowercased()
        var out = ""
        var dash = false
        for ch in lowered {
            if ch.isLetter || ch.isNumber { out.append(ch); dash = false }
            else if !dash && !out.isEmpty { out.append("-"); dash = true }
        }
        while out.hasSuffix("-") { out.removeLast() }
        return out.isEmpty ? "product" : out
    }
}
