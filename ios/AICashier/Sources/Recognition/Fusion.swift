import Foundation

enum Status: String {
    case accepted, unknown, ambiguous
}

struct FusedCandidate: Equatable {
    let skuId: String
    let total: Float
    let appearance: Float
}

struct Decision: Equatable {
    let status: Status
    let skuId: String?
    let candidates: [FusedCandidate]
    let margin: Float

    var top: FusedCandidate? { candidates.first }
}

/// `recognition/fusion.py` without the scale and the ruler: a phone has no
/// load cell and no fixed rig, so the mass and size terms are absent, and an
/// absent modality contributes exactly zero.  The thresholds are the Python
/// defaults and, like them, placeholders until calibrated on real photographs.
struct FusionConfig {
    var appearanceTemperature: Float = 0.07
    var rejectBelowCosine: Float = 0.38
    var ambiguousMargin: Float = 0.35
}

func fuse(_ matches: [Match], cfg: FusionConfig) -> Decision {
    guard !matches.isEmpty else { return Decision(status: .unknown, skuId: nil, candidates: [], margin: 0) }
    var candidates = matches.map { m in
        FusedCandidate(skuId: m.skuId, total: m.score / cfg.appearanceTemperature,
                       appearance: m.score / cfg.appearanceTemperature)
    }
    candidates.sort { $0.total > $1.total }
    let margin = candidates.count > 1 ? candidates[0].total - candidates[1].total : 0
    let best = matches.map(\.score).max() ?? 0
    if best < cfg.rejectBelowCosine {
        return Decision(status: .unknown, skuId: nil, candidates: candidates, margin: margin)
    }
    if candidates.count > 1 && margin < cfg.ambiguousMargin {
        return Decision(status: .ambiguous, skuId: candidates[0].skuId, candidates: candidates, margin: margin)
    }
    return Decision(status: .accepted, skuId: candidates[0].skuId, candidates: candidates, margin: margin)
}
