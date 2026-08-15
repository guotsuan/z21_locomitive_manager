import Foundation
import Darwin

struct FunctionInfo: Identifiable, Codable, Hashable, Sendable {
    var id: Int { number }
    var number: Int = 0
    var imageName: String = "neutral"
    var shortcut: String = ""
    var position: Int = 0
    var time: Double? = nil
    var buttonType: Int = 0
    var isActive: Bool = true

    var buttonTypeName: String {
        [0: "Switch", 1: "Push button", 2: "Timed"][buttonType] ?? "Type \(buttonType)"
    }
}

struct Locomotive: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var vehicleID: Int64?
    var isNewImport = false
    var address = 0
    var name = ""
    var speed = 0
    var direction = true
    var imageName = ""
    var fullName = ""
    var railway = ""
    var description = ""
    var articleNumber = ""
    var decoderType = ""
    var buildYear = ""
    var bufferLength = ""
    var modelBufferLength = ""
    var serviceWeight = ""
    var modelWeight = ""
    var rmin = ""
    var ip = ""
    var driversCab = ""
    var active = true
    var speedDisplay = 0
    var categories: [String] = []
    var crane = false
    var inStockSince = ""
    var regulationStep = 0
    var railVehicleType = 0
    var functions: [FunctionInfo] = []

    static func blank(address: Int) -> Locomotive {
        var value = Locomotive()
        value.address = address
        value.name = "New Locomotive \(address)"
        value.isNewImport = true
        return value
    }
}

enum Z21Error: LocalizedError {
    case invalidArchive(String)
    case database(String)
    case validation(String)
    case externalTool(String)
    case service(String)

    var errorDescription: String? {
        switch self {
        case .invalidArchive(let text), .database(let text),
             .validation(let text), .externalTool(let text), .service(let text):
            return text
        }
    }
}

enum LocomotiveValidator {
    static let defaultCategories = ["Electrical", "Steam", "Diesel", "Train Bus"]

    static func validate(_ locomotive: Locomotive, among all: [Locomotive]) throws {
        let name = locomotive.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else { throw Z21Error.validation("Name is required.") }
        guard (1...9999).contains(locomotive.address) else {
            throw Z21Error.validation("Address must be between 1 and 9999.")
        }
        guard (0...999).contains(locomotive.speed) else {
            throw Z21Error.validation("Maximum speed must be between 0 and 999.")
        }
        if all.contains(where: { $0.id != locomotive.id && $0.address == locomotive.address }) {
            throw Z21Error.validation("Another locomotive already uses address \(locomotive.address).")
        }
        if !locomotive.buildYear.isEmpty,
           (locomotive.buildYear.range(of: #"^\d{4}$"#, options: .regularExpression) == nil ||
            Int(locomotive.buildYear) == nil || !(1800...2100).contains(Int(locomotive.buildYear)!)) {
            throw Z21Error.validation("Build year must be 1800–2100 or empty.")
        }
        if !locomotive.ip.isEmpty, !validIPAddress(locomotive.ip) {
                throw Z21Error.validation("IP address is not valid.")
        }
        if !locomotive.inStockSince.isEmpty,
           locomotive.inStockSince.range(of: #"^\d{4}(?:-\d{2}(?:-\d{2})?)?$"#, options: .regularExpression) == nil {
            throw Z21Error.validation("In-stock date must use YYYY, YYYY-MM, or YYYY-MM-DD.")
        }
        let normalized = locomotive.categories.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        guard normalized.allSatisfy({ category in
            defaultCategories.contains { $0.caseInsensitiveCompare(category) == .orderedSame } ||
                category.range(of: #"^[A-Z][A-Za-z0-9]*(?:[ -][A-Z0-9][A-Za-z0-9]*){0,3}$"#, options: .regularExpression) != nil
        }) else {
            throw Z21Error.validation("Choose a standard category or use a short English Title Case custom category.")
        }
        let numbers = locomotive.functions.map(\.number)
        guard Set(numbers).count == numbers.count, numbers.allSatisfy({ (0...127).contains($0) }) else {
            throw Z21Error.validation("Function numbers must be unique and between F0 and F127.")
        }
    }

    static func normalizeCategories(_ values: [String]) -> [String] {
        var seen = Set<String>()
        return values.compactMap { raw in
            let value = raw.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            guard !value.isEmpty else { return nil }
            let canonical = defaultCategories.first { $0.caseInsensitiveCompare(value) == .orderedSame } ?? value
            return seen.insert(canonical.lowercased()).inserted ? canonical : nil
        }
    }
}

private func validIPAddress(_ value: String) -> Bool {
    var ipv4 = in_addr()
    var ipv6 = in6_addr()
    return value.withCString {
        inet_pton(AF_INET, $0, &ipv4) == 1 || inet_pton(AF_INET6, $0, &ipv6) == 1
    }
}
