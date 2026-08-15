import Foundation
import Security

enum DeepSeekKeychain {
    private static let service = "org.z21-locomotive-manager.deepseek"
    private static let account = "api-key"

    static func get() throws -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data,
              let key = String(data: data, encoding: .utf8) else {
            throw Z21Error.service("Unable to read the DeepSeek key from Keychain (\(status)).")
        }
        return key
    }

    static func set(_ key: String) throws {
        let cleaned = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { throw Z21Error.validation("API key cannot be empty.") }
        try delete(ignoreMissing: true)
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecValueData: Data(cleaned.utf8),
            kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlock
        ]
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw Z21Error.service("Unable to save the DeepSeek key to Keychain (\(status)).")
        }
    }

    static func delete(ignoreMissing: Bool = false) throws {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || (ignoreMissing && status == errSecItemNotFound) else {
            throw Z21Error.service("Unable to remove the DeepSeek key from Keychain (\(status)).")
        }
    }
}
