import Foundation

/// Where the products are, without caring what they are.
///
/// A port of `recognition/proposer.py`: the empty mat is photographed once,
/// every later frame is differenced against it in colour at half resolution,
/// shadows (same chromaticity, lower intensity) are dropped, the mask is
/// closed and opened, and each remaining blob becomes a box.  Class-agnostic
/// by construction, which is what lets a product the app has never seen be
/// found at all.
struct Proposal {
    let box: Box
    let areaPx: Int

    func crop(_ frame: Frame, pad: Int = 6) -> Frame {
        frame.crop(Box(x1: box.x1 - pad, y1: box.y1 - pad, x2: box.x2 + pad, y2: box.y2 + pad))
    }
}

final class BackgroundSubtractionProposer {
    var minAreaPx = 4000
    var diffThreshold: Int = 28
    var maxProposals = 12
    let downscale = 2
    var shadowChromaEps: Float = 0.04
    var shadowRatio: (lo: Float, hi: Float) = (0.55, 0.95)

    /// Half-resolution, blurred RGB.
    struct Small {
        let w: Int, h: Int
        var rgb: [UInt8]
    }

    private var background: Small?
    var isCalibrated: Bool { background != nil }

    func calibrate(_ frame: Frame) {
        background = prepare(frame)
    }

    func propose(_ frame: Frame) -> [Proposal] {
        guard let bg = background else { return [] }
        let cur = prepare(frame)
        guard cur.w == bg.w, cur.h == bg.h else { return [] }
        let n = cur.w * cur.h
        var mask = [UInt8](repeating: 0, count: n)
        let lo = shadowRatio.lo, hi = shadowRatio.hi
        for i in 0..<n {
            let b0 = Int(bg.rgb[i * 3]), b1 = Int(bg.rgb[i * 3 + 1]), b2 = Int(bg.rgb[i * 3 + 2])
            let c0 = Int(cur.rgb[i * 3]), c1 = Int(cur.rgb[i * 3 + 1]), c2 = Int(cur.rgb[i * 3 + 2])
            let d = max(abs(b0 - c0), abs(b1 - c1), abs(b2 - c2))
            guard d > diffThreshold else { continue }
            if shadowChromaEps > 0 {
                // a shadow is the mat, darker: same chromaticity, lower intensity
                let bs = Float(b0 + b1 + b2) + 1, cs = Float(c0 + c1 + c2) + 1
                let chroma = max(abs(Float(b0) / bs - Float(c0) / cs),
                                 abs(Float(b1) / bs - Float(c1) / cs),
                                 abs(Float(b2) / bs - Float(c2) / cs))
                let ratio = cs / bs
                if chroma < shadowChromaEps && ratio > lo && ratio < hi { continue }
            }
            mask[i] = 255
        }
        // close x2 (join the packet's printed graphics into one blob), then open (drop speckle)
        for _ in 0..<2 { mask = Morphology.dilate(mask, cur.w, cur.h, 4); mask = Morphology.erode(mask, cur.w, cur.h, 4) }
        mask = Morphology.erode(mask, cur.w, cur.h, 4)
        mask = Morphology.dilate(mask, cur.w, cur.h, 4)

        let d = downscale
        var out: [Proposal] = []
        for c in ConnectedComponents.find(mask, cur.w, cur.h) {
            guard c.area * d * d >= minAreaPx else { continue }
            out.append(Proposal(box: Box(x1: c.x1 * d, y1: c.y1 * d, x2: (c.x2 + 1) * d, y2: (c.y2 + 1) * d),
                                areaPx: c.area * d * d))
        }
        out.sort { $0.areaPx > $1.areaPx }
        return Array(out.prefix(maxProposals))
    }

    // MARK: - preparation: 2x2 average downscale, then a 5x5 box blur

    private func prepare(_ frame: Frame) -> Small {
        let w = frame.width / downscale, h = frame.height / downscale
        var rgb = [UInt8](repeating: 0, count: w * h * 3)
        let fw = frame.width
        for y in 0..<h {
            for x in 0..<w {
                let p0 = ((y * 2) * fw + x * 2) * 4, p1 = p0 + 4, p2 = p0 + fw * 4, p3 = p2 + 4
                let o = (y * w + x) * 3
                for c in 0..<3 {
                    let s = Int(frame.rgba[p0 + c]) + Int(frame.rgba[p1 + c]) + Int(frame.rgba[p2 + c]) + Int(frame.rgba[p3 + c])
                    rgb[o + c] = UInt8(s / 4)
                }
            }
        }
        return Small(w: w, h: h, rgb: Blur.box5(rgb, w, h))
    }
}

enum Blur {
    /// Separable 5x5 box blur on interleaved RGB, edges clamped.
    static func box5(_ src: [UInt8], _ w: Int, _ h: Int) -> [UInt8] {
        var tmp = [Int](repeating: 0, count: w * h * 3)
        for y in 0..<h {
            for x in 0..<w {
                for c in 0..<3 {
                    var s = 0
                    for k in -2...2 { s += Int(src[(y * w + min(w - 1, max(0, x + k))) * 3 + c]) }
                    tmp[(y * w + x) * 3 + c] = s
                }
            }
        }
        var out = [UInt8](repeating: 0, count: w * h * 3)
        for y in 0..<h {
            for x in 0..<w {
                for c in 0..<3 {
                    var s = 0
                    for k in -2...2 { s += tmp[(min(h - 1, max(0, y + k)) * w + x) * 3 + c] }
                    out[(y * w + x) * 3 + c] = UInt8(s / 25)
                }
            }
        }
        return out
    }
}

enum Morphology {
    /// Square (2r+1) structuring element, separable max / min.
    static func dilate(_ m: [UInt8], _ w: Int, _ h: Int, _ r: Int) -> [UInt8] { pass(m, w, h, r, max) }
    static func erode(_ m: [UInt8], _ w: Int, _ h: Int, _ r: Int) -> [UInt8] { pass(m, w, h, r, min) }

    private static func pass(_ m: [UInt8], _ w: Int, _ h: Int, _ r: Int, _ f: (UInt8, UInt8) -> UInt8) -> [UInt8] {
        var tmp = [UInt8](repeating: 0, count: w * h)
        for y in 0..<h {
            for x in 0..<w {
                var v = m[y * w + x]
                for k in 1...r {
                    if x - k >= 0 { v = f(v, m[y * w + x - k]) }
                    if x + k < w { v = f(v, m[y * w + x + k]) }
                }
                tmp[y * w + x] = v
            }
        }
        var out = [UInt8](repeating: 0, count: w * h)
        for y in 0..<h {
            for x in 0..<w {
                var v = tmp[y * w + x]
                for k in 1...r {
                    if y - k >= 0 { v = f(v, tmp[(y - k) * w + x]) }
                    if y + k < h { v = f(v, tmp[(y + k) * w + x]) }
                }
                out[y * w + x] = v
            }
        }
        return out
    }
}

enum ConnectedComponents {
    struct Component { var x1: Int, y1: Int, x2: Int, y2: Int, area: Int }

    /// 8-connected blobs of a binary mask, by flood fill.
    static func find(_ mask: [UInt8], _ w: Int, _ h: Int) -> [Component] {
        var seen = [Bool](repeating: false, count: w * h)
        var out: [Component] = []
        var stack: [Int] = []
        for start in 0..<(w * h) where mask[start] != 0 && !seen[start] {
            var c = Component(x1: w, y1: h, x2: 0, y2: 0, area: 0)
            stack.removeAll(keepingCapacity: true)
            stack.append(start)
            seen[start] = true
            while let i = stack.popLast() {
                let x = i % w, y = i / w
                c.area += 1
                c.x1 = min(c.x1, x); c.x2 = max(c.x2, x); c.y1 = min(c.y1, y); c.y2 = max(c.y2, y)
                for dy in -1...1 {
                    for dx in -1...1 where dx != 0 || dy != 0 {
                        let nx = x + dx, ny = y + dy
                        guard nx >= 0, ny >= 0, nx < w, ny < h else { continue }
                        let j = ny * w + nx
                        if mask[j] != 0 && !seen[j] { seen[j] = true; stack.append(j) }
                    }
                }
            }
            out.append(c)
        }
        return out
    }
}
