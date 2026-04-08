# EPL Auth Demo

iOS application generated from EPL source code using SwiftUI.

## Prerequisites

- macOS 13+ with Xcode 15+
- iOS 16.0+ deployment target
- Apple Developer account (for device deployment)

## Build & Run

### Using Xcode
1. Open `EPL Auth Demo.xcodeproj` in Xcode
2. Select your target device/simulator
3. Press Cmd+R to build and run

### Using Command Line
```bash
# Build
xcodebuild -project EPL Auth Demo.xcodeproj -scheme EPL Auth Demo -sdk iphonesimulator build

# Run tests
xcodebuild -project EPL Auth Demo.xcodeproj -scheme EPL Auth Demo -sdk iphonesimulator test

# Archive for distribution
xcodebuild -project EPL Auth Demo.xcodeproj -scheme EPL Auth Demo -sdk iphoneos archive
```

## Project Structure

```
EPL Auth Demo/
    EPL Auth DemoApp.swift    — App entry point
    Views/
        ContentView.swift       — Main UI (generated from EPL)
    EPLRuntime.swift            — EPL standard library bridge
    Assets.xcassets/            — App icons and assets
```
