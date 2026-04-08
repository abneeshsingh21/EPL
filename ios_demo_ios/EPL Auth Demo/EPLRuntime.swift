import Foundation

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
