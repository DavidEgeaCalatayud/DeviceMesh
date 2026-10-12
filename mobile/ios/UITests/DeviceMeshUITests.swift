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

    func testAuthenticatedLaunchNavigatesOperatorTabs() {
        let app = XCUIApplication()
        app.launchArguments += ["-DeviceMeshUITestAuthenticated"]
        app.launch()

        XCTAssertTrue(app.navigationBars["DeviceMesh"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Online devices"].exists)

        app.tabBars.buttons["Devices"].tap()
        XCTAssertTrue(app.navigationBars["Devices"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Incidents"].tap()
        XCTAssertTrue(app.navigationBars["Incidents"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Alerts"].tap()
        XCTAssertTrue(app.navigationBars["Alerts"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Synthetics"].tap()
        XCTAssertTrue(app.navigationBars["Synthetics"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Distributed probes"].exists)
    }
}
