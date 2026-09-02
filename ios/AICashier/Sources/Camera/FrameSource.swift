import AVFoundation
import CoreGraphics
import Foundation
import UIKit

/// Where frames come from: the phone camera, or the bundled demo frame when
/// there is no camera (the Simulator, or a laptop running the UI).
protocol FrameSource: AnyObject {
    var name: String { get }
    func start()
    func stop()
    func latest() -> Frame?
    /// Lock exposure and white balance at their current values (a retrieval
    /// system must see the same packet the same way at enrolment and at
    /// checkout).  No-op where there is nothing to lock.
    func setLocked(_ locked: Bool)
}

/// The app's `--demo`: replays one still image.
final class DemoCamera: FrameSource {
    let name = "Demo image"
    private let frame: Frame?

    init(resource: String = "demo_frame", ext: String = "jpg", bundle: Bundle = .main) {
        if let url = bundle.url(forResource: resource, withExtension: ext), let ui = UIImage(contentsOfFile: url.path),
           let cg = ui.cgImage {
            frame = Frame(cgImage: cg)
        } else {
            frame = nil
        }
    }

    func start() {}
    func stop() {}
    func latest() -> Frame? { frame }
    func setLocked(_ locked: Bool) {}
}

/// The back camera at 1280x720, BGRA, latest frame kept in memory only.
final class CameraSession: NSObject, FrameSource, AVCaptureVideoDataOutputSampleBufferDelegate {
    let name = "Camera"
    private let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "camera.frames")
    private var device: AVCaptureDevice?
    private var current: CVPixelBuffer?
    private let lock = NSLock()

    static var isAvailable: Bool {
        #if targetEnvironment(simulator)
        return false
        #else
        return AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) != nil
        #endif
    }

    override init() {
        super.init()
        session.beginConfiguration()
        session.sessionPreset = .hd1280x720
        if let dev = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
           let input = try? AVCaptureDeviceInput(device: dev), session.canAddInput(input) {
            session.addInput(input)
            device = dev
        }
        let output = AVCaptureVideoDataOutput()
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: queue)
        if session.canAddOutput(output) { session.addOutput(output) }
        if let conn = output.connection(with: .video), conn.isVideoRotationAngleSupported(90) {
            conn.videoRotationAngle = 90          // portrait phone, landscape mat
        }
        session.commitConfiguration()
    }

    func start() {
        guard !session.isRunning else { return }
        queue.async { self.session.startRunning() }
    }

    func stop() {
        guard session.isRunning else { return }
        queue.async { self.session.stopRunning() }
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let pb = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lock.lock(); current = pb; lock.unlock()
    }

    func latest() -> Frame? {
        lock.lock(); let pb = current; lock.unlock()
        return pb.flatMap(Frame.init(pixelBuffer:))
    }

    func setLocked(_ locked: Bool) {
        guard let dev = device, (try? dev.lockForConfiguration()) != nil else { return }
        defer { dev.unlockForConfiguration() }
        if locked {
            if dev.isExposureModeSupported(.locked) { dev.exposureMode = .locked }
            if dev.isWhiteBalanceModeSupported(.locked) { dev.whiteBalanceMode = .locked }
        } else {
            if dev.isExposureModeSupported(.continuousAutoExposure) { dev.exposureMode = .continuousAutoExposure }
            if dev.isWhiteBalanceModeSupported(.continuousAutoWhiteBalance) { dev.whiteBalanceMode = .continuousAutoWhiteBalance }
        }
    }
}
