import Foundation

/// Count each item once.  Items sit still on the mat, so a centroid tracker is
/// enough (`recognition/tracker.py`).
final class Track {
    let trackId: Int
    var box: Box
    var votes: [String: Int] = [:]       // "__unknown__" for nothing matched
    var scores: [String: Float] = [:]
    var misses = 0
    var hits = 1
    var lastDecision: Decision?

    init(trackId: Int, box: Box) { self.trackId = trackId; self.box = box }

    func observe(_ skuId: String?, _ score: Float) {
        let key = skuId ?? "__unknown__"
        votes[key, default: 0] += 1
        scores[key] = max(scores[key] ?? -2, score)
    }

    /// (sku, best score, agreement) over every frame seen so far.
    var decision: (String?, Float, Float) {
        guard let (key, n) = votes.max(by: { $0.value < $1.value }) else { return (nil, 0, 0) }
        let total = votes.values.reduce(0, +)
        return (key == "__unknown__" ? nil : key, scores[key] ?? 0, Float(n) / Float(total))
    }
}

final class CentroidTracker {
    var maxDistancePx = 80.0
    var maxMisses = 5
    var minHits = 2
    private(set) var tracks: [Int: Track] = [:]
    private var nextId = 1

    func update(_ boxes: [Box]) -> [Track] {
        var unmatched = Set(tracks.keys)
        for box in boxes {
            let (cx, cy) = box.centre
            var bestId: Int?
            var bestD = maxDistancePx
            for tid in unmatched {
                let (tx, ty) = tracks[tid]!.box.centre
                let d = ((tx - cx) * (tx - cx) + (ty - cy) * (ty - cy)).squareRoot()
                if d < bestD { bestId = tid; bestD = d }
            }
            if let id = bestId {
                let t = tracks[id]!
                t.box = box; t.misses = 0; t.hits += 1
                unmatched.remove(id)
            } else {
                tracks[nextId] = Track(trackId: nextId, box: box)
                nextId += 1
            }
        }
        for tid in unmatched { tracks[tid]!.misses += 1 }
        for (tid, t) in tracks where t.misses > maxMisses { tracks[tid] = nil }
        return Array(tracks.values)
    }

    var confirmed: [Track] {
        tracks.values.filter { $0.hits >= minHits && $0.misses == 0 }.sorted { $0.trackId < $1.trackId }
    }

    func reset() { tracks.removeAll() }
}
