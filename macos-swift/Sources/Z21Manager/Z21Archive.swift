import Foundation

final class Z21ArchiveDocument {
    let sourceURL: URL
    let workingDirectory: URL
    let databaseURL: URL

    init(url: URL) throws {
        sourceURL = url
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("Z21Manager-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        workingDirectory = root
        do {
            try Self.run("/usr/bin/ditto", ["-x", "-k", url.path, root.path])
            let databases = try FileManager.default.subpathsOfDirectory(atPath: root.path)
                .filter { $0.lowercased().hasSuffix("loco.sqlite") || $0.lowercased().hasSuffix(".sqlite") }
            guard let relative = databases.sorted(by: { $0.count < $1.count }).first else {
                throw Z21Error.invalidArchive("The archive contains no SQLite database.")
            }
            let candidate = root.appendingPathComponent(relative)
            guard let safeDatabase = Self.containedRegularFile(candidate, in: root) else {
                throw Z21Error.invalidArchive("The archive database path is not safe.")
            }
            databaseURL = safeDatabase
        } catch {
            try? FileManager.default.removeItem(at: root)
            throw error
        }
    }

    deinit { try? FileManager.default.removeItem(at: workingDirectory) }

    func write(to destination: URL? = nil) throws {
        let target = destination ?? sourceURL
        let parent = target.deletingLastPathComponent()
        let temporary = parent.appendingPathComponent(".\(target.lastPathComponent).\(UUID().uuidString).tmp")
        try Self.run("/usr/bin/ditto", ["-c", "-k", "--sequesterRsrc", workingDirectory.path, temporary.path])
        do {
            if FileManager.default.fileExists(atPath: target.path) {
                _ = try FileManager.default.replaceItemAt(target, withItemAt: temporary)
            } else {
                try FileManager.default.moveItem(at: temporary, to: target)
            }
        } catch {
            try? FileManager.default.removeItem(at: temporary)
            throw error
        }
    }

    func addImage(from source: URL) throws -> String {
        let ext = source.pathExtension.isEmpty ? "png" : source.pathExtension.lowercased()
        let filename = UUID().uuidString.replacingOccurrences(of: "-", with: "").uppercased() + "." + ext
        let target = workingDirectory.appendingPathComponent(filename)
        try FileManager.default.copyItem(at: source, to: target)
        return filename
    }

    func imageURL(named name: String) -> URL? {
        Self.imageURL(in: workingDirectory, named: name)
    }

    static func imageURL(in workingDirectory: URL, named name: String) -> URL? {
        guard !name.isEmpty else { return nil }
        let direct = workingDirectory.appendingPathComponent(name)
        if let safeDirect = Self.containedRegularFile(direct, in: workingDirectory) { return safeDirect }
        let requestedName = URL(fileURLWithPath: name).lastPathComponent
        let match = try? FileManager.default.subpathsOfDirectory(atPath: workingDirectory.path)
            .first(where: { URL(fileURLWithPath: $0).lastPathComponent == requestedName })
        guard let match else { return nil }
        return Self.containedRegularFile(workingDirectory.appendingPathComponent(match), in: workingDirectory)
    }

    private static func containedRegularFile(_ candidate: URL, in root: URL) -> URL? {
        let safeRoot = root.standardizedFileURL.resolvingSymlinksInPath()
        let standardizedCandidate = candidate.standardizedFileURL
        let resolvedCandidate = standardizedCandidate.resolvingSymlinksInPath()
        let rootPrefix = safeRoot.path.hasSuffix("/") ? safeRoot.path : safeRoot.path + "/"
        guard resolvedCandidate.path.hasPrefix(rootPrefix) else { return nil }
        guard let values = try? standardizedCandidate.resourceValues(
            forKeys: [.isRegularFileKey, .isSymbolicLinkKey]
        ), values.isRegularFile == true, values.isSymbolicLink != true else { return nil }
        return standardizedCandidate
    }

    static func run(_ executable: String, _ arguments: [String], currentDirectory: URL? = nil) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.currentDirectoryURL = currentDirectory
        let stderr = Pipe()
        process.standardError = stderr
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            let data = stderr.fileHandleForReading.readDataToEndOfFile()
            let message = String(data: data, encoding: .utf8) ?? "Unknown command error"
            throw Z21Error.externalTool(message.trimmingCharacters(in: .whitespacesAndNewlines))
        }
    }
}
