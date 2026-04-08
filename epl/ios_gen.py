"""
EPL iOS/Swift Project Generator v1.0
=====================================
Generates a complete Xcode project from EPL AST, targeting iOS with SwiftUI.

Generates:
- SwiftUI views from EPL GUI definitions
- Swift Package Manager project structure
- Xcode project file (.xcodeproj)
- App lifecycle (App + ContentView)
- EPLRuntime.swift standard library bridge
"""

import os
import uuid
from epl import ast_nodes as ast


class IOSProjectGenerator:
    """Generates a complete iOS/SwiftUI project from EPL AST."""

    SWIFT_VERSION = "5.9"
    IOS_DEPLOYMENT_TARGET = "16.0"

    def __init__(self, app_name="EPLApp", bundle_id="com.epl.app",
                 team_id=None):
        self.app_name = app_name
        self.bundle_id = bundle_id
        self.team_id = team_id or ""
        self.version = "1.0.0"
        self.build_number = "1"

    def generate(self, program, output_dir: str) -> str:
        """Generate a complete iOS project."""
        os.makedirs(output_dir, exist_ok=True)

        gen = SwiftUIGenerator(self.app_name, self.bundle_id)
        content_view = gen.generate(program)
        runtime_swift = gen.generate_runtime()
        app_swift = gen.generate_app()

        # Project structure
        src_dir = f'{output_dir}/{self.app_name}'
        dirs = [
            src_dir,
            f'{src_dir}/Views',
            f'{src_dir}/Models',
            f'{src_dir}/Assets.xcassets/AppIcon.appiconset',
            f'{src_dir}/Assets.xcassets/AccentColor.colorset',
            f'{src_dir}/Preview Content/Preview Assets.xcassets',
            f'{output_dir}/{self.app_name}.xcodeproj',
            f'{output_dir}/{self.app_name}Tests',
            f'{output_dir}/{self.app_name}UITests',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        self._write(f'{src_dir}/{self.app_name}App.swift', app_swift)
        self._write(f'{src_dir}/Views/ContentView.swift', content_view)
        self._write(f'{src_dir}/EPLRuntime.swift', runtime_swift)
        self._write(f'{src_dir}/Info.plist', self._info_plist())
        self._write(f'{src_dir}/Assets.xcassets/Contents.json', '{"info":{"version":1,"author":"xcode"}}')
        self._write(f'{src_dir}/Assets.xcassets/AccentColor.colorset/Contents.json',
                     '{"colors":[{"idiom":"universal"}],"info":{"version":1,"author":"xcode"}}')
        self._write(f'{src_dir}/Assets.xcassets/AppIcon.appiconset/Contents.json',
                     self._app_icon_contents())
        self._write(f'{src_dir}/Preview Content/Preview Assets.xcassets/Contents.json',
                     '{"info":{"version":1,"author":"xcode"}}')
        self._write(f'{output_dir}/{self.app_name}.xcodeproj/project.pbxproj',
                     self._pbxproj())
        self._write(f'{output_dir}/{self.app_name}Tests/{self.app_name}Tests.swift',
                     self._test_file())
        self._write(f'{output_dir}/{self.app_name}UITests/{self.app_name}UITests.swift',
                     self._ui_test_file())
        self._write(f'{output_dir}/Package.swift', self._package_swift())
        self._write(f'{output_dir}/.gitignore', self._gitignore())
        self._write(f'{output_dir}/README.md', self._readme())

        return output_dir

    def _write(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _info_plist(self):
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>{self.app_name}</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>{self.bundle_id}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>{self.version}</string>
    <key>CFBundleVersion</key>
    <string>{self.build_number}</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UIApplicationSceneManifest</key>
    <dict>
        <key>UIApplicationSupportsMultipleScenes</key>
        <true/>
    </dict>
    <key>UILaunchScreen</key>
    <dict/>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
        <string>UIInterfaceOrientationLandscapeLeft</string>
        <string>UIInterfaceOrientationLandscapeRight</string>
    </array>
</dict>
</plist>'''

    def _app_icon_contents(self):
        return '''{
  "images": [
    {"idiom": "universal", "platform": "ios", "size": "1024x1024"}
  ],
  "info": {"version": 1, "author": "xcode"}
}'''

    def _pbxproj(self):
        """Generate a valid Xcode project.pbxproj file."""
        # Generate stable UUIDs based on app name for reproducibility
        def _uuid(seed):
            import hashlib
            h = hashlib.sha256(f'{self.app_name}:{seed}'.encode()).hexdigest()[:24].upper()
            return h

        root = _uuid('root')
        main_group = _uuid('main_group')
        src_group = _uuid('src_group')
        views_group = _uuid('views_group')
        target = _uuid('target')
        build_config_list = _uuid('bcl')
        debug_config = _uuid('debug')
        release_config = _uuid('release')
        target_bcl = _uuid('target_bcl')
        target_debug = _uuid('target_debug')
        target_release = _uuid('target_release')
        app_file = _uuid('app_file')
        content_file = _uuid('content_file')
        runtime_file = _uuid('runtime_file')
        app_ref = _uuid('app_ref')
        content_ref = _uuid('content_ref')
        runtime_ref = _uuid('runtime_ref')
        sources_phase = _uuid('sources')
        frameworks_phase = _uuid('frameworks')
        resources_phase = _uuid('resources')
        assets_ref = _uuid('assets_ref')
        assets_build = _uuid('assets_build')
        products_group = _uuid('products')
        product_ref = _uuid('product_ref')

        return f'''// !$*UTF8*$!
{{
    archiveVersion = 1;
    classes = {{}};
    objectVersion = 56;
    objects = {{

/* Begin PBXBuildFile section */
        {app_file} /* {self.app_name}App.swift in Sources */ = {{
            isa = PBXBuildFile; fileRef = {app_ref};
        }};
        {content_file} /* ContentView.swift in Sources */ = {{
            isa = PBXBuildFile; fileRef = {content_ref};
        }};
        {runtime_file} /* EPLRuntime.swift in Sources */ = {{
            isa = PBXBuildFile; fileRef = {runtime_ref};
        }};
        {assets_build} /* Assets.xcassets in Resources */ = {{
            isa = PBXBuildFile; fileRef = {assets_ref};
        }};
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
        {product_ref} /* {self.app_name}.app */ = {{
            isa = PBXFileReference; explicitFileType = wrapper.application;
            includeInIndex = 0; path = "{self.app_name}.app";
            sourceTree = BUILT_PRODUCTS_DIR;
        }};
        {app_ref} /* {self.app_name}App.swift */ = {{
            isa = PBXFileReference; lastKnownFileType = sourcecode.swift;
            path = "{self.app_name}App.swift"; sourceTree = "<group>";
        }};
        {content_ref} /* ContentView.swift */ = {{
            isa = PBXFileReference; lastKnownFileType = sourcecode.swift;
            path = "ContentView.swift"; sourceTree = "<group>";
        }};
        {runtime_ref} /* EPLRuntime.swift */ = {{
            isa = PBXFileReference; lastKnownFileType = sourcecode.swift;
            path = "EPLRuntime.swift"; sourceTree = "<group>";
        }};
        {assets_ref} /* Assets.xcassets */ = {{
            isa = PBXFileReference; lastKnownFileType = folder.assetcatalog;
            path = "Assets.xcassets"; sourceTree = "<group>";
        }};
/* End PBXFileReference section */

/* Begin PBXGroup section */
        {main_group} = {{
            isa = PBXGroup;
            children = ({src_group}, {products_group});
            sourceTree = "<group>";
        }};
        {src_group} /* {self.app_name} */ = {{
            isa = PBXGroup;
            children = ({app_ref}, {views_group}, {runtime_ref}, {assets_ref});
            path = "{self.app_name}";
            sourceTree = "<group>";
        }};
        {views_group} /* Views */ = {{
            isa = PBXGroup;
            children = ({content_ref});
            path = "Views";
            sourceTree = "<group>";
        }};
        {products_group} /* Products */ = {{
            isa = PBXGroup;
            children = ({product_ref});
            name = Products;
            sourceTree = "<group>";
        }};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
        {target} /* {self.app_name} */ = {{
            isa = PBXNativeTarget;
            buildConfigurationList = {target_bcl};
            buildPhases = ({sources_phase}, {frameworks_phase}, {resources_phase});
            buildRules = ();
            dependencies = ();
            name = "{self.app_name}";
            productName = "{self.app_name}";
            productReference = {product_ref};
            productType = "com.apple.product-type.application";
        }};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
        {root} /* Project object */ = {{
            isa = PBXProject;
            attributes = {{
                BuildIndependentTargetsInParallel = 1;
                LastSwiftUpdateCheck = 1500;
                LastUpgradeCheck = 1500;
            }};
            buildConfigurationList = {build_config_list};
            compatibilityVersion = "Xcode 14.0";
            developmentRegion = en;
            hasScannedForEncodings = 0;
            knownRegions = (en, Base);
            mainGroup = {main_group};
            productRefGroup = {products_group};
            projectDirPath = "";
            projectRoot = "";
            targets = ({target});
        }};
/* End PBXProject section */

/* Begin PBXSourcesBuildPhase section */
        {sources_phase} /* Sources */ = {{
            isa = PBXSourcesBuildPhase;
            buildActionMask = 2147483647;
            files = ({app_file}, {content_file}, {runtime_file});
            runOnlyForDeploymentPostprocessing = 0;
        }};
/* End PBXSourcesBuildPhase section */

/* Begin PBXFrameworksBuildPhase section */
        {frameworks_phase} /* Frameworks */ = {{
            isa = PBXFrameworksBuildPhase;
            buildActionMask = 2147483647;
            files = ();
            runOnlyForDeploymentPostprocessing = 0;
        }};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXResourcesBuildPhase section */
        {resources_phase} /* Resources */ = {{
            isa = PBXResourcesBuildPhase;
            buildActionMask = 2147483647;
            files = ({assets_build});
            runOnlyForDeploymentPostprocessing = 0;
        }};
/* End PBXResourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
        {debug_config} /* Debug */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                ALWAYS_SEARCH_USER_PATHS = NO;
                CLANG_ENABLE_MODULES = YES;
                COPY_PHASE_STRIP = NO;
                DEBUG_INFORMATION_FORMAT = dwarf;
                ENABLE_STRICT_OBJC_MSGSEND = YES;
                GCC_DYNAMIC_NO_PIC = NO;
                GCC_OPTIMIZATION_LEVEL = 0;
                GCC_PREPROCESSOR_DEFINITIONS = ("DEBUG=1", "$(inherited)");
                MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
                ONLY_ACTIVE_ARCH = YES;
                SDKROOT = iphoneos;
                SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;
                SWIFT_OPTIMIZATION_LEVEL = "-Onone";
            }};
            name = Debug;
        }};
        {release_config} /* Release */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                ALWAYS_SEARCH_USER_PATHS = NO;
                CLANG_ENABLE_MODULES = YES;
                COPY_PHASE_STRIP = NO;
                DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
                ENABLE_NS_ASSERTIONS = NO;
                ENABLE_STRICT_OBJC_MSGSEND = YES;
                MTL_ENABLE_DEBUG_INFO = NO;
                SDKROOT = iphoneos;
                SWIFT_COMPILATION_MODE = wholemodule;
                SWIFT_OPTIMIZATION_LEVEL = "-O";
                VALIDATE_PRODUCT = YES;
            }};
            name = Release;
        }};
        {target_debug} /* Debug */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
                CURRENT_PROJECT_VERSION = {self.build_number};
                DEVELOPMENT_TEAM = "{self.team_id}";
                GENERATE_INFOPLIST_FILE = YES;
                INFOPLIST_FILE = "{self.app_name}/Info.plist";
                IPHONEOS_DEPLOYMENT_TARGET = {self.IOS_DEPLOYMENT_TARGET};
                MARKETING_VERSION = {self.version};
                PRODUCT_BUNDLE_IDENTIFIER = "{self.bundle_id}";
                PRODUCT_NAME = "$(TARGET_NAME)";
                SWIFT_EMIT_LOC_STRINGS = YES;
                SWIFT_VERSION = {self.SWIFT_VERSION};
                TARGETED_DEVICE_FAMILY = "1,2";
            }};
            name = Debug;
        }};
        {target_release} /* Release */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
                CURRENT_PROJECT_VERSION = {self.build_number};
                DEVELOPMENT_TEAM = "{self.team_id}";
                GENERATE_INFOPLIST_FILE = YES;
                INFOPLIST_FILE = "{self.app_name}/Info.plist";
                IPHONEOS_DEPLOYMENT_TARGET = {self.IOS_DEPLOYMENT_TARGET};
                MARKETING_VERSION = {self.version};
                PRODUCT_BUNDLE_IDENTIFIER = "{self.bundle_id}";
                PRODUCT_NAME = "$(TARGET_NAME)";
                SWIFT_EMIT_LOC_STRINGS = YES;
                SWIFT_VERSION = {self.SWIFT_VERSION};
                TARGETED_DEVICE_FAMILY = "1,2";
            }};
            name = Release;
        }};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
        {build_config_list} /* Build configuration list for PBXProject */ = {{
            isa = XCConfigurationList;
            buildConfigurations = ({debug_config}, {release_config});
            defaultConfigurationIsVisible = 0;
            defaultConfigurationName = Release;
        }};
        {target_bcl} /* Build configuration list for PBXNativeTarget */ = {{
            isa = XCConfigurationList;
            buildConfigurations = ({target_debug}, {target_release});
            defaultConfigurationIsVisible = 0;
            defaultConfigurationName = Release;
        }};
/* End XCConfigurationList section */

    }};
    rootObject = {root};
}}
'''

    def _package_swift(self):
        return f'''// swift-tools-version:{self.SWIFT_VERSION}
import PackageDescription

let package = Package(
    name: "{self.app_name}",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "{self.app_name}", targets: ["{self.app_name}"]),
    ],
    targets: [
        .target(name: "{self.app_name}", path: "{self.app_name}"),
        .testTarget(name: "{self.app_name}Tests",
                     dependencies: ["{self.app_name}"],
                     path: "{self.app_name}Tests"),
    ]
)
'''

    def _test_file(self):
        return f'''import XCTest
@testable import {self.app_name}

final class {self.app_name}Tests: XCTestCase {{
    func testRuntimeMath() throws {{
        let runtime = EPLRuntime()
        XCTAssertEqual(runtime.abs(-5), 5.0)
        XCTAssertEqual(runtime.round(3.7), 4.0)
    }}

    func testRuntimeStrings() throws {{
        let runtime = EPLRuntime()
        XCTAssertEqual(runtime.toText(42), "42")
        XCTAssertEqual(runtime.length("hello"), 5)
    }}
}}
'''

    def _ui_test_file(self):
        return f'''import XCTest

final class {self.app_name}UITests: XCTestCase {{
    func testAppLaunches() throws {{
        let app = XCUIApplication()
        app.launch()
    }}
}}
'''

    def _gitignore(self):
        return '''# Xcode
build/
DerivedData/
*.xcuserdata
*.xcworkspace
xcuserdata/
*.moved-aside
*.pbxuser
!default.pbxuser
*.mode1v3
!default.mode1v3
*.mode2v3
!default.mode2v3
*.perspectivev3
!default.perspectivev3

# Swift Package Manager
.build/
Packages/
Package.resolved
.swiftpm/

# CocoaPods
Pods/
Podfile.lock

# OS
.DS_Store
'''

    def _readme(self):
        return f'''# {self.app_name}

iOS application generated from EPL source code using SwiftUI.

## Prerequisites

- macOS 13+ with Xcode 15+
- iOS {self.IOS_DEPLOYMENT_TARGET}+ deployment target
- Apple Developer account (for device deployment)

## Build & Run

### Using Xcode
1. Open `{self.app_name}.xcodeproj` in Xcode
2. Select your target device/simulator
3. Press Cmd+R to build and run

### Using Command Line
```bash
# Build
xcodebuild -project {self.app_name}.xcodeproj -scheme {self.app_name} -sdk iphonesimulator build

# Run tests
xcodebuild -project {self.app_name}.xcodeproj -scheme {self.app_name} -sdk iphonesimulator test

# Archive for distribution
xcodebuild -project {self.app_name}.xcodeproj -scheme {self.app_name} -sdk iphoneos archive
```

## Project Structure

```
{self.app_name}/
    {self.app_name}App.swift    — App entry point
    Views/
        ContentView.swift       — Main UI (generated from EPL)
    EPLRuntime.swift            — EPL standard library bridge
    Assets.xcassets/            — App icons and assets
```
'''


class SwiftUIGenerator:
    """Generates SwiftUI code from EPL AST."""

    def __init__(self, app_name, bundle_id):
        self.app_name = app_name
        self.bundle_id = bundle_id
        self._imports = {'SwiftUI'}
        self._state_vars = []
        self._widgets = []
        self._functions = []
        self._indent = 0

    def generate(self, program) -> str:
        """Generate ContentView.swift from EPL AST."""
        body_lines = []
        for stmt in program.statements:
            lines = self._emit_stmt(stmt)
            if lines:
                body_lines.extend(lines)

        # Build ContentView
        out = []
        for imp in sorted(self._imports):
            out.append(f'import {imp}')
        out.append('')
        out.append('struct ContentView: View {')

        # State variables
        for sv in self._state_vars:
            out.append(f'    @State private var {sv["name"]}: {sv["type"]} = {sv["default"]}')
        if self._state_vars:
            out.append('')

        out.append('    var body: some View {')
        out.append('        NavigationStack {')
        out.append('            ScrollView {')
        out.append('                VStack(spacing: 16) {')

        if self._widgets:
            for w in self._widgets:
                out.append(f'                    {w}')
        elif body_lines:
            for line in body_lines:
                out.append(f'                    {line}')
        else:
            out.append(f'                    Text("Welcome to {self.app_name}")')
            out.append('                        .font(.title)')

        out.append('                }')
        out.append('                .padding()')
        out.append('            }')
        out.append(f'            .navigationTitle("{self.app_name}")')
        out.append('        }')
        out.append('    }')

        # Helper functions
        for fn in self._functions:
            out.append('')
            out.extend(fn)

        out.append('}')
        out.append('')
        out.append('#Preview {')
        out.append('    ContentView()')
        out.append('}')
        out.append('')

        return '\n'.join(out)

    def generate_app(self) -> str:
        """Generate the App entry point."""
        return f'''import SwiftUI

@main
struct {self.app_name}App: App {{
    var body: some Scene {{
        WindowGroup {{
            ContentView()
        }}
    }}
}}
'''

    def generate_runtime(self) -> str:
        """Generate EPLRuntime.swift — standard library bridge."""
        return '''import Foundation

/// EPL Runtime Library for Swift/iOS
class EPLRuntime {
    // MARK: - I/O
    func say(_ value: Any) {
        print(value)
    }

    // MARK: - Type conversion
    func toText(_ value: Any) -> String {
        return String(describing: value)
    }

    func toInteger(_ value: Any) -> Int {
        if let n = value as? Int { return n }
        if let d = value as? Double { return Int(d) }
        if let s = value as? String { return Int(s) ?? 0 }
        return 0
    }

    func toFloat(_ value: Any) -> Double {
        if let d = value as? Double { return d }
        if let n = value as? Int { return Double(n) }
        if let s = value as? String { return Double(s) ?? 0.0 }
        return 0.0
    }

    // MARK: - Math
    func abs(_ n: Double) -> Double { return Swift.abs(n) }
    func round(_ n: Double) -> Double { return Foundation.round(n) }
    func floor(_ n: Double) -> Double { return Foundation.floor(n) }
    func ceil(_ n: Double) -> Double { return Foundation.ceil(n) }
    func sqrt(_ n: Double) -> Double { return Foundation.sqrt(n) }
    func pow(_ base: Double, _ exp: Double) -> Double { return Foundation.pow(base, exp) }
    func min(_ a: Double, _ b: Double) -> Double { return Swift.min(a, b) }
    func max(_ a: Double, _ b: Double) -> Double { return Swift.max(a, b) }

    // MARK: - String operations
    func length(_ s: String) -> Int { return s.count }
    func uppercase(_ s: String) -> String { return s.uppercased() }
    func lowercase(_ s: String) -> String { return s.lowercased() }
    func trim(_ s: String) -> String { return s.trimmingCharacters(in: .whitespacesAndNewlines) }
    func contains(_ s: String, _ sub: String) -> Bool { return s.contains(sub) }
    func replace(_ s: String, _ old: String, _ new: String) -> String { return s.replacingOccurrences(of: old, with: new) }
    func split(_ s: String, _ sep: String) -> [String] { return s.components(separatedBy: sep) }
    func join(_ arr: [String], _ sep: String) -> String { return arr.joined(separator: sep) }
    func substring(_ s: String, _ start: Int, _ end: Int) -> String {
        let startIdx = s.index(s.startIndex, offsetBy: max(0, min(start, s.count)))
        let endIdx = s.index(s.startIndex, offsetBy: max(0, min(end, s.count)))
        return String(s[startIdx..<endIdx])
    }
    func startsWith(_ s: String, _ prefix: String) -> Bool { return s.hasPrefix(prefix) }
    func endsWith(_ s: String, _ suffix: String) -> Bool { return s.hasSuffix(suffix) }

    // MARK: - List operations
    func listLength(_ arr: [Any]) -> Int { return arr.count }
    func listAppend(_ arr: inout [Any], _ item: Any) { arr.append(item) }
    func listRemove(_ arr: inout [Any], _ index: Int) -> Any { return arr.remove(at: index) }
    func listReverse(_ arr: [Any]) -> [Any] { return arr.reversed() }
    func listContains(_ arr: [Any], _ item: Any) -> Bool {
        return arr.contains(where: { String(describing: $0) == String(describing: item) })
    }

    // MARK: - Map operations
    func mapKeys(_ dict: [String: Any]) -> [String] { return Array(dict.keys) }
    func mapValues(_ dict: [String: Any]) -> [Any] { return Array(dict.values) }
    func mapHasKey(_ dict: [String: Any], _ key: String) -> Bool { return dict[key] != nil }
    func mapSize(_ dict: [String: Any]) -> Int { return dict.count }

    // MARK: - JSON
    func toJson(_ value: Any) -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: value),
              let str = String(data: data, encoding: .utf8) else { return "{}" }
        return str
    }

    func parseJson(_ str: String) -> Any {
        guard let data = str.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) else { return [:] }
        return obj
    }

    // MARK: - Date/Time
    func now() -> String {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return fmt.string(from: Date())
    }

    func timestamp() -> Double {
        return Date().timeIntervalSince1970
    }

    // MARK: - File operations (sandboxed)
    func readFile(_ path: String) -> String {
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(path)
        return (try? String(contentsOf: url, encoding: .utf8)) ?? ""
    }

    func writeFile(_ path: String, _ content: String) -> Bool {
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(path)
        do {
            try content.write(to: url, atomically: true, encoding: .utf8)
            return true
        } catch { return false }
    }

    func fileExists(_ path: String) -> Bool {
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(path)
        return FileManager.default.fileExists(atPath: url.path)
    }

    // MARK: - HTTP (async)
    func httpGet(_ url: String) async -> [String: Any] {
        guard let url = URL(string: url) else { return ["error": "Invalid URL"] }
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let body = String(data: data, encoding: .utf8) ?? ""
            return ["status": status, "body": body]
        } catch {
            return ["error": error.localizedDescription]
        }
    }

    func httpPost(_ url: String, _ bodyStr: String) async -> [String: Any] {
        guard let url = URL(string: url) else { return ["error": "Invalid URL"] }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.httpBody = bodyStr.data(using: .utf8)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let body = String(data: data, encoding: .utf8) ?? ""
            return ["status": status, "body": body]
        } catch {
            return ["error": error.localizedDescription]
        }
    }

    // MARK: - Crypto
    func hashSHA256(_ input: String) -> String {
        guard let data = input.data(using: .utf8) else { return "" }
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    // MARK: - Random
    func randomInt(_ min: Int, _ max: Int) -> Int {
        return Int.random(in: min...max)
    }

    func randomFloat() -> Double {
        return Double.random(in: 0.0...1.0)
    }

    // MARK: - UserDefaults (persistent storage)
    func store(_ key: String, _ value: Any) {
        UserDefaults.standard.set(value, forKey: key)
    }

    func retrieve(_ key: String) -> Any? {
        return UserDefaults.standard.object(forKey: key)
    }
}

// SHA256 implementation using CryptoKit when available
import CryptoKit
'''

    def _emit_stmt(self, node):
        """Emit a SwiftUI-compatible representation of an EPL AST node."""
        lines = []

        if isinstance(node, ast.PrintStatement):
            expr = self._expr(node.expression)
            lines.append(f'Text({expr})')

        elif isinstance(node, ast.VarDeclaration):
            swift_type = self._swift_type(node.var_type)
            val = self._expr(node.value)
            self._state_vars.append({
                'name': node.name,
                'type': swift_type,
                'default': val
            })

        elif isinstance(node, ast.FunctionDef):
            fn_lines = []
            fn_lines.append(f'    func {node.name}({self._params(node.params)}) {{')
            for stmt in node.body:
                inner = self._emit_stmt(stmt)
                for l in inner:
                    fn_lines.append(f'        {l}')
            fn_lines.append('    }')
            self._functions.append(fn_lines)

        elif isinstance(node, (ast.WindowCreate,)):
            pass  # Window creation handled by SwiftUI App structure

        elif isinstance(node, (ast.WidgetAdd,)):
            widget_type = getattr(node, 'widget_type', 'label')
            props = getattr(node, 'properties', {})
            widget_code = self._swiftui_widget(widget_type, props)
            if widget_code:
                self._widgets.append(widget_code)

        return lines

    def _swiftui_widget(self, wtype, props):
        """Convert an EPL widget to SwiftUI code."""
        text = props.get('text', props.get('label', '""'))
        if isinstance(text, str) and not text.startswith('"'):
            text = f'"{text}"'

        if wtype in ('label', 'text'):
            return f'Text({text})'
        elif wtype == 'button':
            action = props.get('action', '{}')
            return f'Button({text}) {{ {action} }}'
        elif wtype == 'input':
            placeholder = props.get('placeholder', '"Enter text"')
            return f'TextField({placeholder}, text: .constant(""))'
        elif wtype == 'textarea':
            return f'TextEditor(text: .constant(""))'
        elif wtype == 'checkbox':
            return f'Toggle({text}, isOn: .constant(false))'
        elif wtype == 'slider':
            return f'Slider(value: .constant(0.5))'
        elif wtype == 'image':
            src = props.get('source', '"photo"')
            return f'Image(systemName: {src}).resizable().aspectRatio(contentMode: .fit)'
        elif wtype == 'dropdown':
            return f'Picker({text}, selection: .constant(0)) {{ Text("Option 1").tag(0) }}'
        elif wtype == 'progress':
            return 'ProgressView()'
        elif wtype == 'separator':
            return 'Divider()'
        return f'Text({text})'

    def _swift_type(self, type_str):
        """Map EPL type to Swift type."""
        if type_str is None:
            return 'String'
        ts = str(type_str).lower()
        mapping = {
            'integer': 'Int', 'int': 'Int',
            'decimal': 'Double', 'float': 'Double', 'number': 'Double',
            'text': 'String', 'string': 'String',
            'boolean': 'Bool', 'bool': 'Bool',
            'list': '[Any]', 'array': '[Any]',
            'map': '[String: Any]', 'dictionary': '[String: Any]',
        }
        return mapping.get(ts, 'String')

    def _expr(self, node):
        """Convert EPL expression to Swift literal."""
        if node is None:
            return '""'
        if isinstance(node, ast.Literal):
            v = node.value
            if isinstance(v, str):
                escaped = v.replace('\\', '\\\\').replace('"', '\\"')
                return f'"{escaped}"'
            if isinstance(v, bool):
                return 'true' if v else 'false'
            return str(v)
        if isinstance(node, ast.Identifier):
            return node.name
        if isinstance(node, ast.BinaryOp):
            return f'{self._expr(node.left)} {self._swift_op(node.operator)} {self._expr(node.right)}'
        if isinstance(node, ast.FunctionCall):
            name = node.name if isinstance(node.name, str) else node.name.name
            args_str = ', '.join(self._expr(a) for a in (node.arguments or []))
            return f'{name}({args_str})'
        return str(node)

    def _swift_op(self, op):
        mapping = {
            'plus': '+', 'minus': '-', 'times': '*', 'divided by': '/',
            'is equal to': '==', 'is not equal to': '!=',
            'is greater than': '>', 'is less than': '<',
            'and': '&&', 'or': '||',
        }
        return mapping.get(op, op)

    def _params(self, params):
        parts = []
        for p in params:
            name = p[0]
            ptype = self._swift_type(p[1] if len(p) > 1 else None)
            parts.append(f'_ {name}: {ptype}')
        return ', '.join(parts)


def generate_ios_project(program, output_dir, app_name="EPLApp",
                          bundle_id="com.epl.app", team_id=None):
    """Convenience function to generate an iOS project from EPL AST."""
    gen = IOSProjectGenerator(app_name=app_name, bundle_id=bundle_id,
                               team_id=team_id)
    return gen.generate(program, output_dir)
