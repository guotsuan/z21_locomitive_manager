import AppKit
import Combine
import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var locomotives: [Locomotive] = []
    @Published var selection: UUID?
    @Published var searchText = ""
    @Published var appStatus = AppStatus.information("Open a .z21 file to begin")
    @Published var errorMessage: String?
    @Published var isBusy = false
    @Published var isDirty = false
    @Published var fieldProposals: [FieldProposal] = []
    @Published var functionProposals: [FunctionProposal] = []
    @Published var ocrText = ""
    @Published var importReviewSession: ImportReviewSession?
    @Published var pendingFieldChanges: [ImportFieldChange] = []
    @Published var pendingFunctionChanges: [FunctionInfo] = []
    @Published var showingSettings = false
    @Published var cropSourceURL: URL?

    private(set) var fileURL: URL?
    private var documentSession: DocumentSession?
    private var editRevision: UInt64 = 0
    private let continuityCamera = ContinuityCameraCapture()
    private let ocrAIService = OCRAIService()
    let importCoordinator = ImportCoordinator()

    var selectedIndex: Int? { selection.flatMap { id in locomotives.firstIndex { $0.id == id } } }
    var selected: Locomotive? { selectedIndex.map { locomotives[$0] } }
    var importTarget: Locomotive? { importTargetIndex.map { locomotives[$0] } }
    var filteredLocomotives: [Locomotive] {
        guard !searchText.isEmpty else { return locomotives }
        return locomotives.filter { $0.name.localizedCaseInsensitiveContains(searchText) || String($0.address).contains(searchText) }
    }
    var availableIcons: [String] { IconCatalog.icons() }
    func open(_ url: URL) {
        requestAbandonChanges { [weak self] proceed in
            guard proceed else { return }
            self?.openConfirmed(url)
        }
    }

    private func openConfirmed(_ url: URL) {
        guard !isBusy else {
            present(Z21Error.validation("Wait for the current operation to finish before opening another archive."))
            return
        }
        isBusy = true
        appStatus = .working("Opening \(url.lastPathComponent)…")
        Task {
            do {
                let opened = try await DocumentSession.open(url)
                documentSession = opened.session
                fileURL = url
                locomotives = opened.locomotives
                selection = opened.locomotives.first?.id
                editRevision = 0
                isDirty = false
                appStatus = .success("Loaded \(opened.locomotives.count) locomotives from \(url.lastPathComponent)")
                NSDocumentController.shared.noteNewRecentDocumentURL(url)
            } catch { present(error) }
            isBusy = false
        }
    }

    func openPanel() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.init(filenameExtension: "z21")!]
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { open(url) }
    }

    func save() {
        save(completion: nil)
    }

    func save(completion: ((Bool) -> Void)?) {
        guard !isBusy else {
            present(Z21Error.validation("Wait for the current operation to finish before saving."))
            completion?(false)
            return
        }
        guard let documentSession else {
            present(Z21Error.validation("No Z21 file is open."))
            completion?(false)
            return
        }
        var snapshot = locomotives
        do {
            for index in snapshot.indices {
                snapshot[index].categories = LocomotiveValidator.normalizeCategories(snapshot[index].categories)
            }
            for locomotive in snapshot { try LocomotiveValidator.validate(locomotive, among: snapshot) }
        } catch {
            present(error)
            completion?(false)
            return
        }

        let savingRevision = editRevision
        isBusy = true
        appStatus = .working("Saving \(snapshot.count) locomotives…")
        Task {
            do {
                let saved = try await documentSession.save(snapshot)
                mergePersistentIdentity(from: saved)
                if editRevision == savingRevision {
                    locomotives = saved
                    isDirty = false
                }
                appStatus = .success("Saved \(saved.count) locomotives")
                isBusy = false
                completion?(true)
            } catch {
                present(error)
                isBusy = false
                completion?(false)
            }
        }
    }

    func markDirty() {
        editRevision &+= 1
        isDirty = true
    }

    private func mergePersistentIdentity(from saved: [Locomotive]) {
        let identities = Dictionary(uniqueKeysWithValues: saved.map { ($0.id, ($0.vehicleID, $0.isNewImport)) })
        for index in locomotives.indices {
            guard let identity = identities[locomotives[index].id] else { continue }
            locomotives[index].vehicleID = identity.0
            locomotives[index].isNewImport = identity.1
        }
    }

    func addLocomotive() {
        let used = Set(locomotives.map(\.address))
        guard let address = (1...9999).first(where: { !used.contains($0) }) else { return }
        let locomotive = Locomotive.blank(address: address)
        locomotives.append(locomotive)
        selection = locomotive.id
        markDirty()
        appStatus = .warning("Created locomotive at address \(address)")
    }

    func deleteSelected() {
        guard let index = selectedIndex else { return }
        locomotives.remove(at: index)
        selection = locomotives.indices.contains(index) ? locomotives[index].id : locomotives.last?.id
        markDirty()
        appStatus = .warning("Locomotive removed; click Save to persist")
    }

    func importLocomotive() {
        guard let documentSession, !isBusy else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.init(filenameExtension: "z21loco")!]
        if panel.runModal() == .OK, let url = panel.url {
            let existing = locomotives
            isBusy = true
            appStatus = .working("Importing \(url.lastPathComponent)…")
            Task {
                do {
                    let value = try await documentSession.importLocomotive(from: url, existing: existing)
                    locomotives.append(value)
                    selection = value.id
                    markDirty()
                    appStatus = .warning("Imported \(value.name); click Save to persist")
                } catch { present(error) }
                isBusy = false
            }
        }
    }

    func exportSelected(airDrop: Bool = false) {
        guard let locomotive = selected, let documentSession, !isBusy else { return }
        if airDrop {
            do {
                let filename = "\(safeFilename(locomotive.name)).z21loco"
                let target = try ImportExportService.airDropExportURL(filename: filename)
                isBusy = true
                appStatus = .working("Preparing \(filename)…")
                Task {
                    do {
                        try await documentSession.exportLocomotive(locomotive, to: target)
                        try ImportExportService.shareViaAirDrop(target)
                        appStatus = .information("Choose an AirDrop recipient for \(filename)")
                    } catch {
                        AirDropShareManager.cleanupTemporaryExport(at: target)
                        present(error)
                    }
                    isBusy = false
                }
            } catch {
                present(error)
            }
            return
        }

        let panel = NSSavePanel()
        panel.allowedContentTypes = [.init(filenameExtension: "z21loco")!]
        panel.nameFieldStringValue = "\(safeFilename(locomotive.name)).z21loco"
        if panel.runModal() == .OK, let target = panel.url {
            isBusy = true
            appStatus = .working("Exporting \(locomotive.name)…")
            Task {
                do {
                    try await documentSession.exportLocomotive(locomotive, to: target)
                    appStatus = .success("Exported \(locomotive.name)")
                } catch { present(error) }
                isBusy = false
            }
        }
    }

    func importLocomotiveJSON() { chooseJSON(functionsOnly: false) }
    func importFunctionsJSON() { chooseJSON(functionsOnly: true) }

    func chooseDocumentForOCR(functionTable: Bool = false) {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.pdf, .png, .jpeg, .tiff, .heic]
        if panel.runModal() == .OK, let url = panel.url { recognize(url, functionTable: functionTable) }
    }

    func captureFromIPhone(functionTable: Bool = false) {
        let started = continuityCamera.capture { [weak self] url in
            guard let self else { return }
            guard let url else {
                self.appStatus = .failure("The iPhone capture could not be received")
                return
            }
            self.recognize(url, functionTable: functionTable, deleteSourceWhenFinished: true)
        }
        if started {
            let target = functionTable ? "the function table" : "the manual"
            let action = "choose Take Photo or Scan Documents for \(target)"
            appStatus = .information("Choose your iPhone or iPad, then \(action)")
        } else {
            appStatus = .failure("No active window is available for Continuity Camera")
        }
    }

    func importLocomotiveImage() {
        guard selectedIndex != nil, documentSession != nil else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.png, .jpeg, .tiff, .heic]
        if panel.runModal() == .OK, let url = panel.url {
            cropSourceURL = url
        }
    }

    func applyCroppedImage(_ source: URL, rect: CGRect) {
        guard let targetID = selection, let documentSession, !isBusy else { return }
        isBusy = true
        appStatus = .working("Processing locomotive image…")
        Task {
            var cropped: URL?
            do {
                let result = try await Task.detached(priority: .userInitiated) {
                    try ImageCropper.crop(source, normalized: rect)
                }.value
                cropped = result
                let imageName = try await documentSession.addImage(from: result)
                guard let index = locomotives.firstIndex(where: { $0.id == targetID }) else {
                    throw Z21Error.validation("The locomotive selected for this image is no longer available.")
                }
                locomotives[index].imageName = imageName
                cropSourceURL = nil
                markDirty()
                appStatus = .warning("Updated locomotive image; click Save to persist")
            } catch { present(error) }
            if let cropped { try? FileManager.default.removeItem(at: cropped) }
            isBusy = false
        }
    }

    func recognize(_ url: URL, functionTable: Bool, deleteSourceWhenFinished: Bool = false) {
        guard let targetID = selection, let target = selected else { return }
        let targetName = target.name
        isBusy = true
        appStatus = .working("Recognizing text with Apple Vision…")
        Task {
            defer {
                if deleteSourceWhenFinished { try? FileManager.default.removeItem(at: url) }
            }
            do {
                let result = try await ocrAIService.recognize(url)
                let proposals = functionTable
                    ? try await ocrAIService.extractFunctions(result: result, availableIcons: availableIcons)
                    : []
                guard locomotives.contains(where: { $0.id == targetID }) else {
                    throw Z21Error.validation("The locomotive selected for this import is no longer available.")
                }
                ocrText = result.text
                if functionTable {
                    functionProposals = proposals
                    importReviewSession = ImportReviewSession(source: url.lastPathComponent,
                                                              targetID: targetID,
                                                              target: targetName,
                                                              stage: .functionChanges)
                } else {
                    importReviewSession = ImportReviewSession(source: url.lastPathComponent,
                                                              targetID: targetID,
                                                              target: targetName,
                                                              stage: .ocrText)
                }
                appStatus = .success("Recognized \(result.pages.count) page(s)")
            } catch { present(error) }
            isBusy = false
        }
    }

    func analyzeFields() {
        guard let session = importReviewSession, let locomotive = importTarget else { return }
        let sessionID = session.id
        let recognizedText = ocrText
        appStatus = .working("Analyzing recognized details with DeepSeek…")
        isBusy = true
        Task {
            do {
                let proposals = try await ocrAIService.extractFields(text: recognizedText, existing: locomotive)
                guard importReviewSession?.id == sessionID, importTarget != nil else {
                    isBusy = false
                    return
                }
                fieldProposals = proposals
                importReviewSession?.stage = .fieldChanges
                appStatus = .information("Review \(fieldProposals.count) proposed detail changes")
            } catch { present(error) }
            isBusy = false
        }
    }

    func applyFields(_ selectedProposals: Set<UUID>) {
        guard let index = importTargetIndex else {
            present(Z21Error.validation("The locomotive selected for this import is no longer available."))
            return
        }
        for proposal in fieldProposals where selectedProposals.contains(proposal.id) {
            apply(proposal, to: &locomotives[index])
        }
        finishImport("Applied \(selectedProposals.count) detail changes")
        if !selectedProposals.isEmpty { markDirty() }
    }

    func applyFunctions(_ selectedNumbers: Set<Int>) {
        guard let index = importTargetIndex else {
            present(Z21Error.validation("The locomotive selected for this import is no longer available."))
            return
        }
        for proposal in functionProposals where selectedNumbers.contains(proposal.number) {
            let info = FunctionInfo(number: proposal.number, imageName: proposal.iconName,
                                    shortcut: FunctionMatcher.shortcut(description: proposal.name, icon: proposal.iconName),
                                    position: proposal.number, buttonType: proposal.buttonType)
            if let existing = locomotives[index].functions.firstIndex(where: { $0.number == proposal.number }) {
                locomotives[index].functions[existing] = info
            } else { locomotives[index].functions.append(info) }
        }
        normalizePositions(&locomotives[index].functions)
        finishImport("Applied \(selectedNumbers.count) function changes")
        if !selectedNumbers.isEmpty { markDirty() }
    }

    func imageURL(for locomotive: Locomotive) -> URL? { documentSession?.imageURL(named: locomotive.imageName) }

    private func chooseJSON(functionsOnly: Bool) {
        guard let targetID = selection else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json]
        if panel.runModal() == .OK, let url = panel.url {
            perform {
                guard let index = locomotives.firstIndex(where: { $0.id == targetID }) else {
                    throw Z21Error.validation("The locomotive selected for this import is no longer available.")
                }
                let original = locomotives[index]
                var proposed = original
                let data = try Data(contentsOf: url)
                if functionsOnly {
                    try JSONImporter.applyFunctionsJSON(data, to: &proposed, availableIcons: availableIcons)
                    pendingFunctionChanges = proposed.functions.filter { value in
                        original.functions.first(where: { $0.number == value.number }) != value
                    }
                    guard !pendingFunctionChanges.isEmpty else {
                        throw Z21Error.validation("The JSON file does not contain any function changes.")
                    }
                } else {
                    try JSONImporter.applyLocomotiveJSON(data, to: &proposed)
                    pendingFieldChanges = importCoordinator.fieldChanges(from: original, to: proposed)
                    guard !pendingFieldChanges.isEmpty else {
                        throw Z21Error.validation("The JSON file does not contain any detail changes.")
                    }
                }
                importCoordinator.pendingLocomotive = proposed
                importReviewSession = ImportReviewSession(
                    source: url.lastPathComponent,
                    targetID: targetID,
                    target: original.name,
                    stage: functionsOnly ? .jsonFunctionChanges : .jsonFieldChanges)
                appStatus = .information("Review changes from \(url.lastPathComponent)")
            }
        }
    }

    func applyJSONFields(_ keys: Set<String>) {
        guard let index = importTargetIndex, let proposed = importCoordinator.pendingLocomotive else {
            present(Z21Error.validation("The locomotive selected for this import is no longer available."))
            return
        }
        for key in keys { importCoordinator.applyField(key, from: proposed, to: &locomotives[index]) }
        if !keys.isEmpty { markDirty() }
        finishImport("Applied \(keys.count) JSON detail changes")
    }

    func applyJSONFunctions(_ numbers: Set<Int>) {
        guard let index = importTargetIndex, let proposed = importCoordinator.pendingLocomotive else {
            present(Z21Error.validation("The locomotive selected for this import is no longer available."))
            return
        }
        for value in proposed.functions where numbers.contains(value.number) {
            if let existing = locomotives[index].functions.firstIndex(where: { $0.number == value.number }) {
                locomotives[index].functions[existing] = value
            } else { locomotives[index].functions.append(value) }
        }
        normalizePositions(&locomotives[index].functions)
        if !numbers.isEmpty { markDirty() }
        finishImport("Applied \(numbers.count) JSON function changes")
    }

    func cancelImportReview() {
        importReviewSession = nil
        importCoordinator.reset()
        pendingFieldChanges = []
        pendingFunctionChanges = []
        appStatus = .information("Import review cancelled; no changes applied")
    }

    private func finishImport(_ message: String) {
        importReviewSession = nil
        importCoordinator.reset()
        pendingFieldChanges = []
        pendingFunctionChanges = []
        appStatus = .warning(message + "; click Save to persist")
    }

    private func perform(_ action: () throws -> Void) {
        do { try action() } catch { present(error) }
    }

    private var importTargetIndex: Int? {
        importCoordinator.targetIndex(for: importReviewSession, in: locomotives)
    }

    func present(_ error: Error) {
        errorMessage = error.localizedDescription
        appStatus = .failure(error.localizedDescription)
    }

    func requestAbandonChanges(markDiscarded: Bool = false, completion: @escaping (Bool) -> Void) {
        guard isDirty else {
            completion(true)
            return
        }
        let alert = NSAlert()
        alert.messageText = "Save changes before continuing?"
        alert.informativeText = "The current Z21 archive contains unsaved changes."
        alert.addButton(withTitle: "Save")
        alert.addButton(withTitle: "Discard")
        alert.addButton(withTitle: "Cancel")
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            save(completion: completion)
        case .alertSecondButtonReturn:
            if markDiscarded { isDirty = false }
            completion(true)
        default:
            completion(false)
        }
    }
}

private func apply(_ proposal: FieldProposal, to value: inout Locomotive) {
    switch proposal.field {
    case "name": value.name = proposal.value
    case "full_name": value.fullName = proposal.value
    case "railway": value.railway = proposal.value
    case "article_number": value.articleNumber = proposal.value
    case "decoder_type": value.decoderType = proposal.value
    case "build_year": value.buildYear = proposal.value
    case "model_buffer_length": value.modelBufferLength = proposal.value
    case "service_weight": value.serviceWeight = proposal.value
    case "model_weight": value.modelWeight = proposal.value
    case "rmin": value.rmin = proposal.value
    case "drivers_cab": value.driversCab = proposal.value
    case "max_speed": value.speed = Int(proposal.value) ?? value.speed
    case "categories": value.categories = [proposal.value]
    case "description": value.description = proposal.value
    default: break
    }
}

private func safeFilename(_ value: String) -> String {
    let result = value.components(separatedBy: CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_ ")).inverted).joined()
    return result.isEmpty ? "locomotive" : result
}
