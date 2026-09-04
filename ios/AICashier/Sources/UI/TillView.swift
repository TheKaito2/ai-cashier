import SwiftUI

struct TillView: View {
    @EnvironmentObject var store: Store
    @State private var showEnrol = false
    @State private var showStaffConfirm = false
    @State private var chooseFor: RecognisedItem?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    CameraPreview()
                    readouts
                    detectedPanel
                    HStack(spacing: 10) {
                        Button(action: store.scan) { Text(store.scanning ? "SCANNING…" : "SCAN PRODUCTS") }
                            .buttonStyle(BigButtonStyle(fill: Theme.accent)).disabled(store.scanning)
                        Button {
                            if store.restrictedInDetected.isEmpty { store.addToCart(staffConfirmed: false) } else { showStaffConfirm = true }
                        } label: {
                            Text(store.sellable.count > 1 ? "Add \(store.sellable.count)" : "Add to cart").frame(minWidth: 96, minHeight: 56)
                        }
                        .buttonStyle(QuietButtonStyle()).disabled(store.sellable.isEmpty)
                    }
                    CartPanel()
                    Text(store.status).font(Theme.mono(12)).foregroundStyle(Theme.muted)
                }
                .padding()
            }
            .background(Theme.bg)
            .navigationTitle("AI Cashier")
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button(action: store.calibrateMat) { Text("Calibrate mat").font(Theme.sans(15, .medium)) }
                    Button { showEnrol = true } label: { Text("Add product").font(Theme.sans(15, .medium)) }
                }
            }
            .sheet(isPresented: $showEnrol) { EnrolView() }
            .sheet(item: $store.pendingPayment) { _ in PaymentView() }
            .alert("Age-restricted item", isPresented: $showStaffConfirm) {
                Button("ID checked - confirm") { store.addToCart(staffConfirmed: true) }
                Button("Cancel", role: .cancel) { store.addToCart(staffConfirmed: false) }
            } message: {
                Text("A member of staff must check the buyer's ID (20 or over) and that they are not intoxicated before this can be sold.")
            }
            .confirmationDialog("Which one is it?", isPresented: Binding(get: { chooseFor != nil }, set: { if !$0 { chooseFor = nil } })) {
                if let item = chooseFor {
                    ForEach(item.decision.candidates.prefix(3), id: \.skuId) { c in
                        Button(store.products.first { $0.id == c.skuId }?.name ?? c.skuId) { store.choose(item, sku: c.skuId) }
                    }
                }
            }
            .alert("Problem", isPresented: Binding(get: { store.errorText != nil }, set: { if !$0 { store.errorText = nil } })) {
                Button("OK", role: .cancel) {}
            } message: { Text(store.errorText ?? "") }
        }
    }

    /// Instrument readouts under the frame, as on the till.
    private var readouts: some View {
        HStack {
            Text("GALLERY \(store.pipeline.gallery.skus.count) products · \(store.pipeline.gallery.count) views")
            Spacer()
            Text(store.matCalibrated ? "MAT calibrated" : "MAT NOT CALIBRATED")
                .foregroundStyle(store.matCalibrated ? Theme.muted : Theme.bad)
        }
        .font(Theme.mono(11)).foregroundStyle(Theme.muted).padding(.horizontal, 2)
    }

    private var detectedPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            Eyebrow(text: "Just detected")
            if store.detected.isEmpty {
                Text(store.matCalibrated ? "Place products under the camera, then press SCAN."
                                         : "Clear the mat and press Calibrate mat once.")
                    .font(Theme.sans(15)).foregroundStyle(Theme.muted).padding(.vertical, 6)
            }
            ForEach(store.detected) { item in
                DetectedChip(item: item, product: store.product(for: item),
                             onDismiss: { store.dismiss(item) },
                             onEnrol: { showEnrol = true },
                             onChoose: { chooseFor = item })
            }
        }
    }
}

extension PendingPayment: Identifiable { var id: String { paymentId } }

/// The camera is the hero.  Boxes and prices are drawn on the frame itself,
/// and the border carries the state: scanning, unknown, ambiguous, ready.
struct CameraPreview: View {
    @EnvironmentObject var store: Store
    var body: some View {
        ZStack(alignment: .bottomLeading) {
            if let img = store.preview {
                Image(decorative: img, scale: 1, orientation: .up).resizable().aspectRatio(contentMode: .fit)
                    .overlay { DetectionOverlay(imageWidth: img.width) }
            } else {
                Rectangle().fill(Theme.viewfinder).aspectRatio(16 / 9, contentMode: .fit)
                    .overlay(Text("NO CAMERA").font(Theme.mono(12)).kerning(1.2).foregroundStyle(Theme.muted))
            }
            HStack(spacing: 6) {
                Circle().fill(store.matCalibrated ? Theme.ok : Theme.warn).frame(width: 8, height: 8)
                Text(store.matCalibrated ? "mat calibrated" : "mat not calibrated")
                Text("· \(store.camera.name)")
            }
            .font(Theme.mono(11)).padding(.horizontal, 10).padding(.vertical, 6)
            .background(.ultraThinMaterial, in: Capsule()).padding(8)
        }
        .background(Theme.viewfinder)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(borderColour, lineWidth: 2))
    }

    private var borderColour: Color {
        if store.scanning { return Theme.accent }
        if store.detected.isEmpty { return Theme.line }
        if store.detected.contains(where: { $0.status == .unknown }) { return Theme.accent }
        if store.detected.contains(where: { $0.status == .ambiguous }) { return Theme.info }
        return Theme.ok
    }
}

struct DetectionOverlay: View {
    @EnvironmentObject var store: Store
    let imageWidth: Int

    var body: some View {
        Canvas { ctx, size in
            let s = size.width / CGFloat(imageWidth)
            for item in store.detected {
                let b = item.box
                let rect = CGRect(x: CGFloat(b.x1) * s, y: CGFloat(b.y1) * s,
                                  width: CGFloat(b.width) * s, height: CGFloat(b.height) * s)
                let colour = Theme.status(item.status)
                ctx.stroke(Path(rect), with: .color(colour), lineWidth: 3)
                // the label may not be wider than its box, or neighbours overprint each other
                let full = caption(item)
                var text = full
                var label = ctx.resolve(Text(text).font(Theme.mono(11, .semibold)).foregroundStyle(Theme.onAccent))
                var ts = label.measure(in: CGSize(width: size.width, height: 40))
                let maxWidth = max(rect.width + 2, 72)
                var keep = full.count
                while ts.width + 14 > maxWidth, keep > 4 {
                    keep -= 1
                    text = String(full.prefix(keep)).trimmingCharacters(in: .whitespaces) + "…"
                    label = ctx.resolve(Text(text).font(Theme.mono(11, .semibold)).foregroundStyle(Theme.onAccent))
                    ts = label.measure(in: CGSize(width: size.width, height: 40))
                }
                let tag = CGRect(x: rect.minX - 1, y: rect.minY >= ts.height + 8 ? rect.minY - ts.height - 8 : rect.maxY,
                                 width: ts.width + 14, height: ts.height + 8)
                ctx.fill(Path(tag), with: .color(colour))
                ctx.draw(label, at: CGPoint(x: tag.minX + 7, y: tag.minY + 4), anchor: .topLeading)
            }
        }
        .allowsHitTesting(false)
    }

    private func caption(_ item: RecognisedItem) -> String {
        guard item.status != .unknown, let p = store.product(for: item) else { return "UNKNOWN · TEACH" }
        if item.status == .ambiguous { return "? \(p.name)" }
        return "\(store.settings.currency)\(Int(p.price.rounded()))  \(p.name)"      // price first: it survives truncation
    }
}

struct DetectedChip: View {
    let item: RecognisedItem
    let product: Product?
    let onDismiss: () -> Void
    let onEnrol: () -> Void
    let onChoose: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Rectangle().fill(colour).frame(width: 4)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(Theme.sans(16, .semibold)).foregroundStyle(Theme.ink)
                Text(subtitle).font(Theme.mono(11)).foregroundStyle(Theme.muted)
            }
            Spacer(minLength: 6)
            if let p = product, item.status != .unknown {
                Text(baht(p.price)).font(Theme.mono(16, .semibold)).foregroundStyle(Theme.accentInk)
            }
            if item.status == .unknown { Button("Teach", action: onEnrol).buttonStyle(QuietButtonStyle()) }
            if item.status == .ambiguous { Button("Choose", action: onChoose).buttonStyle(QuietButtonStyle()) }
            Button(action: onDismiss) { Image(systemName: "xmark") }.buttonStyle(QuietButtonStyle())
                .padding(.trailing, 10)
        }
        .padding(.vertical, 10)
        .background(Theme.surface2)
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.line))
    }

    private var colour: Color { Theme.status(item.status) }

    private var title: String {
        if item.status == .unknown { return "Unknown item" }
        return product?.name ?? item.skuId ?? "Unknown"
    }

    private var subtitle: String {
        if item.status == .unknown { return "not in the gallery - teach it or call staff" }
        guard let p = product else { return "recognised, but not priced" }
        if p.restricted != .none { return "\(p.restricted.rawValue.uppercased()) - staff must check ID (20+)" }
        if item.status == .ambiguous, item.decision.candidates.count > 1 { return "not sure - could be \(item.decision.candidates[1].skuId)" }
        return "\(p.category) · \(Int((item.agreement * 100).rounded()))% of frames agreed"
    }
}

/// The cart, set the way the receipt will print: paper, mono, a torn edge.
struct CartPanel: View {
    @EnvironmentObject var store: Store

    var body: some View {
        VStack(spacing: 12) {
            ReceiptCard {
                VStack(spacing: 3) {
                    Text(store.settings.storeName.uppercased()).font(Theme.mono(13, .semibold)).frame(maxWidth: .infinity)
                    Text(store.settings.vatRegistered ? "TAX INVOICE (ABB)" : "ใบเสร็จรับเงิน / RECEIPT")
                        .font(Theme.mono(11)).foregroundStyle(Theme.paperMuted).frame(maxWidth: .infinity)
                    Text("\(count) item\(count == 1 ? "" : "s")")
                        .font(Theme.mono(11)).foregroundStyle(Theme.paperMuted).frame(maxWidth: .infinity)
                    rule
                    if store.cart.isEmpty {
                        Text("NOTHING SCANNED YET").font(Theme.mono(11)).foregroundStyle(Theme.paperMuted).padding(.vertical, 12)
                    }
                    ForEach(store.cart) { line in ReceiptLine(line: line) }
                    rule
                    money("Subtotal", store.subtotal)
                    money("VAT \(Int((store.settings.taxRate * 100).rounded()))%", store.tax)
                    HStack(alignment: .firstTextBaseline) {
                        Text("TOTAL").font(Theme.mono(13, .semibold))
                        Spacer()
                        Text(baht(store.total, store.settings.currency)).font(Theme.mono(30, .semibold))
                    }
                    Text("ขอบคุณค่ะ / THANK YOU").font(Theme.mono(11)).foregroundStyle(Theme.paperMuted)
                        .frame(maxWidth: .infinity).padding(.top, 4)
                }
            }
            Button(action: store.checkout) {
                Text(store.cart.isEmpty ? "PAY" : "PAY  \(baht(store.total, store.settings.currency))")
            }
            .buttonStyle(BigButtonStyle(fill: Theme.ok)).disabled(store.cart.isEmpty)
            Button("Clear cart", action: store.clearCart)
                .buttonStyle(QuietButtonStyle(tint: Theme.bad)).disabled(store.cart.isEmpty)
        }
    }

    private var count: Int { store.cart.reduce(0) { $0 + $1.quantity } }
    private var rule: some View { Rectangle().fill(Theme.paperLine).frame(height: 1).padding(.vertical, 4) }

    private func money(_ k: String, _ v: Double) -> some View {
        HStack {
            Text(k).font(Theme.mono(12)).foregroundStyle(Theme.paperMuted)
            Spacer()
            Text(String(format: "%.2f", v)).font(Theme.mono(13))
        }
    }
}

struct ReceiptLine: View {
    @EnvironmentObject var store: Store
    let line: CartLine

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 1) {
                Text(line.product.name).font(Theme.mono(13))
                HStack {
                    Text("  \(line.quantity) x " + String(format: "%.2f", line.product.price))
                        .font(Theme.mono(11)).foregroundStyle(Theme.paperMuted)
                    Spacer()
                    Text(String(format: "%.2f", line.subtotal)).font(Theme.mono(13))
                }
            }
            step("−") { store.setQuantity(line.id, max(0, line.quantity - 1)) }
            step("+") { store.setQuantity(line.id, min(line.quantity + 1, max(1, line.product.stock))) }
        }
        .padding(.vertical, 4)
    }

    private func step(_ glyph: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) { Text(glyph).font(Theme.mono(18, .semibold)).frame(width: 40, height: 40) }
            .buttonStyle(.plain).foregroundStyle(Theme.paperInk)
            .background(Theme.paper2, in: RoundedRectangle(cornerRadius: 4))
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.paperLine))
    }
}
