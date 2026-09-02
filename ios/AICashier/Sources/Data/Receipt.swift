import Foundation

/// The receipt in the two forms Thai law knows (`server/services/receipt.py`):
/// an abbreviated tax invoice for a VAT-registered shop, a plain receipt for
/// everyone else.  32 columns, what a thermal printer takes as-is.
enum Receipt {
    static let width = 32

    private static func line(_ left: String, _ right: String = "") -> String {
        if right.isEmpty { return String(left.prefix(width)) }
        let l = String(left.prefix(width - right.count - 1))
        return l.padding(toLength: width - right.count, withPad: " ", startingAt: 0) + right
    }

    private static func centre(_ text: String) -> String {
        let t = String(text.prefix(width))
        let pad = max(0, (width - t.count) / 2)
        return String(repeating: " ", count: pad) + t
    }

    static func render(_ sale: Sale, settings: ShopSettings) -> String {
        let vat = settings.vatRegistered
        let f = DateFormatter()
        f.dateFormat = "dd/MM/yyyy HH:mm"
        var out = [centre(settings.storeName)]
        if !settings.storeAddress.isEmpty { out.append(centre(settings.storeAddress)) }
        if vat {
            out += [centre("ใบกำกับภาษีอย่างย่อ"), centre("TAX INVOICE (ABB)"),
                    centre("TIN \(settings.tin.isEmpty ? "-" : settings.tin)")]
        } else {
            out.append(centre("ใบเสร็จรับเงิน / RECEIPT"))
        }
        out += [line("No. \(sale.id)"), line(f.string(from: sale.timestamp)), String(repeating: "-", count: width)]
        for it in sale.items {
            out.append(line(it.productName))
            out.append(line("  \(it.quantity) x " + String(format: "%.2f", it.price), String(format: "%.2f", it.total)))
        }
        out.append(String(repeating: "-", count: width))
        if vat {
            out.append(line("Subtotal", String(format: "%.2f", sale.subtotal)))
            out.append(line("VAT \(Int((settings.taxRate * 100).rounded()))%", String(format: "%.2f", sale.tax)))
        }
        out.append(line("TOTAL", settings.currency + String(format: "%.2f", sale.total)))
        if vat { out.append(centre("VAT included / รวม VAT แล้ว")) }
        out.append(centre("Thank you / ขอบคุณค่ะ"))
        return out.joined(separator: "\n") + "\n"
    }
}
