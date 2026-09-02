import SwiftUI

@main
struct AICashierApp: App {
    @StateObject private var store = Store()

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(store)
        }
    }
}

struct RootView: View {
    var body: some View {
        TabView {
            TillView().tabItem { Label("Till", systemImage: "camera.viewfinder") }
            InventoryView().tabItem { Label("Inventory", systemImage: "shippingbox") }
            AnalyticsView().tabItem { Label("Takings", systemImage: "chart.bar") }
            SettingsView().tabItem { Label("Shop", systemImage: "gearshape") }
        }
        .tint(Theme.accent)
    }
}

enum Theme {
    static let accent = Color(red: 1.0, green: 0.478, blue: 0.094)      // #FF7A18, the till's orange
    static let ok = Color(red: 0.18, green: 0.8, blue: 0.443)
    static let warn = Color(red: 0.9, green: 0.62, blue: 0.1)
    static let info = Color(red: 0.298, green: 0.604, blue: 1.0)
}

func baht(_ v: Double, _ symbol: String = "฿") -> String { symbol + String(format: "%.2f", v) }
