import SwiftUI

struct InventoryView: View {
    @EnvironmentObject var store: Store
    @State private var restockFor: Product?
    @State private var restockQty = 10

    var body: some View {
        NavigationStack {
            List {
                if store.products.isEmpty {
                    Text("No products yet. Teach one on the Till tab.").foregroundStyle(.secondary)
                }
                ForEach(store.products) { p in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name).fontWeight(.semibold)
                            HStack(spacing: 6) {
                                Text(p.category).font(.caption).foregroundStyle(.secondary)
                                if p.restricted != .none {
                                    Text(p.restricted.rawValue).font(.caption2).padding(.horizontal, 6).padding(.vertical, 2)
                                        .background(Theme.warn.opacity(0.2), in: Capsule())
                                }
                                Text("\(store.pipeline.gallery.count(p.id)) views").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                        VStack(alignment: .trailing) {
                            Text(baht(p.price, store.settings.currency))
                            Text("\(p.stock) in stock").font(.caption).foregroundStyle(p.stock <= p.minStock ? Theme.warn : .secondary)
                        }
                    }
                    .swipeActions {
                        Button("Restock") { restockFor = p; restockQty = 10 }.tint(Theme.info)
                        Button("Remove", role: .destructive) { store.removeProduct(p.id) }
                    }
                }
            }
            .navigationTitle("Inventory")
            .alert("Restock \(restockFor?.name ?? "")", isPresented: Binding(get: { restockFor != nil }, set: { if !$0 { restockFor = nil } })) {
                TextField("Quantity", value: $restockQty, format: .number).keyboardType(.numberPad)
                Button("Add") { if let p = restockFor { try? store.db.updateStock(p.id, delta: restockQty); store.reloadProducts() } }
                Button("Cancel", role: .cancel) {}
            }
        }
    }
}

struct AnalyticsView: View {
    @EnvironmentObject var store: Store
    @State private var analytics = Analytics()
    @State private var sales: [Sale] = []
    @State private var events: [Event] = []

    var body: some View {
        NavigationStack {
            List {
                Section("Today") {
                    stat("Sales", "\(analytics.todaySales)")
                    stat("Taken", baht(analytics.todayRevenue, store.settings.currency))
                    stat("Low stock", "\(analytics.lowStockCount)")
                }
                Section("All time") {
                    stat("Sales", "\(analytics.totalSales)")
                    stat("Taken", baht(analytics.totalRevenue, store.settings.currency))
                }
                Section("Best sellers") {
                    ForEach(Array(analytics.topProducts.enumerated()), id: \.offset) { _, t in
                        HStack { Text(t.name); Spacer(); Text("\(t.quantity) · \(baht(t.revenue, store.settings.currency))").foregroundStyle(.secondary) }
                    }
                }
                Section("Recent sales") {
                    ForEach(sales) { s in
                        HStack { Text(s.id).font(.caption.monospaced()); Spacer(); Text(baht(s.total, store.settings.currency)) }
                    }
                }
                Section("Deployment log") {
                    ForEach(events) { e in
                        VStack(alignment: .leading) {
                            Text(e.kind).font(.caption).fontWeight(.semibold)
                            Text(e.payload.map { "\($0.key)=\($0.value)" }.sorted().joined(separator: "  ")).font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("Takings")
            .refreshable { load() }
            .onAppear(perform: load)
        }
    }

    private func stat(_ k: String, _ v: String) -> some View { HStack { Text(k); Spacer(); Text(v).fontWeight(.semibold) } }

    private func load() {
        analytics = (try? store.db.analytics()) ?? Analytics()
        sales = (try? store.db.sales(limit: 20)) ?? []
        events = (try? store.db.events(limit: 50)) ?? []
    }
}

struct SettingsView: View {
    @EnvironmentObject var store: Store

    var body: some View {
        NavigationStack {
            Form {
                Section("Shop") {
                    TextField("Store name", text: $store.settings.storeName)
                    TextField("Address (on the receipt)", text: $store.settings.storeAddress)
                    HStack { Text("VAT rate"); Spacer(); TextField("0.07", value: $store.settings.taxRate, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing) }
                    Toggle("VAT registered (abbreviated tax invoice)", isOn: $store.settings.vatRegistered)
                    if store.settings.vatRegistered { TextField("Taxpayer id (TIN)", text: $store.settings.tin) }
                }
                Section("PromptPay") {
                    TextField("Mobile, national id or e-wallet id", text: $store.settings.promptpayId).keyboardType(.numberPad)
                    Text("Leave empty to show a placeholder code that cannot be paid.").font(.footnote).foregroundStyle(.secondary)
                }
                Section("Camera") {
                    Toggle("Use the demo image instead of the camera", isOn: $store.useDemoCamera)
                    Toggle("Lock exposure and white balance", isOn: $store.exposureLocked)
                    Text("Lock it once the light is set, so a packet looks the same at checkout as it did when it was taught.").font(.footnote).foregroundStyle(.secondary)
                }
                Section("Recognition") {
                    HStack {
                        Text("Reject below cosine")
                        Spacer()
                        TextField("0.38", value: Binding(get: { store.settings.rejectBelowCosine ?? Double(store.pipeline.cfg.rejectBelowCosine) },
                                                        set: { store.settings.rejectBelowCosine = $0 }), format: .number)
                            .keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                    }
                    Text("\(store.pipeline.gallery.skus.count) products taught · \(store.pipeline.gallery.count) reference views · centre \(store.pipeline.gallery.frozen ? "frozen" : "floating")")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section {
                    Button("Save", action: store.saveSettings)
                }
                Section("About") {
                    Text("AI Cashier \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "") · Group 3, Assumption College Sriracha. No picture is ever kept; only a product's numbers persist.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Shop")
        }
    }
}
