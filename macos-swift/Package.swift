// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Z21LocomotiveManager",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Z21Manager", targets: ["Z21Manager"])
    ],
    targets: [
        .systemLibrary(
            name: "CSQLite"
        ),
        .executableTarget(
            name: "Z21Manager",
            dependencies: ["CSQLite"],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
        .testTarget(
            name: "Z21ManagerTests",
            dependencies: ["Z21Manager"],
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
