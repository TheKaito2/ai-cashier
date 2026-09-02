import CoreGraphics
import UIKit
import XCTest
@testable import AICashier

/// `tools/export_fixtures.py` writes these from the Python implementation.
/// Every test here asks the Swift port to reproduce them.
struct Fixtures: Decodable {
    struct Embedder: Decodable { let dim: Int }
    struct Thresholds: Decodable { let reject_below_cosine: Float; let ambiguous_margin: Float; let appearance_temperature: Float }
    struct Crop: Decodable { let sku: String; let role: String }
    struct Gallery: Decodable { let enrolled: [String]; let k: Int; let centre: [Float] }
    struct Expected: Decodable { let top1: String; let score: Float; let accepted: Bool }
    struct PromptPayVector: Decodable { let target: String; let amount: Double?; let payload: String }
    struct Crc: Decodable { let input: String; let value: Int }

    let embedder: Embedder
    let thresholds: Thresholds
    let crops: [String: Crop]
    let embeddings: [String: [Float]]
    let gallery: Gallery
    let expected_matches: [String: Expected]
    let scene_boxes: [[Int]]
    let promptpay: [PromptPayVector]
    let crc16_check: Crc
}

private final class Marker {}

enum FX {
    static var bundle: Bundle { Bundle(for: Marker.self) }

    static func load() throws -> Fixtures {
        let url = try XCTUnwrap(bundle.url(forResource: "fixtures", withExtension: "json", subdirectory: "Fixtures"))
        return try JSONDecoder().decode(Fixtures.self, from: Data(contentsOf: url))
    }

    static func image(_ name: String, sub: String = "Fixtures") throws -> CGImage {
        let url = try XCTUnwrap(bundle.url(forResource: name, withExtension: "png", subdirectory: sub), "missing \(sub)/\(name).png")
        return try XCTUnwrap(UIImage(contentsOfFile: url.path)?.cgImage)
    }

    static func cosine(_ a: [Float], _ b: [Float]) -> Float {
        Vec.dot(Vec.l2(a), Vec.l2(b))
    }

    static func gallery(from f: Fixtures) -> SkuGallery {
        let g = SkuGallery(dim: f.embedder.dim)
        for sku in f.gallery.enrolled {
            for n in 0..<f.gallery.k { g.enrol(sku, [f.embeddings["\(sku)-\(n)"]!]) }
        }
        g.freezeCentre()
        return g
    }
}
