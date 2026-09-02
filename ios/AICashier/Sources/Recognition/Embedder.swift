import CoreGraphics
import CoreML
import Vision

/// The same MobileNetV3-Small trunk the till runs through ONNX Runtime,
/// exported to Core ML by `tools/export_coreml.py` with the ImageNet
/// normalisation folded in.  Vision resizes the crop to 224x224; the output is
/// the 576-number description of what the crop looks like.
final class CoreMLEmbedder {
    enum Error: Swift.Error { case modelMissing, noOutput }

    let dim: Int
    private let model: VNCoreMLModel

    init(bundle: Bundle = .main) throws {
        guard let url = bundle.url(forResource: "MobileNetV3Small", withExtension: "mlmodelc") else {
            throw Error.modelMissing
        }
        let config = MLModelConfiguration()
        config.computeUnits = .all
        let ml = try MLModel(contentsOf: url, configuration: config)
        model = try VNCoreMLModel(for: ml)
        dim = 576
    }

    func embed(_ image: CGImage) throws -> [Float] {
        let request = VNCoreMLRequest(model: model)
        request.imageCropAndScaleOption = .scaleFill
        try VNImageRequestHandler(cgImage: image, orientation: .up).perform([request])
        guard let obs = request.results?.first as? VNCoreMLFeatureValueObservation,
              let arr = obs.featureValue.multiArrayValue else { throw Error.noOutput }
        var out = [Float](repeating: 0, count: arr.count)
        for i in 0..<arr.count { out[i] = arr[i].floatValue }
        return out
    }

    func embed(_ images: [CGImage]) throws -> [[Float]] {
        try images.map(embed)
    }
}
