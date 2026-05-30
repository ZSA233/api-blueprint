// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SwiftConformance",
    platforms: [
        .macOS(.v12)
    ],
    dependencies: [
        .package(path: "..")
    ],
    targets: [
        .executableTarget(
            name: "SwiftConformance",
            dependencies: [
                .product(name: "ABClient", package: "swift"),
                .product(name: "ABClientRuntime", package: "swift"),
                .product(name: "ABClientAPIRoutes", package: "swift"),
                .product(name: "ABClientAltRoutes", package: "swift"),
            ]
        )
    ]
)
