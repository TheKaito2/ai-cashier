import SwiftUI
import UIKit

/// docs/DESIGN.md, both columns.  The phone follows the system appearance:
/// paper by day, the instrument panel by night.  The receipt is paper in both.
enum Theme {
    static let bg = dyn(0xF3F1EC, 0x131110)
    static let surface = dyn(0xFBFAF7, 0x1C1917)
    static let surface2 = dyn(0xEAE7E0, 0x262220)
    static let line = dyn(0xD6D2C9, 0x3A342F)
    static let ink = dyn(0x1A1714, 0xF2EDE4)
    static let muted = dyn(0x6B655C, 0xA39B8F)
    static let accent = Color(hex: 0xFF7A18)
    static let accentInk = dyn(0xB4500A, 0xFFA45C)
    static let onAccent = Color(hex: 0x1A1714)
    static let ok = dyn(0x1E8E4E, 0x3DD68C)
    static let warn = dyn(0xC27C0E, 0xF2B33D)
    static let bad = dyn(0xC93A3E, 0xF0575B)
    static let info = dyn(0x2F6FD6, 0x6FA8FF)
    static let paper = Color(hex: 0xFBFAF7)
    static let paper2 = Color(hex: 0xEAE7E0)
    static let paperInk = Color(hex: 0x1A1714)
    static let paperMuted = Color(hex: 0x6B655C)
    static let paperLine = Color(hex: 0xD6D2C9)
    static let viewfinder = Color(hex: 0x0A0908)

    /// State, not decoration: the same three colours the till paints on its frame.
    static func status(_ s: Status) -> Color {
        switch s { case .accepted: return ok; case .ambiguous: return info; case .unknown: return accent }
    }

    /// IBM abbreviates the PostScript names: Regular has no suffix, Medium is
    /// `-Medm`, SemiBold `-SmBld` (read from the name tables in assets/fonts).
    enum Weight: String { case regular = "", medium = "-Medm", semibold = "-SmBld", bold = "-Bold" }

    static func sans(_ size: CGFloat, _ weight: Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("IBMPlexSansThai\(weight.rawValue)", size: size, relativeTo: style)
    }

    /// Plex Mono ships Regular / Medium / SemiBold here; bold falls to SemiBold.
    static func mono(_ size: CGFloat, _ weight: Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("IBMPlexMono\(weight == .bold ? Weight.semibold.rawValue : weight.rawValue)", size: size, relativeTo: style)
    }

    static func uiFont(_ name: String, _ size: CGFloat) -> UIFont {
        UIFont(name: name, size: size) ?? .systemFont(ofSize: size)
    }

    /// Navigation and tab bars are UIKit underneath; give them the same face.
    static func installAppearance() {
        let nav = UINavigationBarAppearance()
        nav.configureWithDefaultBackground()
        nav.largeTitleTextAttributes = [.font: uiFont("IBMPlexSansThai-SmBld", 32)]
        nav.titleTextAttributes = [.font: uiFont("IBMPlexSansThai-SmBld", 17)]
        UINavigationBar.appearance().standardAppearance = nav
        UINavigationBar.appearance().scrollEdgeAppearance = nav
        UITabBarItem.appearance().setTitleTextAttributes([.font: uiFont("IBMPlexSansThai-Medm", 10)], for: .normal)
    }

    private static func dyn(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) })
    }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
    }
}

extension Color {
    init(hex: UInt32) { self.init(UIColor(hex: hex)) }
}

/// The bottom of a receipt, the way the printer's tear bar leaves it.
struct TornEdge: Shape {
    var tooth: CGFloat = 7
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: r.minY))
        var x = r.minX, down = true
        while x < r.maxX {
            x = min(x + tooth, r.maxX)
            p.addLine(to: CGPoint(x: x, y: down ? r.maxY : r.minY))
            down.toggle()
        }
        p.addLine(to: CGPoint(x: r.maxX, y: r.minY))
        p.closeSubpath()
        return p
    }
}

/// Paper on the panel with a torn bottom edge: the cart, the printed receipt.
struct ReceiptCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(spacing: 0) {
            content
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .foregroundStyle(Theme.paperInk)
                .background(Theme.paper, in: UnevenRoundedRectangle(topLeadingRadius: 4, topTrailingRadius: 4))
            TornEdge().fill(Theme.paper).frame(height: 9)
        }
        .compositingGroup()
        .shadow(color: .black.opacity(0.18), radius: 14, y: 8)
    }
}

struct Eyebrow: View {
    let text: String
    var body: some View {
        Text(text.uppercased()).font(Theme.mono(11, .medium)).kerning(1.4).foregroundStyle(Theme.muted)
    }
}

/// The two big buttons: accent for the action that starts a sale, ok for the one that ends it.
struct BigButtonStyle: ButtonStyle {
    var fill: Color
    var foreground: Color = Theme.onAccent
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.mono(15, .semibold)).kerning(1.5)
            .frame(maxWidth: .infinity, minHeight: 56)
            .foregroundStyle(foreground)
            .background(fill.opacity(configuration.isPressed ? 0.8 : 1), in: RoundedRectangle(cornerRadius: 6))
    }
}

struct QuietButtonStyle: ButtonStyle {
    var tint: Color = Theme.ink
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.sans(15, .medium))
            .padding(.horizontal, 14).frame(minHeight: 44)
            .foregroundStyle(tint)
            .background(Theme.surface2.opacity(configuration.isPressed ? 0.6 : 1), in: RoundedRectangle(cornerRadius: 6))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line))
    }
}

extension View {
    /// Lists and forms on the paper ground instead of the system grey.
    func paperGround() -> some View {
        self.scrollContentBackground(.hidden).background(Theme.bg)
    }
}

/// A surface on the paper ground with an eyebrow title, as on the dashboard.
struct Panel<Content: View>: View {
    let title: String
    var note: String = ""
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Eyebrow(text: title)
                Spacer()
                Text(note).font(Theme.mono(11)).foregroundStyle(Theme.muted)
            }
            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line))
    }
}
