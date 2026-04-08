// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "EPL Auth Demo",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "EPL Auth Demo", targets: ["EPL Auth Demo"]),
    ],
    targets: [
        .target(name: "EPL Auth Demo", path: "EPL Auth Demo"),
        .testTarget(name: "EPL Auth DemoTests",
                     dependencies: ["EPL Auth Demo"],
                     path: "EPL Auth DemoTests"),
    ]
)
