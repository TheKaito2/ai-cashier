import Accelerate
import Foundation

struct Match: Equatable {
    let skuId: String
    let score: Float
    let nViews: Int
}

enum Vec {
    static func l2(_ v: [Float]) -> [Float] {
        var n: Float = 0
        vDSP_dotpr(v, 1, v, 1, &n, vDSP_Length(v.count))
        let norm = max(n.squareRoot(), 1e-12)
        var out = [Float](repeating: 0, count: v.count)
        var s = 1 / norm
        vDSP_vsmul(v, 1, &s, &out, 1, vDSP_Length(v.count))
        return out
    }

    static func dot(_ a: [Float], _ b: [Float]) -> Float {
        var r: Float = 0
        vDSP_dotpr(a, 1, b, 1, &r, vDSP_Length(a.count))
        return r
    }

    static func minus(_ a: [Float], _ b: [Float]) -> [Float] {
        var out = [Float](repeating: 0, count: a.count)
        vDSP_vsub(b, 1, a, 1, &out, 1, vDSP_Length(a.count))
        return out
    }
}

/// k reference vectors per SKU, matched by cosine similarity in a centred
/// space.  A port of `recognition/gallery.py`, frozen centre included: once
/// `minSkusToFreeze` products are enrolled the centre is pinned so that
/// enrolling more never moves an existing score.
final class SkuGallery {
    static let minSkusToFreeze = 4

    let dim: Int
    private(set) var vectors: [[Float]] = []        // raw, L2-normalised
    private(set) var skuIds: [String] = []
    private(set) var centre: [Float]?
    private var centredCache: [[Float]]?

    init(dim: Int) { self.dim = dim }

    var count: Int { skuIds.count }
    var skus: [String] { Array(Set(skuIds)).sorted() }
    var frozen: Bool { centre != nil }

    func count(_ sku: String) -> Int { skuIds.filter { $0 == sku }.count }

    @discardableResult
    func enrol(_ sku: String, _ views: [[Float]]) -> Int {
        for v in views {
            precondition(v.count == dim, "expected \(dim)-d vectors, got \(v.count)")
            vectors.append(Vec.l2(v))
            skuIds.append(sku)
        }
        centredCache = nil
        return count(sku)
    }

    @discardableResult
    func remove(_ sku: String) -> Int {
        let keep = skuIds.indices.filter { skuIds[$0] != sku }
        let removed = skuIds.count - keep.count
        vectors = keep.map { vectors[$0] }
        skuIds = keep.map { skuIds[$0] }
        centredCache = nil
        return removed
    }

    var mean: [Float] {
        guard !vectors.isEmpty else { return [Float](repeating: 0, count: dim) }
        var acc = [Float](repeating: 0, count: dim)
        for v in vectors { vDSP_vadd(acc, 1, v, 1, &acc, 1, vDSP_Length(dim)) }
        var s = 1 / Float(vectors.count)
        vDSP_vsmul(acc, 1, &s, &acc, 1, vDSP_Length(dim))
        return acc
    }

    func freezeCentre() { centre = mean; centredCache = nil }
    func thawCentre() { centre = nil; centredCache = nil }
    func setCentre(_ c: [Float]) { centre = c; centredCache = nil }

    var reference: [Float] { centre ?? mean }

    private func centred() -> [[Float]] {
        if let c = centredCache { return c }
        let ref = reference
        let c = vectors.map { Vec.l2(Vec.minus($0, ref)) }
        centredCache = c
        return c
    }

    func project(_ v: [Float]) -> [Float] { Vec.l2(Vec.minus(Vec.l2(v), reference)) }

    /// Rank SKUs by their best-matching reference view.
    func match(_ v: [Float], topK: Int = 3) -> [Match] {
        guard count > 0 else { return [] }
        let q = project(v)
        var best: [String: Float] = [:]
        for (row, sku) in zip(centred(), skuIds) {
            let s = Vec.dot(row, q)
            if s > (best[sku] ?? -2) { best[sku] = s }
        }
        return best.sorted { $0.value > $1.value }.prefix(topK)
            .map { Match(skuId: $0.key, score: $0.value, nViews: count($0.key)) }
    }

    /// Note: `project` L2-normalises the query first.  Python stores raw
    /// vectors L2-normalised and projects the raw query without normalising;
    /// the difference is a positive scale on the query, which the final
    /// normalisation removes, so scores are identical.
}
