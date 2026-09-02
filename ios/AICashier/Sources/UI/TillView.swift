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
                    detectedPanel
                    HStack(spacing: 10) {
                        Button(action: store.scan) {
                            Text(store.scanning ? "SCANNING..." : "SCAN PRODUCTS")
                                .frame(maxWidth: .infinity, minHeight: 56).fontWeight(.bold)
                        }
                        .buttonStyle(.borderedProminent).tint(Theme.accent).disabled(store.scanning)
                        Button {
                            if store.restrictedInDetected.isEmpty { store.addToCart(staffConfirmed: false) } else { showStaffConfirm = true }
                        } label: {
                            Text(store.sellable.count > 1 ? "Add \(store.sellable.count)" : "Add to cart")
                                .frame(minWidth: 110, minHeight: 56)
                        }
                        .buttonStyle(.bordered).disabled(store.sellable.isEmpty)
                    }
                    CartPanel()
                    Text(store.status).font(.footnote).foregroundStyle(.secondary)
                }
                .padding()
            }
            .navigationTitle("AI Cashier")
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button("Calibrate mat", action: store.calibrateMat)
                    Button("Add product") { showEnrol = true }
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

    private var detectedPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("JUST DETECTED").font(.caption).fontWeight(.semibold).foregroundStyle(.secondary).kerning(1)
            if store.detected.isEmpty {
                Text(store.matCalibrated ? "Place products under the camera, then press SCAN."
                                         : "Clear the mat and press Calibrate mat once.")
                    .foregroundStyle(.secondary).padding(.vertical, 6)
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

struct CameraPreview: View {
    @EnvironmentObject var store: Store
    var body: some View {
        ZStack(alignment: .bottomLeading) {
            if let img = store.preview {
                Image(decorative: img, scale: 1, orientation: .up).resizable().aspectRatio(contentMode: .fit)
            } else {
                Rectangle().fill(.black).aspectRatio(16 / 9, contentMode: .fit)
                    .overlay(Text("No camera").foregroundStyle(.white))
            }
            HStack(spacing: 6) {
                Circle().fill(store.matCalibrated ? Theme.ok : Theme.warn).frame(width: 8, height: 8)
                Text(store.matCalibrated ? "mat calibrated" : "mat not calibrated").font(.caption2)
                Text("· \(store.camera.name)").font(.caption2)
            }
            .padding(6).background(.ultraThinMaterial, in: Capsule()).padding(8)
        }
        .clipShape(RoundedRectangle(cornerRadius: 14))
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
            VStack(alignment: .leading, spacing: 2) {
                if item.status == .unknown {
                    Text("Unknown item").fontWeight(.semibold)
                    Text("not in the gallery - teach it or call staff").font(.caption).foregroundStyle(.secondary)
                } else if let p = product {
                    Text(p.name).fontWeight(.semibold)
                    Text(detail(p)).font(.caption).foregroundStyle(.secondary)
                } else {
                    Text(item.skuId ?? "Unknown").fontWeight(.semibold)
                    Text("recognised, but not priced").font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
            if let p = product, item.status != .unknown { Text(baht(p.price)).fontWeight(.bold).foregroundStyle(Theme.accent) }
            if item.status == .unknown { Button("Teach", action: onEnrol).buttonStyle(.bordered) }
            if item.status == .ambiguous { Button("Choose", action: onChoose).buttonStyle(.bordered) }
            Button(action: onDismiss) { Image(systemName: "xmark") }.buttonStyle(.bordered)
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(.secondarySystemBackground)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(colour, lineWidth: 1.5))
    }

    private var colour: Color {
        switch item.status { case .accepted: return Theme.ok; case .ambiguous: return Theme.info; case .unknown: return Theme.warn }
    }

    private func detail(_ p: Product) -> String {
        if p.restricted != .none { return "\(p.restricted.rawValue.uppercased()) - staff must check ID (20+)" }
        if item.status == .ambiguous, item.decision.candidates.count > 1 { return "not sure - could be \(item.decision.candidates[1].skuId)" }
        return "\(p.category) · \(Int((item.agreement * 100).rounded()))% of frames agreed"
    }
}

struct CartPanel: View {
    @EnvironmentObject var store: Store
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("CART").font(.caption).fontWeight(.semibold).foregroundStyle(.secondary).kerning(1)
                Spacer()
                Text("\(store.cart.reduce(0) { $0 + $1.quantity }) items").font(.caption).foregroundStyle(.secondary)
            }
            if store.cart.isEmpty { Text("Nothing scanned yet.").foregroundStyle(.secondary).padding(.vertical, 6) }
            ForEach(store.cart) { line in
                HStack {
                    VStack(alignment: .leading) {
                        Text(line.product.name)
                        Text("\(baht(line.product.price, store.settings.currency)) each").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Stepper("× \(line.quantity)", value: Binding(get: { line.quantity }, set: { store.setQuantity(line.id, $0) }), in: 0...max(1, line.product.stock))
                        .fixedSize()
                    Text(baht(line.subtotal, store.settings.currency)).fontWeight(.semibold).frame(minWidth: 70, alignment: .trailing)
                }
                Divider()
            }
            row("Subtotal", baht(store.subtotal, store.settings.currency))
            row("VAT \(Int((store.settings.taxRate * 100).rounded()))%", baht(store.tax, store.settings.currency))
            HStack { Text("TOTAL").fontWeight(.bold); Spacer(); Text(baht(store.total, store.settings.currency)).font(.title).fontWeight(.bold) }
            Button(action: store.checkout) { Text("PAY").frame(maxWidth: .infinity, minHeight: 56).fontWeight(.bold) }
                .buttonStyle(.borderedProminent).tint(Theme.ok).disabled(store.cart.isEmpty)
            Button("Clear cart", role: .destructive, action: store.clearCart).disabled(store.cart.isEmpty)
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemBackground)))
    }

    private func row(_ k: String, _ v: String) -> some View {
        HStack { Text(k).foregroundStyle(.secondary); Spacer(); Text(v) }
    }
}
