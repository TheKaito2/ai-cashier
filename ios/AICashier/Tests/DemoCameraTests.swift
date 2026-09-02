import XCTest
@testable import AICashier

final class DemoCameraTests: XCTestCase {
    func testTheBundledDemoImagesDecode() throws {
        let frame = DemoCamera().latest()
        XCTAssertNotNil(frame, "demo_frame.jpg did not decode from the app bundle")
        XCTAssertEqual(frame?.width, 1280)
        let mat = DemoCamera(resource: "demo_mat", ext: "png").latest()
        XCTAssertNotNil(mat)
        XCTAssertNotNil(frame?.cgImage())
        let p = BackgroundSubtractionProposer()
        p.calibrate(mat!)
        XCTAssertEqual(p.propose(frame!).count, 2, "the two demo packets")
    }
}
