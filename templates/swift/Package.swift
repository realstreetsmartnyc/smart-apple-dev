// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "{{NAME}}",
    platforms: [
        .iOS(.v15),
    ],
    products: [
        .executable(name: "{{NAME}}", targets: ["{{NAME}}"]),
    ],
    dependencies: [
        .package(url: "https://github.com/firebase/firebase-ios-sdk.git", from: "10.0.0"),
    ],
    targets: [
        .executableTarget(
            name: "{{NAME}}",
            path: "Sources",
            dependencies: [
                .product(name: "FirebaseCore", package: "firebase-ios-sdk"),
                .product(name: "FirebaseAnalytics", package: "firebase-ios-sdk"),
                .product(name: "FirebaseAuth", package: "firebase-ios-sdk"),
                .product(name: "FirebaseFirestore", package: "firebase-ios-sdk"),
                .product(name: "FirebaseStorage", package: "firebase-ios-sdk"),
                .product(name: "FirebaseMessaging", package: "firebase-ios-sdk"),
            ]
        )
    ]
)