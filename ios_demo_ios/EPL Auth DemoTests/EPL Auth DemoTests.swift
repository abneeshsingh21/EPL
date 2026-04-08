import XCTest
@testable import EPL Auth Demo

final class EPL Auth DemoTests: XCTestCase {
    func testRuntimeMath() throws {
        let runtime = EPLRuntime()
        XCTAssertEqual(runtime.abs(-5), 5.0)
        XCTAssertEqual(runtime.round(3.7), 4.0)
    }

    func testRuntimeStrings() throws {
        let runtime = EPLRuntime()
        XCTAssertEqual(runtime.toText(42), "42")
        XCTAssertEqual(runtime.length("hello"), 5)
    }
}
