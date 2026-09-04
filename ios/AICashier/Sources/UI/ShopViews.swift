import Charts
import SwiftUI

struct InventoryView: View {
    @EnvironmentObject var store: Store
    @State private var restockFor: Product?
    @State private var restockQty = 10

    var body: some View {
        NavigationStack {
            List {
                if store.products.isEmpty {
                    Text("No products yet. Teach one on the Till tab.").font(Theme.sans(15)).foregroundStyle(Theme.muted)
                        .listRowBackground(Theme.surface)
                }
                ForEach(store.products) { p in
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(p.name).font(Theme.sans(16, .semibold)).foregroundStyle(Theme.ink)
                            HStack(spacing: 8) {
                                Text(p.category).font(Theme.mono(11)).foregroundStyle(Theme.muted)
                                Text("\(store.pipeline.gallery.count(p.id)) views").font(Theme.mono(11)).foregroundStyle(Theme.muted)
                                if p.restricted != .none { Chip(text: p.restricted.rawValue, colour: Theme.warn) }
                            }
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 3) {
                            Text(baht(p.price, store.settings.currency)).font(Theme.mono(16, .semibold)).foregroundStyle(Theme.ink)
                            HStack(spacing: 6) {
                                Text("\(p.stock) / min \(p.minStock)").font(Theme.mono(11)).foregroundStyle(Theme.muted)
                                Chip(text: p.stock == 0 ? "out" : p.stock <= p.minStock ? "low" : "in stock",
                                     colour: p.stock == 0 ? Theme.bad : p.stock <= p.minStock ? Theme.warn : Theme.ok)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                    .listRowBackground(Theme.surface)
                    .swipeActions {
                        Button("Restock") { restockFor = p; restockQty = 10 }.tint(Theme.info)
                        Button("Remove", role: .destructive) { store.removeProduct(p.id) }
                    }
                }
            }
            .paperGround()
            .navigationTitle("Inventory")
            .alert("Restock \(restockFor?.name ?? "")", isPresented: Binding(get: { restockFor != nil }, set: { if !$0 { restockFor = nil } })) {
                TextField("Quantity", value: $restockQty, format: .number).keyboardType(.numberPad)
                Button("Add") { if let p = restockFor { try? store.db.updateStock(p.id, delta: restockQty); store.reloadProducts() } }
                Button("Cancel", role: .cancel) {}
            }
        }
    }
}

struct Chip: View {
    let text: String
    let colour: Color
    var body: some View {
        Text(text.uppercased()).font(Theme.mono(9, .medium)).kerning(0.8)
            .padding(.horizontal, 5).padding(.vertical, 2)
            .foregroundStyle(colour)
            .overlay(RoundedRectangle(cornerRadius: 3).stroke(colour))
    }
}

struct AnalyticsView: View {
    @EnvironmentObject var store: Store
    @State private var analytics = Analytics()
    @State private var sales: [Sale] = []
    @State private var events: [Event] = []

    struct Bucket: Identifiable { let id: Int; let label: String; let value: Double }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    HStack(alignment: .top, spacing: 16) {
                        figure(baht(analytics.todayRevenue, store.settings.currency), "taken today")
                        figure("\(analytics.todaySales)", "sales today")
                        figure(baht(analytics.totalRevenue, store.settings.currency), "all time")
                    }
                    .padding(.vertical, 12)
                    .overlay(alignment: .top) { Rectangle().fill(Theme.line).frame(height: 1) }
                    .overlay(alignment: .bottom) { Rectangle().fill(Theme.line).frame(height: 1) }

                    Panel(title: "Takings by day", note: "last 14 days") {
                        Chart(byDay) { d in
                            BarMark(x: .value("Day", d.label), y: .value("Takings", d.value))
                                .foregroundStyle(Theme.accent).cornerRadius(2)
                        }
                        .chartXAxis {
                            // a categorical axis is not thinned automatically: label every third day
                            AxisMarks(values: byDay.enumerated().filter { $0.offset % 3 == 0 }.map { $0.element.label }) { _ in
                                AxisValueLabel().font(Theme.mono(9)).foregroundStyle(Theme.muted)
                            }
                        }
                        .chartYAxis {
                            AxisMarks { _ in
                                AxisGridLine().foregroundStyle(Theme.line)
                                AxisValueLabel().font(Theme.mono(9)).foregroundStyle(Theme.muted)
                            }
                        }
                        .frame(height: 150)
                    }

                    Panel(title: "Best sellers", note: "by revenue") {
                        if analytics.topProducts.isEmpty {
                            Text("NOTHING SOLD YET").font(Theme.mono(11)).foregroundStyle(Theme.muted).frame(maxWidth: .infinity).padding(.vertical, 12)
                        } else {
                            Chart(Array(analytics.topProducts.prefix(6).enumerated()), id: \.offset) { pair in
                                BarMark(x: .value("Revenue", pair.element.revenue), y: .value("Product", pair.element.name))
                                    .foregroundStyle(Theme.accent).cornerRadius(2)
                                    .annotation(position: .trailing) {
                                        Text("\(baht(pair.element.revenue, store.settings.currency)) · \(pair.element.quantity)").font(Theme.mono(9)).foregroundStyle(Theme.ink)
                                    }
                            }
                            .chartXAxis(.hidden)
                            .chartYAxis { AxisMarks { _ in AxisValueLabel().font(Theme.mono(10)).foregroundStyle(Theme.ink) } }
                            .frame(height: CGFloat(min(6, analytics.topProducts.count)) * 36)
                        }
                    }

                    Panel(title: "Recent sales", note: "last 20") {
                        if sales.isEmpty { Text("NO SALES YET").font(Theme.mono(11)).foregroundStyle(Theme.muted).frame(maxWidth: .infinity).padding(.vertical, 12) }
                        ForEach(sales) { s in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(s.id).font(Theme.mono(12)).foregroundStyle(Theme.ink)
                                    Text(s.timestamp.formatted(date: .abbreviated, time: .shortened)).font(Theme.sans(12)).foregroundStyle(Theme.muted)
                                }
                                Spacer()
                                Text(baht(s.total, store.settings.currency)).font(Theme.mono(15, .semibold)).foregroundStyle(Theme.ink)
                            }
                            .padding(.vertical, 6)
                            Rectangle().fill(Theme.line).frame(height: 1)
                        }
                    }

                    Panel(title: "Deployment log", note: "last 50") {
                        if events.isEmpty { Text("NOTHING LOGGED YET").font(Theme.mono(11)).foregroundStyle(Theme.muted).frame(maxWidth: .infinity).padding(.vertical, 12) }
                        ForEach(events) { e in
                            VStack(alignment: .leading, spacing: 2) {
                                Chip(text: e.kind.replacingOccurrences(of: "_", with: " "), colour: e.kind == "abstention" ? Theme.warn : Theme.muted)
                                Text(e.payload.map { "\($0.key)=\($0.value)" }.sorted().joined(separator: "  ")).font(Theme.mono(11)).foregroundStyle(Theme.muted)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
                .padding()
            }
            .background(Theme.bg)
            .navigationTitle("Takings")
            .refreshable { load() }
            .onAppear(perform: load)
        }
    }

    private func figure(_ n: String, _ k: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(n).font(Theme.mono(22, .semibold)).foregroundStyle(Theme.ink).minimumScaleFactor(0.7).lineLimit(1)
            Eyebrow(text: k)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// The last 14 days, oldest first, from the sales that came back.
    private var byDay: [Bucket] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        return (0..<14).reversed().map { back in
            let day = cal.date(byAdding: .day, value: -back, to: today)!
            let total = sales.filter { cal.isDate($0.timestamp, inSameDayAs: day) }.reduce(0) { $0 + $1.total }
            return Bucket(id: back, label: day.formatted(.dateTime.day().month(.abbreviated)), value: total)
        }
    }

    private func load() {
        analytics = (try? store.db.analytics()) ?? Analytics()
        sales = (try? store.db.sales(limit: 200)) ?? []
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
            .paperGround()
            .navigationTitle("Shop")
        }
    }
}
