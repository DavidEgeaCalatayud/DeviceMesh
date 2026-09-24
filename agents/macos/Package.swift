// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "DeviceMeshMacAgent",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "devicemesh-macos-agent", targets: ["DeviceMeshMacAgent"]),
    ],
    targets: [
        .executableTarget(
            name: "DeviceMeshMacAgent",
            linkerSettings: [.linkedFramework("Security")]
        ),
        .testTarget(
            name: "DeviceMeshMacAgentTests",
            dependencies: ["DeviceMeshMacAgent"]
        ),
    ]
)
