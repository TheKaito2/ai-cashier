import Foundation

/// A payment QR a Thai banking app will actually open: the EMVCo
/// merchant-presented payload with the PromptPay AID, byte for byte what
/// `server/services/promptpay.py` produces.
enum PromptPay {
    static let aid = "A000000677010111"

    enum Error: LocalizedError {
        case notAPromptPayId(String), amountNotPositive, fieldTooLong(String)
        var errorDescription: String? {
            switch self {
            case .notAPromptPayId(let t): return "\(t) is not a Thai mobile number, national ID or e-wallet id"
            case .amountNotPositive: return "amount must be positive"
            case .fieldTooLong(let tag): return "field \(tag) is too long"
            }
        }
    }

    /// CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final xor.
    static func crc16(_ s: String) -> UInt16 {
        var crc: UInt16 = 0xFFFF
        for byte in s.utf8 {
            crc ^= UInt16(byte) << 8
            for _ in 0..<8 {
                crc = (crc & 0x8000) != 0 ? (crc << 1) ^ 0x1021 : crc << 1
            }
        }
        return crc
    }

    static func field(_ tag: String, _ value: String) throws -> String {
        guard value.count <= 99 else { throw Error.fieldTooLong(tag) }
        return tag + String(format: "%02d", value.count) + value
    }

    /// (sub-tag, formatted value) for the merchant account field.
    static func normaliseTarget(_ target: String) throws -> (String, String) {
        var digits = target.filter(\.isNumber)
        if digits.count == 15 { return ("03", digits) }                       // e-wallet
        if digits.count == 13 && !digits.hasPrefix("0066") { return ("02", digits) }   // national / tax id
        if digits.hasPrefix("0066") { return ("01", digits) }
        if digits.hasPrefix("66") { digits = "00" + digits }
        else if digits.hasPrefix("0") { digits = "0066" + digits.dropFirst() }
        else { digits = "0066" + digits }
        guard digits.count == 13 else { throw Error.notAPromptPayId(target) }
        return ("01", digits)
    }

    static func buildPayload(target: String, amount: Double? = nil) throws -> String {
        let (sub, value) = try normaliseTarget(target)
        let merchant = try field("00", aid) + field(sub, value)
        var payload = try field("00", "01")
            + field("01", amount == nil ? "11" : "12")
            + field("29", merchant)
            + field("53", "764")
        if let amount {
            guard amount > 0 else { throw Error.amountNotPositive }
            payload += try field("54", String(format: "%.2f", amount))
        }
        payload += try field("58", "TH")
        payload += "6304"
        return payload + String(format: "%04X", crc16(payload))
    }
}
