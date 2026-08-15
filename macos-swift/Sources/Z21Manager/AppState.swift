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
    private var document: Z21ArchiveDocument?
    private var repository: Z21Repository?
    private var pendingImportLocomotive: Locomotive?
    private let continuityCamera = ContinuityCameraCapture()

    var selectedIndex: Int? { selection.flatMap { id in locomotives.firstIndex { $0.id == id } } }
    var selected: Locomotive? { selectedIndex.map { locomotives[$0] } }
    var filteredLocomotives: [Locomotive] {
        guard !searchText.isEmpty else { return locomotives }
        return locomotives.filter { $0.name.localizedCaseInsensitiveContains(searchText) || String($0.address).contains(searchText) }
    }
    var availableIcons: [String] { IconCatalog.icons() }
    func open(_ url: URL) {
        guard confirmAbandonChanges() else { return }
        perform {
            let document = try Z21ArchiveDocument(url: url)
            let repository = try Z21Repository(databaseURL: document.databaseURL)
            let values = try repository.loadLocomotives()
            self.document = document
            self.repository = repository
            self.fileURL = url
            self.locomotives = values
            self.selection = values.first?.id
            self.isDirty = false
            self.appStatus = .success("Loaded \(values.count) locomotives from \(url.lastPathComponent)")
            NSDocumentController.shared.noteNewRecentDocumentURL(url)
        }
    }

    func openPanel() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.init(filenameExtension: "z21")!]
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { open(url) }
    }

    func save() {
        perform {
            guard let repository, let document else { throw Z21Error.validation("No Z21 file is open.") }
            for index in locomotives.indices {
                locomotives[index].categories = LocomotiveValidator.normalizeCategories(locomotives[index].categories)
            }
            for locomotive in locomotives { try LocomotiveValidator.validate(locomotive, among: locomotives) }
            try repository.save(&locomotives)
            try document.write()
            isDirty = false
            appStatus = .success("Saved \(locomotives.count) locomotives")
        }
    }

    func markDirty() { isDirty = true }

    func addLocomotive() {
        let used = Set(locomotives.map(\.address))
        guard let address = (1...9999).first(where: { !used.contains($0) }) else { return }
        let locomotive = Locomotive.blank(address: address)
        locomotives.append(locomotive)
        selection = locomotive.id
        isDirty = true
        appStatus = .warning("Created locomotive at address \(address)")
    }

    func deleteSelected() {
        guard let index = selectedIndex else { return }
        locomotives.remove(at: index)
        selection = locomotives.indices.contains(index) ? locomotives[index].id : locomotives.last?.id
        isDirty = true
        appStatus = .warning("Locomotive removed; click Save to persist")
    }

    func importLocomotive() {
        guard let document else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.init(filenameExtension: "z21loco")!]
        if panel.runModal() == .OK, let url = panel.url {
            perform {
                let value = try ImportExportService.importLocomotive(from: url, into: document, existing: locomotives)
                locomotives.append(value)
                selection = value.id
                isDirty = true
                appStatus = .warning("Imported \(value.name); click Save to persist")
            }
        }
    }

    func exportSelected(airDrop: Bool = false) {
        guard let locomotive = selected, let source = fileURL else { return }
        if airDrop {
            perform {
                let filename = "\(safeFilename(locomotive.name)).z21loco"
                let target = try ImportExportService.airDropExportURL(filename: filename)
                try ImportExportService.exportLocomotive(locomotive, from: source, to: target)
                try ImportExportService.shareViaAirDrop(target)
                appStatus = .information("Choose an AirDrop recipient for \(filename)")
            }
            return
        }

        let panel = NSSavePanel()
        panel.allowedContentTypes = [.init(filenameExtension: "z21loco")!]
        panel.nameFieldStringValue = "\(safeFilename(locomotive.name)).z21loco"
        if panel.runModal() == .OK, let target = panel.url {
            perform {
                try ImportExportService.exportLocomotive(locomotive, from: source, to: target)
                appStatus = .success("Exported \(locomotive.name)")
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
            self.recognize(url, functionTable: functionTable)
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
        guard selectedIndex != nil, document != nil else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.png, .jpeg, .tiff, .heic]
        if panel.runModal() == .OK, let url = panel.url {
            cropSourceURL = url
        }
    }

    func applyCroppedImage(_ source: URL, rect: CGRect) {
        guard let index = selectedIndex, let document else { return }
        perform {
            let cropped = try ImageCropper.crop(source, normalized: rect)
            defer { try? FileManager.default.removeItem(at: cropped) }
            locomotives[index].imageName = try document.addImage(from: cropped)
            cropSourceURL = nil
            isDirty = true
            appStatus = .warning("Updated locomotive image; click Save to persist")
        }
    }

    func recognize(_ url: URL, functionTable: Bool) {
        guard selectedIndex != nil else { return }
        isBusy = true
        appStatus = .working("Recognizing text with Apple Vision…")
        Task {
            do {
                let result = try await Task.detached { try AppleVisionOCR.recognize(url) }.value
                ocrText = result.text
                if functionTable {
                    try await analyzeFunctions(result)
                    importReviewSession = ImportReviewSession(source: url.lastPathComponent,
                                                              target: selected?.name ?? "Locomotive",
                                                              stage: .functionChanges)
                } else {
                    importReviewSession = ImportReviewSession(source: url.lastPathComponent,
                                                              target: selected?.name ?? "Locomotive",
                                                              stage: .ocrText)
                }
                appStatus = .success("Recognized \(result.pages.count) page(s)")
            } catch { present(error) }
            isBusy = false
        }
    }

    func analyzeFields() {
        guard let locomotive = selected else { return }
        appStatus = .working("Analyzing recognized details with DeepSeek…")
        Task {
            do {
                guard let key = try DeepSeekKeychain.get() else { throw Z21Error.service("Add a DeepSeek API key in Settings first.") }
                isBusy = true
                fieldProposals = try await DeepSeekService(apiKey: key).extractFields(text: ocrText, existing: locomotive)
                importReviewSession?.stage = .fieldChanges
                appStatus = .information("Review \(fieldProposals.count) proposed detail changes")
            } catch { present(error) }
            isBusy = false
        }
    }

    func applyFields(_ selectedProposals: Set<UUID>) {
        guard let index = selectedIndex else { return }
        for proposal in fieldProposals where selectedProposals.contains(proposal.id) {
            apply(proposal, to: &locomotives[index])
        }
        finishImport("Applied \(selectedProposals.count) detail changes")
        isDirty = true
    }

    func applyFunctions(_ selectedNumbers: Set<Int>) {
        guard let index = selectedIndex else { return }
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
        isDirty = true
    }

    func imageURL(for locomotive: Locomotive) -> URL? { document?.imageURL(named: locomotive.imageName) }

    private func analyzeFunctions(_ result: OCRResult) async throws {
        guard let key = try DeepSeekKeychain.get() else { throw Z21Error.service("Add a DeepSeek API key in Settings first.") }
        functionProposals = try await DeepSeekService(apiKey: key).extractFunctions(result: result, availableIcons: availableIcons)
    }

    private func chooseJSON(functionsOnly: Bool) {
        guard let index = selectedIndex else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json]
        if panel.runModal() == .OK, let url = panel.url {
            perform {
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
                    pendingFieldChanges = Self.fieldChanges(from: original, to: proposed)
                    guard !pendingFieldChanges.isEmpty else {
                        throw Z21Error.validation("The JSON file does not contain any detail changes.")
                    }
                }
                pendingImportLocomotive = proposed
                importReviewSession = ImportReviewSession(
                    source: url.lastPathComponent,
                    target: original.name,
                    stage: functionsOnly ? .jsonFunctionChanges : .jsonFieldChanges)
                appStatus = .information("Review changes from \(url.lastPathComponent)")
            }
        }
    }

    func applyJSONFields(_ keys: Set<String>) {
        guard let index = selectedIndex, let proposed = pendingImportLocomotive else { return }
        for key in keys { Self.applyField(key, from: proposed, to: &locomotives[index]) }
        isDirty = !keys.isEmpty || isDirty
        finishImport("Applied \(keys.count) JSON detail changes")
    }

    func applyJSONFunctions(_ numbers: Set<Int>) {
        guard let index = selectedIndex, let proposed = pendingImportLocomotive else { return }
        for value in proposed.functions where numbers.contains(value.number) {
            if let existing = locomotives[index].functions.firstIndex(where: { $0.number == value.number }) {
                locomotives[index].functions[existing] = value
            } else { locomotives[index].functions.append(value) }
        }
        normalizePositions(&locomotives[index].functions)
        isDirty = !numbers.isEmpty || isDirty
        finishImport("Applied \(numbers.count) JSON function changes")
    }

    func cancelImportReview() {
        importReviewSession = nil
        pendingImportLocomotive = nil
        pendingFieldChanges = []
        pendingFunctionChanges = []
        appStatus = .information("Import review cancelled; no changes applied")
    }

    private func finishImport(_ message: String) {
        importReviewSession = nil
        pendingImportLocomotive = nil
        pendingFieldChanges = []
        pendingFunctionChanges = []
        appStatus = .warning(message + "; click Save to persist")
    }

    private func perform(_ action: () throws -> Void) {
        do { try action() } catch { present(error) }
    }

    private static func fieldChanges(from current: Locomotive, to proposed: Locomotive) -> [ImportFieldChange] {
        let values: [(String, String, String, String)] = [
            ("name", "Name", current.name, proposed.name),
            ("address", "Address", String(current.address), String(proposed.address)),
            ("speed", "Max Speed", String(current.speed), String(proposed.speed)),
            ("speedDisplay", "Speed Display", String(current.speedDisplay), String(proposed.speedDisplay)),
            ("fullName", "Full Name", current.fullName, proposed.fullName),
            ("railway", "Railway", current.railway, proposed.railway),
            ("articleNumber", "Article Number", current.articleNumber, proposed.articleNumber),
            ("decoderType", "Decoder / Interface", current.decoderType, proposed.decoderType),
            ("buildYear", "Build Year", current.buildYear, proposed.buildYear),
            ("modelBufferLength", "Model Buffer Length", current.modelBufferLength, proposed.modelBufferLength),
            ("serviceWeight", "Service Weight", current.serviceWeight, proposed.serviceWeight),
            ("modelWeight", "Model Weight", current.modelWeight, proposed.modelWeight),
            ("rmin", "Minimum Radius", current.rmin, proposed.rmin),
            ("ip", "IP Address", current.ip, proposed.ip),
            ("driversCab", "Driver’s Cab", current.driversCab, proposed.driversCab),
            ("description", "Description", current.description, proposed.description)
        ]
        return values.compactMap { key, label, old, new in
            old == new ? nil : ImportFieldChange(id: key, label: label, current: old, proposed: new)
        }
    }

    private static func applyField(_ key: String, from source: Locomotive, to target: inout Locomotive) {
        switch key {
        case "name": target.name = source.name
        case "address": target.address = source.address
        case "speed": target.speed = source.speed
        case "speedDisplay": target.speedDisplay = source.speedDisplay
        case "fullName": target.fullName = source.fullName
        case "railway": target.railway = source.railway
        case "articleNumber": target.articleNumber = source.articleNumber
        case "decoderType": target.decoderType = source.decoderType
        case "buildYear": target.buildYear = source.buildYear
        case "modelBufferLength": target.modelBufferLength = source.modelBufferLength
        case "serviceWeight": target.serviceWeight = source.serviceWeight
        case "modelWeight": target.modelWeight = source.modelWeight
        case "rmin": target.rmin = source.rmin
        case "ip": target.ip = source.ip
        case "driversCab": target.driversCab = source.driversCab
        case "description": target.description = source.description
        default: break
        }
    }

    private func present(_ error: Error) {
        errorMessage = error.localizedDescription
        appStatus = .failure(error.localizedDescription)
    }

    func confirmAbandonChanges() -> Bool {
        guard isDirty else { return true }
        let alert = NSAlert()
        alert.messageText = "Save changes before continuing?"
        alert.informativeText = "The current Z21 archive contains unsaved changes."
        alert.addButton(withTitle: "Save")
        alert.addButton(withTitle: "Discard")
        alert.addButton(withTitle: "Cancel")
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            save()
            return !isDirty
        case .alertSecondButtonReturn:
            return true
        default:
            return false
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
