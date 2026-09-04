import UIKit
import XCTest
@testable import AICashier

final class FontsTests: XCTestCase {
    /// The bundled Plex faces must register under the PostScript names Theme uses,
    /// or every screen silently falls back to San Francisco.
    func testTheBundledPlexFacesRegister() {
        for name in ["IBMPlexSansThai", "IBMPlexSansThai-Medm", "IBMPlexSansThai-SmBld", "IBMPlexSansThai-Bold",
                     "IBMPlexMono", "IBMPlexMono-Medm", "IBMPlexMono-SmBld"] {
            XCTAssertNotNil(UIFont(name: name, size: 12), name)
        }
    }
}
