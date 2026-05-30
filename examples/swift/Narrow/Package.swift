// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SwiftNarrowEntrypoint",
    platforms: [
        .macOS(.v12)
    ],
    dependencies: [
        .package(path: "..")
    ],
    targets: [
        .executableTarget(
            name: "SwiftNarrowEntrypoint",
            dependencies: [
                .product(name: "ABClientRuntime", package: "swift"),
                .product(name: "ABClientAPIRoutes", package: "swift"),
            ]
        )
    ]
)
