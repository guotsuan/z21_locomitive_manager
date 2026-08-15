import Foundation

struct OpenedDocument: Sendable {
    let session: DocumentSession
    let locomotives: [Locomotive]
}

actor DocumentSession {
    nonisolated let fileURL: URL
    nonisolated let workingDirectory: URL

    private let document: Z21ArchiveDocument
    private let repository: Z21Repository

    private init(fileURL: URL, document: Z21ArchiveDocument, repository: Z21Repository) {
        self.fileURL = fileURL
        self.workingDirectory = document.workingDirectory
        self.document = document
        self.repository = repository
    }

    static func open(_ url: URL) async throws -> OpenedDocument {
        try await Task.detached(priority: .userInitiated) {
            let document = try Z21ArchiveDocument(url: url)
            let repository = try Z21Repository(databaseURL: document.databaseURL)
            let locomotives = try repository.loadLocomotives()
            let session = DocumentSession(fileURL: url, document: document, repository: repository)
            return OpenedDocument(session: session, locomotives: locomotives)
        }.value
    }

    func save(_ values: [Locomotive]) throws -> [Locomotive] {
        var saved = values
        try repository.save(&saved)
        try document.write()
        return saved
    }

    func importLocomotive(from url: URL, existing: [Locomotive]) throws -> Locomotive {
        try ImportExportService.importLocomotive(from: url, into: document, existing: existing)
    }

    func exportLocomotive(_ locomotive: Locomotive, to destination: URL) throws {
        try ImportExportService.exportLocomotive(locomotive, from: document, to: destination)
    }

    func addImage(from source: URL) throws -> String {
        try document.addImage(from: source)
    }

    nonisolated func imageURL(named name: String) -> URL? {
        Z21ArchiveDocument.imageURL(in: workingDirectory, named: name)
    }
}
