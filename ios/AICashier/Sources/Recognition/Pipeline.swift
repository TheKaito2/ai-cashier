import Foundation

struct RecognisedItem: Identifiable {
    let trackId: Int
    let box: Box
    let decision: Decision
    let agreement: Float
    let hits: Int

    var id: Int { trackId }
    var skuId: String? { decision.skuId }
    var status: Status { decision.status }
}

/// Frame in, recognised items out: propose -> embed -> match -> fuse -> track.
/// A port of `recognition/pipeline.py`.  Nothing here ever writes a picture.
final class RecognitionPipeline {
    let proposer: BackgroundSubtractionProposer
    let embedder: CoreMLEmbedder
    var gallery: SkuGallery
    var cfg: FusionConfig
    let tracker = CentroidTracker()
    /// once a track has agreed with itself this many times, stop re-embedding it
    var settledHits = 4
    private var settled: [Int: Decision] = [:]

    init(proposer: BackgroundSubtractionProposer, embedder: CoreMLEmbedder, gallery: SkuGallery,
         cfg: FusionConfig = FusionConfig()) {
        self.proposer = proposer
        self.embedder = embedder
        self.gallery = gallery
        self.cfg = cfg
    }

    func calibrate(_ emptyMat: Frame) { proposer.calibrate(emptyMat) }

    func reset() { tracker.reset(); settled.removeAll() }

    func process(_ frame: Frame) throws -> [RecognisedItem] {
        let proposals = proposer.propose(frame)
        let tracks = tracker.update(proposals.map(\.box))
        var byBox: [Box: Track] = [:]
        for t in tracks { byBox[t.box] = t }

        var pending: [(Track, Proposal)] = []
        for p in proposals {
            guard let t = byBox[p.box], settled[t.trackId] == nil else { continue }
            pending.append((t, p))
        }
        if !pending.isEmpty {
            let crops = pending.compactMap { $0.1.crop(frame).cgImage() }
            let vectors = try embedder.embed(crops)
            for ((track, _), v) in zip(pending, vectors) {
                let matches = gallery.match(v, topK: 3)
                let decision = fuse(matches, cfg: cfg)
                track.observe(decision.skuId, matches.map(\.score).max() ?? 0)
                track.lastDecision = decision
            }
        }

        var items: [RecognisedItem] = []
        for track in tracker.confirmed {
            let decision = settled[track.trackId] ?? decide(track)
            if track.hits >= settledHits && settled[track.trackId] == nil { settled[track.trackId] = decision }
            let (_, _, agreement) = track.decision
            items.append(RecognisedItem(trackId: track.trackId, box: track.box, decision: decision,
                                        agreement: agreement, hits: track.hits))
        }
        return items
    }

    private func decide(_ track: Track) -> Decision {
        let (sku, _, _) = track.decision
        guard let last = track.lastDecision else {
            return Decision(status: .unknown, skuId: nil, candidates: [], margin: 0)
        }
        if sku == last.skuId { return last }
        return Decision(status: sku == nil ? .unknown : .accepted, skuId: sku,
                        candidates: last.candidates, margin: last.margin)
    }

    /// Teach the app a product from k views of it on the mat.  The whole
    /// "add a new product" path: no labelling, no training, no restart.
    @discardableResult
    func enrol(_ skuId: String, frames: [Frame]) throws -> Int {
        var crops: [CGImage] = []
        for frame in frames {
            guard let best = proposer.propose(frame).max(by: { $0.areaPx < $1.areaPx }),
                  let img = best.crop(frame).cgImage() else { continue }
            crops.append(img)
        }
        guard !crops.isEmpty else { throw PipelineError.nothingOnTheMat }
        gallery.enrol(skuId, try embedder.embed(crops))
        return gallery.count(skuId)
    }
}

enum PipelineError: LocalizedError {
    case nothingOnTheMat
    var errorDescription: String? { "Nothing found on the mat in any of those frames." }
}
