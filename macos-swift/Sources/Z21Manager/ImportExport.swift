import AppKit
import Foundation

enum IconCatalog {
    static func directory() -> URL? {
        var candidates: [URL] = []
        let current = URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
        var cursor = current
        for _ in 0..<5 {
            candidates.append(cursor.appendingPathComponent("icons", isDirectory: true))
            cursor.deleteLastPathComponent()
        }
        candidates.append(Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/icons", isDirectory: true))
        return candidates.first { FileManager.default.fileExists(atPath: $0.path) }
    }

    static func icons() -> [String] {
        guard let directory = directory(), let names = try? FileManager.default.contentsOfDirectory(atPath: directory.path) else { return ["neutral"] }
        return names.filter { $0.lowercased().hasSuffix(".png") }.map {
            URL(fileURLWithPath: $0).deletingPathExtension().lastPathComponent
                .replacingOccurrences(of: "_Normal", with: "")
        }.sorted()
    }

    static func url(named name: String) -> URL? {
        guard let directory = directory() else { return nil }
        let candidates = [name, "\(name).png", "\(name)_Normal.png"]
        return candidates.map { directory.appendingPathComponent($0) }
            .first { FileManager.default.fileExists(atPath: $0.path) }
    }
}

enum ImportExportService {
    static func importLocomotive(from url: URL, into document: Z21ArchiveDocument,
                                 existing: [Locomotive]) throws -> Locomotive {
        let importedDocument = try Z21ArchiveDocument(url: url)
        let imported = try Z21Repository(databaseURL: importedDocument.databaseURL).loadLocomotives()
        guard var locomotive = imported.first else { throw Z21Error.invalidArchive("No locomotive was found in the .z21loco file.") }
        locomotive.id = UUID()
        locomotive.vehicleID = nil
        locomotive.isNewImport = true
        if let image = importedDocument.imageURL(named: locomotive.imageName) {
            locomotive.imageName = try document.addImage(from: image)
        }
        try LocomotiveValidator.validate(locomotive, among: existing)
        return locomotive
    }

    static func exportLocomotive(_ locomotive: Locomotive, from sourceDocument: Z21ArchiveDocument,
                                 to destination: URL) throws {
        let tempArchive = FileManager.default.temporaryDirectory
            .appendingPathComponent("Z21-export-\(UUID().uuidString).z21loco")
        defer { try? FileManager.default.removeItem(at: tempArchive) }
        try sourceDocument.write(to: tempArchive)
        let document = try Z21ArchiveDocument(url: tempArchive)
        var clone = locomotive
        clone.id = UUID()
        var only = [clone]
        try Z21Repository(databaseURL: document.databaseURL).save(&only)
        try document.write(to: destination)
    }

    static func airDropExportURL(filename: String) throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("Z21LocomotiveManager", isDirectory: true)
            .appendingPathComponent("AirDrop", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory.appendingPathComponent(filename)
    }

    @MainActor
    static func shareViaAirDrop(_ url: URL) throws {
        try AirDropShareManager.share(url)
    }
}

enum JSONImporter {
    static func applyLocomotiveJSON(_ data: Data, to locomotive: inout Locomotive) throws {
        let root = try JSONSerialization.jsonObject(with: data)
        let object: [String: Any]?
        if let dictionary = root as? [String: Any] {
            if dictionary["address"] != nil || dictionary["name"] != nil { object = dictionary }
            else { object = (dictionary["locomotives"] as? [[String: Any]])?.first }
        } else { object = (root as? [[String: Any]])?.first }
        guard let object else { throw Z21Error.validation("No locomotive object was found in the JSON file.") }
        func string(_ keys: String...) -> String? {
            for key in keys { if let value = object[key], !(value is NSNull) { return String(describing: value) } }
            return nil
        }
        if let value = string("name"), locomotive.name.isEmpty || locomotive.name.hasPrefix("New Locomotive ") { locomotive.name = value }
        if let value = string("address"), let number = Int(value), locomotive.address == 0 { locomotive.address = number }
        if let value = string("Maxspeed", "maxSpeed", "speed", "maxspeed"), locomotive.speed == 0,
           let number = Double(value.components(separatedBy: CharacterSet.decimalDigits.inverted).joined()), number <= 999 {
            locomotive.speed = Int(number)
            if value.lowercased().contains("mph") { locomotive.speedDisplay = 2 }
        }
        if let value = string("fullName", "full_name"), locomotive.fullName.isEmpty { locomotive.fullName = value }
        if let value = string("railway") { locomotive.railway = value }
        if let value = string("articleNumber", "article_number"), locomotive.articleNumber.isEmpty { locomotive.articleNumber = value }
        if let value = string("decoderType", "decoder_type") { locomotive.decoderType = value }
        if let value = string("buildYear", "build_year"), locomotive.buildYear.isEmpty { locomotive.buildYear = value }
        if let value = string("modelBufferLength", "model_buffer_length"), locomotive.modelBufferLength.isEmpty { locomotive.modelBufferLength = value }
        if let value = string("serviceWeight", "service_weight"), locomotive.serviceWeight.isEmpty { locomotive.serviceWeight = value }
        if let value = string("modelWeight", "model_weight"), locomotive.modelWeight.isEmpty { locomotive.modelWeight = value }
        if let value = string("minimumRadius", "rmin"), locomotive.rmin.isEmpty { locomotive.rmin = value }
        if let value = string("ipAddress", "ip"), locomotive.ip.isEmpty { locomotive.ip = value }
        if let value = string("driversCab", "drivers_cab"), locomotive.driversCab.isEmpty { locomotive.driversCab = value }
        if let value = string("description"), locomotive.description.isEmpty { locomotive.description = value }
    }

    static func applyFunctionsJSON(_ data: Data, to locomotive: inout Locomotive,
                                   availableIcons: [String]) throws {
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let functions = root["functions"] as? [[String: Any]], !functions.isEmpty else {
            throw Z21Error.validation("The JSON file has no non-empty functions array.")
        }
        for item in functions {
            let raw = String(describing: item["number"] ?? "").uppercased().replacingOccurrences(of: "F", with: "")
            guard let number = Int(raw), (0...127).contains(number) else { continue }
            let name = (item["name"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "Function \(number)"
            let suppliedIcon = (item["icon"] as? String) ?? ""
            let icon = availableIcons.first(where: { $0.caseInsensitiveCompare(suppliedIcon) == .orderedSame })
                ?? FunctionMatcher.match(name, available: availableIcons)
            let shortcut = ((item["shortcut"] as? String)?.isEmpty == false ? item["shortcut"] as! String : FunctionMatcher.shortcut(description: name, icon: icon))
            let type = ["switch": 0, "push": 1, "time": 2][(item["type"] as? String ?? "switch").lowercased()] ?? 0
            let newValue = FunctionInfo(number: number, imageName: icon, shortcut: shortcut,
                                        position: locomotive.functions.count, buttonType: type)
            if let index = locomotive.functions.firstIndex(where: { $0.number == number }) { locomotive.functions[index] = newValue }
            else { locomotive.functions.append(newValue) }
        }
        normalizePositions(&locomotive.functions)
    }
}

func normalizePositions(_ functions: inout [FunctionInfo]) {
    functions.sort { $0.number < $1.number }
    for index in functions.indices { functions[index].position = index }
}
