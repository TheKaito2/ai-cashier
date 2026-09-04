import SwiftUI

@main
struct AICashierApp: App {
    @StateObject private var store = Store()

    init() { Theme.installAppearance() }

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(store)
        }
    }
}

struct RootView: View {
    /// `--tab takings` on launch opens that tab: how the screenshot harness gets there.
    @State private var tab = CommandLine.arguments.firstIndex(of: "--tab").map { CommandLine.arguments[$0 + 1] } ?? "till"

    var body: some View {
        TabView(selection: $tab) {
            TillView().tabItem { Label("Till", systemImage: "camera.viewfinder") }.tag("till")
            InventoryView().tabItem { Label("Inventory", systemImage: "shippingbox") }.tag("inventory")
            AnalyticsView().tabItem { Label("Takings", systemImage: "chart.bar") }.tag("takings")
            SettingsView().tabItem { Label("Shop", systemImage: "gearshape") }.tag("shop")
        }
        .tint(Theme.accentInk)
        .font(Theme.sans(17))
    }
}

func baht(_ v: Double, _ symbol: String = "฿") -> String { symbol + String(format: "%.2f", v) }
