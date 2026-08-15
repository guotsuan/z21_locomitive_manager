import AppKit
import Foundation

@MainActor
enum AirDropShareManager {
    private static var activeShares: [UUID: AirDropShareCoordinator] = [:]

    static func share(_ url: URL) throws {
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw Z21Error.service("The AirDrop export file could not be created.")
        }
        guard let service = NSSharingService(named: .sendViaAirDrop) else {
            throw Z21Error.service("AirDrop is not available on this Mac.")
        }
        guard service.canPerform(withItems: [url]) else {
            throw Z21Error.service("AirDrop cannot share this .z21loco file.")
        }

        let id = UUID()
        let coordinator = AirDropShareCoordinator(fileURL: url) {
            activeShares[id] = nil
        }
        activeShares[id] = coordinator
        coordinator.start(service: service)
    }

    static func cleanupTemporaryExport(at fileURL: URL) {
        let directory = fileURL.deletingLastPathComponent()
        guard directory.deletingLastPathComponent().lastPathComponent == "AirDrop" else { return }
        try? FileManager.default.removeItem(at: directory)
    }
}

@MainActor
private final class AirDropShareCoordinator: NSObject, NSSharingServiceDelegate {
    private let fileURL: URL
    private let onFinish: () -> Void
    private var service: NSSharingService?
    private var timeoutTask: Task<Void, Never>?
    private var isFinished = false

    init(fileURL: URL, onFinish: @escaping () -> Void) {
        self.fileURL = fileURL
        self.onFinish = onFinish
    }

    func start(service: NSSharingService) {
        self.service = service
        service.delegate = self
        service.perform(withItems: [fileURL])
        timeoutTask = Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 10 * 60 * 1_000_000_000)
            self?.finish()
        }
    }

    func sharingService(_ sharingService: NSSharingService, didShareItems items: [Any]) {
        finish()
    }

    func sharingService(_ sharingService: NSSharingService, didFailToShareItems items: [Any], error: Error) {
        finish()
    }

    private func finish() {
        guard !isFinished else { return }
        isFinished = true
        timeoutTask?.cancel()
        timeoutTask = nil
        service?.delegate = nil
        service = nil
        AirDropShareManager.cleanupTemporaryExport(at: fileURL)
        onFinish()
    }
}
