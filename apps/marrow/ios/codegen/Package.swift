// swift-tools-version: 5.10
// ponytail: manifest-only package — exists solely so `swift run swift-openapi-generator`
// resolves the pinned CLI. Pinned exact so checked-in generated code is reproducible.
import PackageDescription

let package = Package(
    name: "codegen",
    platforms: [.macOS(.v13)],
    dependencies: [
        .package(url: "https://github.com/apple/swift-openapi-generator", exact: "1.13.0")
    ]
)
