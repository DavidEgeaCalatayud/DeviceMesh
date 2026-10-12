import XCTest

final class DeviceMeshUITests: XCTestCase {
    func testUnauthenticatedLaunchShowsLoginSurface() {
        let app = XCUIApplication()
        app.launchArguments += ["-DeviceMeshUITestReset", "1"]
        app.launch()

        XCTAssertTrue(app.navigationBars["DeviceMesh"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.textFields["https://mesh.example.com"].exists)
        XCTAssertTrue(app.textFields["Username"].exists)
        XCTAssertTrue(app.secureTextFields["Password"].exists)
        XCTAssertTrue(app.secureTextFields["MFA possession factor (if enabled)"].exists)
        XCTAssertTrue(app.buttons["Sign in"].exists)
    }
}
