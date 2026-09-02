import XCTest
@testable import AICashier

final class EmbedderTests: XCTestCase {
    /// The Core ML trunk sees the same crops as the ONNX trunk on the till.
    func testCoreMLEmbeddingsMatchTheOnnxFixtures() throws {
        let f = try FX.load()
        let embedder = try CoreMLEmbedder()
        XCTAssertEqual(embedder.dim, f.embedder.dim)
        var worst: Float = 1
        for (name, _) in f.crops {
            let v = try embedder.embed(try FX.image(name, sub: "Fixtures/crops"))
            XCTAssertEqual(v.count, f.embedder.dim)
            let cos = FX.cosine(v, f.embeddings[name]!)
            worst = min(worst, cos)
            XCTAssertGreaterThan(cos, 0.98, "\(name): cosine \(cos) against the Python embedding")
        }
        print("worst Core ML vs ONNX cosine over \(f.crops.count) crops: \(worst)")
    }
}

final class GalleryTests: XCTestCase {
    func testFrozenCentreEqualsPython() throws {
        let f = try FX.load()
        let g = FX.gallery(from: f)
        XCTAssertTrue(g.frozen)
        let diff = zip(g.centre!, f.gallery.centre).map { abs($0 - $1) }.max() ?? 1
        XCTAssertLessThan(diff, 1e-4)
    }

    func testEveryQueryRanksAsPythonDid() throws {
        let f = try FX.load()
        let g = FX.gallery(from: f)
        for (name, exp) in f.expected_matches {
            let m = g.match(f.embeddings[name]!, topK: 3)
            XCTAssertEqual(m.first?.skuId, exp.top1, name)
            XCTAssertEqual(m.first?.score ?? -2, exp.score, accuracy: 1e-3, name)
            let decision = fuse(m, cfg: FusionConfig(rejectBelowCosine: f.thresholds.reject_below_cosine))
            XCTAssertEqual(decision.status != .unknown, exp.accepted, "\(name): accepted?")
        }
    }

    func testEnrollingAfterTheFreezeMovesNoExistingScore() throws {
        let f = try FX.load()
        let g = FX.gallery(from: f)
        let queries = f.expected_matches.keys.sorted()
        let before = queries.map { g.match(f.embeddings[$0]!)[0].score }
        g.enrol("extra", [f.embeddings["never-enrolled-snack-0"]!])
        let after = queries.map { g.match(f.embeddings[$0]!)[0].score }
        for (a, b) in zip(before, after) { XCTAssertEqual(a, b, accuracy: 1e-6) }
    }
}

final class ProposerTests: XCTestCase {
    func testTwoProductsOnTheSceneAreFoundWhereTheTillFoundThem() throws {
        let f = try FX.load()
        let mat = try XCTUnwrap(Frame(cgImage: try FX.image("mat")))
        let scene = try XCTUnwrap(Frame(cgImage: try FX.image("scene")))
        let p = BackgroundSubtractionProposer()
        p.calibrate(mat)
        let found = p.propose(scene).map(\.box)
        XCTAssertEqual(found.count, f.scene_boxes.count, "boxes: \(found)")
        for e in f.scene_boxes {
            let hit = found.contains { abs($0.x1 - e[0]) <= 12 && abs($0.y1 - e[1]) <= 12 && abs($0.x2 - e[2]) <= 12 && abs($0.y2 - e[3]) <= 12 }
            XCTAssertTrue(hit, "no box within 12 px of \(e); found \(found)")
        }
    }

    func testTheEmptyMatProposesNothing() throws {
        let mat = try XCTUnwrap(Frame(cgImage: try FX.image("mat")))
        let p = BackgroundSubtractionProposer()
        p.calibrate(mat)
        XCTAssertEqual(p.propose(mat).count, 0)
    }

    func testASoftShadowOnTheMatProposesNothing() {
        var rgba = [UInt8](repeating: 0, count: 640 * 480 * 4)
        for i in 0..<(640 * 480) { rgba[i * 4] = 120; rgba[i * 4 + 1] = 110; rgba[i * 4 + 2] = 100; rgba[i * 4 + 3] = 255 }
        let mat = Frame(width: 640, height: 480, rgba: rgba)
        var shadowed = rgba
        for y in 150..<330 { for x in 200..<440 { let i = (y * 640 + x) * 4; shadowed[i] = 72; shadowed[i + 1] = 66; shadowed[i + 2] = 60 } }
        let p = BackgroundSubtractionProposer()
        p.calibrate(mat)
        XCTAssertEqual(p.propose(Frame(width: 640, height: 480, rgba: shadowed)).count, 0)
        var blue = rgba
        for y in 150..<330 { for x in 200..<440 { let i = (y * 640 + x) * 4; blue[i] = 40; blue[i + 1] = 40; blue[i + 2] = 140 } }
        XCTAssertEqual(p.propose(Frame(width: 640, height: 480, rgba: blue)).count, 1)
    }
}

final class TrackerTests: XCTestCase {
    func testAStillItemIsOneTrack() {
        let t = CentroidTracker()
        let box = Box(x1: 100, y1: 100, x2: 300, y2: 400)
        for _ in 0..<5 { _ = t.update([box]) }
        XCTAssertEqual(t.confirmed.count, 1)
        XCTAssertEqual(t.confirmed.first?.hits, 5)
    }
}
