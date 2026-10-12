import XCTest

final class DeviceMeshUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testFreshInstallShowsSecureLoginSurface() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-ApplePersistenceIgnoreState", "YES"]
        app.launch()

        XCTAssertTrue(app.navigationBars["DeviceMesh"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Secure operator access"].exists)
        XCTAssertTrue(app.textFields["https://mesh.example.com"].exists)
        XCTAssertTrue(app.textFields["Username"].exists)
        XCTAssertTrue(app.secureTextFields["Password"].exists)
        XCTAssertTrue(app.buttons["Sign in"].exists)
    }
}
