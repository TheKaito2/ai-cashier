import CoreGraphics
import CoreVideo
import Foundation

/// A pixel box in full-resolution image coordinates, `x2`/`y2` exclusive.
struct Box: Equatable, Hashable {
    var x1: Int, y1: Int, x2: Int, y2: Int

    var width: Int { x2 - x1 }
    var height: Int { y2 - y1 }
    var area: Int { max(0, width) * max(0, height) }
    var centre: (Double, Double) { (Double(x1 + x2) / 2, Double(y1 + y2) / 2) }
}

/// One camera frame as tightly packed RGBA8, the shape both the proposer and
/// Vision are happy with.  Mirrors the numpy BGR frame in Python.
struct Frame {
    let width: Int
    let height: Int
    var rgba: [UInt8]

    init(width: Int, height: Int, rgba: [UInt8]) {
        self.width = width
        self.height = height
        self.rgba = rgba
    }

    /// Decode any CGImage (PNG, JPEG, a crop) into RGBA8.
    init?(cgImage: CGImage) {
        let w = cgImage.width, h = cgImage.height
        var bytes = [UInt8](repeating: 0, count: w * h * 4)
        let ok = bytes.withUnsafeMutableBytes { buf -> Bool in
            guard let ctx = CGContext(data: buf.baseAddress, width: w, height: h, bitsPerComponent: 8,
                                      bytesPerRow: w * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
                                          | CGBitmapInfo.byteOrder32Big.rawValue) else { return false }
            ctx.draw(cgImage, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        guard ok else { return nil }
        self.init(width: w, height: h, rgba: bytes)
    }

    /// The camera delivers 32BGRA; swap to RGBA once, here.
    init?(pixelBuffer: CVPixelBuffer) {
        guard CVPixelBufferGetPixelFormatType(pixelBuffer) == kCVPixelFormatType_32BGRA else { return nil }
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(pixelBuffer) else { return nil }
        let w = CVPixelBufferGetWidth(pixelBuffer), h = CVPixelBufferGetHeight(pixelBuffer)
        let stride = CVPixelBufferGetBytesPerRow(pixelBuffer)
        var out = [UInt8](repeating: 0, count: w * h * 4)
        let src = base.assumingMemoryBound(to: UInt8.self)
        for y in 0..<h {
            let row = src + y * stride
            var o = y * w * 4
            var i = 0
            for _ in 0..<w {
                out[o] = row[i + 2]; out[o + 1] = row[i + 1]; out[o + 2] = row[i]; out[o + 3] = 255
                o += 4; i += 4
            }
        }
        self.init(width: w, height: h, rgba: out)
    }

    func cgImage() -> CGImage? {
        let data = Data(rgba)
        guard let provider = CGDataProvider(data: data as CFData) else { return nil }
        return CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
                       bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                       bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue
                                                | CGBitmapInfo.byteOrder32Big.rawValue),
                       provider: provider, decode: nil, shouldInterpolate: true, intent: .defaultIntent)
    }

    func crop(_ box: Box) -> Frame {
        let x1 = max(0, box.x1), y1 = max(0, box.y1), x2 = min(width, box.x2), y2 = min(height, box.y2)
        let w = max(1, x2 - x1), h = max(1, y2 - y1)
        var out = [UInt8](repeating: 0, count: w * h * 4)
        for y in 0..<h {
            let s = ((y1 + y) * width + x1) * 4
            out.replaceSubrange(y * w * 4 ..< (y + 1) * w * 4, with: rgba[s ..< s + w * 4])
        }
        return Frame(width: w, height: h, rgba: out)
    }
}
