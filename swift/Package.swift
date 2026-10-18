// swift-tools-version: 6.0
import PackageDescription

let package = Package(
  name: "TARS",
  platforms: [.macOS(.v15)],
  products: [
    .executable(name: "TARSApp", targets: ["TARSApp"]),
    .library(name: "TARSKit", targets: ["TARSKit"]),
  ],
  targets: [
    .target(
      name: "TARSKit",
      path: "Sources/TARSKit",
      swiftSettings: [.swiftLanguageMode(.v6)]
    ),
    .executableTarget(
      name: "TARSApp",
      dependencies: ["TARSKit"],
      path: "Sources/TARSApp",
      swiftSettings: [.swiftLanguageMode(.v6)]
    ),
    .testTarget(
      name: "TARSKitTests",
      dependencies: ["TARSKit"],
      path: "Tests/TARSKitTests",
      swiftSettings: [.swiftLanguageMode(.v6)]
    ),
  ]
)
