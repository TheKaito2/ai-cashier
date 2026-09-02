import CoreImage
import CoreImage.CIFilterBuiltins
import SwiftUI

struct PaymentView: View {
    @EnvironmentObject var store: Store
    @State private var receipt: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                if let p = store.pendingPayment {
                    Text("SCAN TO PAY").font(.caption).fontWeight(.semibold).kerning(1).foregroundStyle(.secondary)
                    Text(baht(p.total, store.settings.currency)).font(.system(size: 44, weight: .bold))
                    if let img = QR.image(p.qrPayload) {
                        Image(decorative: img, scale: 1).resizable().interpolation(.none).scaledToFit().frame(maxWidth: 280)
                    }
                    if !p.payable {
                        Text("PromptPay is not configured. This code is a placeholder, not a payment. Set the PromptPay id in the Shop tab before taking money.")
                            .font(.footnote).foregroundStyle(Theme.warn).multilineTextAlignment(.center)
                    }
                    Text("Payment \(p.paymentId.prefix(8)) · \(p.items.count) lines").font(.caption).foregroundStyle(.secondary)
                    Button(action: store.confirmPayment) { Text("Payment received").frame(maxWidth: .infinity, minHeight: 56).fontWeight(.bold) }
                        .buttonStyle(.borderedProminent).tint(Theme.ok)
                    Button("Cancel", role: .cancel, action: store.cancelPayment)
                } else if let sale = store.lastSale {
                    Text("Paid").font(.title).fontWeight(.bold)
                    ScrollView { Text(Receipt.render(sale, settings: store.settings)).font(.system(.footnote, design: .monospaced)) }
                        .frame(maxHeight: 320)
                    ShareLink(item: Receipt.render(sale, settings: store.settings)) { Label("Share receipt", systemImage: "square.and.arrow.up") }
                }
            }
            .padding()
            .interactiveDismissDisabled(store.pendingPayment != nil)
        }
    }
}

enum QR {
    static func image(_ payload: String, scale: CGFloat = 8) -> CGImage? {
        let f = CIFilter.qrCodeGenerator()
        f.message = Data(payload.utf8)
        f.correctionLevel = "M"
        guard let out = f.outputImage?.transformed(by: CGAffineTransform(scaleX: scale, y: scale)) else { return nil }
        return CIContext().createCGImage(out, from: out.extent)
    }
}
