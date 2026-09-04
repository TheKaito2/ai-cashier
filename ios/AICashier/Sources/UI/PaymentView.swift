import CoreImage
import CoreImage.CIFilterBuiltins
import SwiftUI

struct PaymentView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    if let p = store.pendingPayment {
                        Eyebrow(text: "Scan to pay")
                        Text(baht(p.total, store.settings.currency)).font(Theme.mono(44, .semibold)).foregroundStyle(Theme.ink)
                        if let img = QR.image(p.qrPayload) {
                            Image(decorative: img, scale: 1).resizable().interpolation(.none).scaledToFit().frame(maxWidth: 260)
                                .padding(12).background(Color.white, in: RoundedRectangle(cornerRadius: 6))
                        }
                        if !p.payable {
                            Text("PromptPay is not configured. This code is a placeholder, not a payment. Set the PromptPay id in the Shop tab before taking money.")
                                .font(Theme.sans(13)).foregroundStyle(Theme.warn).multilineTextAlignment(.center)
                        }
                        Text("Payment \(p.paymentId.prefix(8)) · \(p.items.count) lines").font(Theme.mono(11)).foregroundStyle(Theme.muted)
                        Button(action: store.confirmPayment) { Text("PAYMENT RECEIVED") }.buttonStyle(BigButtonStyle(fill: Theme.ok))
                        Button("Cancel", role: .cancel, action: store.cancelPayment).buttonStyle(QuietButtonStyle())
                    } else if let sale = store.lastSale {
                        Eyebrow(text: "Paid")
                        ReceiptCard {
                            Text(Receipt.render(sale, settings: store.settings)).font(Theme.mono(13))
                        }
                        ShareLink(item: Receipt.render(sale, settings: store.settings)) {
                            Label("Share receipt", systemImage: "square.and.arrow.up").font(Theme.sans(15, .medium))
                        }
                        Button(action: { dismiss() }) { Text("DONE") }.buttonStyle(BigButtonStyle(fill: Theme.ok))
                    }
                }
                .padding()
            }
            .background(Theme.bg)
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
