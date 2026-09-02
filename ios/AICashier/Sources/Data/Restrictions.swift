import Foundation

/// What Thai law lets a till sell, and when (`server/services/restrictions.py`).
/// Hours are a constant, not a setting: the law sets them, not the shop.
enum Restriction: String, CaseIterable, Codable {
    case none, alcohol, tobacco
}

struct Gate {
    let ok: Bool
    var reason = ""
    var needsStaff = false
}

enum Restrictions {
    static let minAge = 20

    static func alcoholHoursOpen(_ now: Date = Date(), calendar: Calendar = .current) -> Bool {
        let h = calendar.component(.hour, from: now)
        return h >= 11                                 // 11:00 up to midnight
    }

    static func saleGate(_ restricted: Restriction, staffConfirmed: Bool = false, now: Date = Date()) -> Gate {
        switch restricted {
        case .none:
            return Gate(ok: true)
        case .alcohol:
            if !alcoholHoursOpen(now) {
                return Gate(ok: false, reason: "Alcohol may only be sold 11:00-24:00 (Alcoholic Beverage Control Act No. 2 B.E. 2568)")
            }
            if !staffConfirmed {
                return Gate(ok: false, reason: "Alcohol: staff must confirm the buyer is \(minAge)+ and sober", needsStaff: true)
            }
            return Gate(ok: true)
        case .tobacco:
            if !staffConfirmed {
                return Gate(ok: false, reason: "Tobacco: staff-only sale, buyer must be \(minAge)+ (Tobacco Products Control Act B.E. 2560)", needsStaff: true)
            }
            return Gate(ok: true)
        }
    }

    /// Tobacco may not be displayed, so customer-facing lists never carry it.
    static func customerVisible(_ restricted: Restriction) -> Bool { restricted != .tobacco }
}
