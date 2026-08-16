import AppKit
import Foundation
import XCTest
@testable import Z21Manager

final class Z21ManagerTests: XCTestCase {
    private var repositoryRoot: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
    }

    private var fixture: URL { repositoryRoot.appendingPathComponent("z21_new.z21") }

    func testLoadsRealZ21Archive() throws {
        let document = try Z21ArchiveDocument(url: fixture)
        let locomotives = try Z21Repository(databaseURL: document.databaseURL).loadLocomotives()
        XCTAssertGreaterThan(locomotives.count, 60)
        XCTAssertTrue(locomotives.allSatisfy { $0.vehicleID != nil })
        XCTAssertTrue(locomotives.contains { !$0.functions.isEmpty })
    }

    func testRoundTripPreservesArchiveMembersAndChanges() throws {
        let temporary = FileManager.default.temporaryDirectory
            .appendingPathComponent("roundtrip-\(UUID().uuidString).z21")
        try FileManager.default.copyItem(at: fixture, to: temporary)
        defer { try? FileManager.default.removeItem(at: temporary) }

        var before: Set<String> = []
        do {
            let document = try Z21ArchiveDocument(url: temporary)
            before = Set(try FileManager.default.subpathsOfDirectory(atPath: document.workingDirectory.path))
            let repository = try Z21Repository(databaseURL: document.databaseURL)
            var locomotives = try repository.loadLocomotives()
            let originalCount = locomotives.count
            locomotives[0].description = "Swift round-trip test"
            try repository.save(&locomotives)
            try document.write()
            XCTAssertEqual(locomotives.count, originalCount)
        }

        let reopened = try Z21ArchiveDocument(url: temporary)
        let after = Set(try FileManager.default.subpathsOfDirectory(atPath: reopened.workingDirectory.path))
        XCTAssertEqual(before, after)
        let values = try Z21Repository(databaseURL: reopened.databaseURL).loadLocomotives()
        XCTAssertEqual(values[0].description, "Swift round-trip test")
    }

    func testLocomotiveExportContainsOnlySelectedLocomotive() throws {
        let sourceDocument = try Z21ArchiveDocument(url: fixture)
        let sourceLocomotives = try Z21Repository(databaseURL: sourceDocument.databaseURL).loadLocomotives()
        let selected = try XCTUnwrap(sourceLocomotives.first { !$0.functions.isEmpty })
        let target = FileManager.default.temporaryDirectory
            .appendingPathComponent("single-locomotive-\(UUID().uuidString).z21loco")
        defer { try? FileManager.default.removeItem(at: target) }

        try ImportExportService.exportLocomotive(selected, from: sourceDocument, to: target)

        let exportedDocument = try Z21ArchiveDocument(url: target)
        let exported = try Z21Repository(databaseURL: exportedDocument.databaseURL).loadLocomotives()
        XCTAssertEqual(exported.count, 1)
        XCTAssertEqual(exported[0].name, selected.name)
        XCTAssertEqual(exported[0].address, selected.address)
        XCTAssertEqual(exported[0].functions.map(\.number), selected.functions.map(\.number))
        XCTAssertEqual(exported[0].functions.map(\.imageName), selected.functions.map(\.imageName))
        XCTAssertEqual(exported[0].functions.map(\.shortcut), selected.functions.map(\.shortcut))
        XCTAssertEqual(exported[0].functions.map(\.buttonType), selected.functions.map(\.buttonType))
        XCTAssertEqual(exported[0].functions.map(\.time), selected.functions.map(\.time))
        XCTAssertEqual(exported[0].functions.map(\.isActive), selected.functions.map(\.isActive))
    }

    func testValidationRejectsDuplicateAddress() throws {
        var first = Locomotive.blank(address: 3)
        first.name = "One"
        var second = Locomotive.blank(address: 3)
        second.name = "Two"
        XCTAssertThrowsError(try LocomotiveValidator.validate(second, among: [first, second]))
    }

    func testFunctionHelpersOrderAndFindGaps() {
        var values = [FunctionInfo(number: 4), FunctionInfo(number: 0), FunctionInfo(number: 2)]
        normalizePositions(&values)
        XCTAssertEqual(values.map(\.number), [0, 2, 4])
        XCTAssertEqual(FunctionMatcher.missingNumbers(values), [1, 3])
        XCTAssertEqual(FunctionMatcher.match("Open door", available: ["neutral", "door_open"]), "door_open")
    }

    func testFunctionMatcherUsesSandenIconForSandingTerms() {
        let icons = ["neutral", "sanden", "sound1"]
        XCTAssertEqual(FunctionMatcher.match("Sanding", available: icons), "sanden")
        XCTAssertEqual(FunctionMatcher.match("Sandstreuer", available: icons), "sanden")
        XCTAssertEqual(FunctionMatcher.match("Sablage", available: icons), "sanden")
        XCTAssertEqual(FunctionMatcher.match("撒砂", available: icons), "sanden")
    }

    func testFunctionMatcherUsesSound2IconForDriverNoise() {
        let icons = ["neutral", "sound1", "sound2"]
        XCTAssertEqual(FunctionMatcher.match("Driver noise", available: icons), "sound2")
        XCTAssertEqual(FunctionMatcher.match("Driving sound", available: icons), "sound2")
        XCTAssertEqual(FunctionMatcher.match("Fahrgeräusch", available: icons), "sound2")
        XCTAssertEqual(FunctionMatcher.match("Bruit de conduite", available: icons), "sound2")
    }

    func testFunctionExtractionRequiresEnglishNamesAndOriginalEvidence() {
        let prompt = DeepSeekService.functionExtractionPrompt
        XCTAssertTrue(prompt.contains("name_en"))
        XCTAssertTrue(prompt.contains("When no English description is present, translate"))
        XCTAssertTrue(prompt.contains("original OCR language"))
        XCTAssertEqual(FunctionMatcher.shortcut(description: "Driver noise", icon: "sound2"), "Drno")
    }

    func testFunctionReviewDoesNotSelectUnknownContentByDefault() {
        let proposals = [
            FunctionProposal(number: 0, name: "Front light", iconName: "light", buttonType: 0,
                             confidence: 0.95, evidence: "F0 Licht"),
            FunctionProposal(number: 1, name: "Unknown", iconName: "neutral", buttonType: 0,
                             confidence: 0.2, evidence: "F1"),
            FunctionProposal(number: 2, name: "No description", iconName: "neutral", buttonType: 0,
                             confidence: 0.2, evidence: "F2")
        ]

        XCTAssertEqual(FunctionReviewSelection.defaults(for: proposals, existingNumbers: []), [0])
        XCTAssertEqual(FunctionReviewSelection.defaults(for: proposals, existingNumbers: [0]), [])
        XCTAssertEqual(
            FunctionReviewSelection.settingAll(true, numbers: [0, 1, 2], current: []),
            [0, 1, 2]
        )
        XCTAssertEqual(
            FunctionReviewSelection.settingAll(false, numbers: [0, 1, 2], current: [0, 1, 2, 9]),
            [9]
        )
    }

    func testFunctionAccessibilitySummaryContainsStateAndSelection() {
        let function = FunctionInfo(
            number: 7,
            imageName: "light",
            shortcut: "Main beam",
            time: 1.5,
            buttonType: 2,
            isActive: false
        )

        XCTAssertEqual(
            FunctionAccessibility.summary(for: function, isSelected: true),
            "F7, Main beam, Timed, 1.5 seconds, inactive, selected"
        )
    }

    func testJSONFunctionImportUpdatesAndAdds() throws {
        var locomotive = Locomotive.blank(address: 1)
        locomotive.functions = [FunctionInfo(number: 0, imageName: "neutral")]
        let data = #"{"functions":[{"number":"F0","name":"Light","type":"switch"},{"number":"F2","name":"Open door","type":"push"}]}"#.data(using: .utf8)!
        try JSONImporter.applyFunctionsJSON(data, to: &locomotive,
                                            availableIcons: ["neutral", "light", "door_open"])
        XCTAssertEqual(locomotive.functions.map(\.number), [0, 2])
        XCTAssertEqual(locomotive.functions[1].imageName, "door_open")
        XCTAssertEqual(locomotive.functions[1].buttonType, 1)
    }

    func testVehicleTypeAndInactiveFunctionRoundTrip() throws {
        let temporary = FileManager.default.temporaryDirectory
            .appendingPathComponent("vehicle-type-roundtrip-\(UUID().uuidString).z21")
        try FileManager.default.copyItem(at: fixture, to: temporary)
        defer { try? FileManager.default.removeItem(at: temporary) }

        let vehicleID: Int64
        do {
            let document = try Z21ArchiveDocument(url: temporary)
            let repository = try Z21Repository(databaseURL: document.databaseURL)
            var locomotives = try repository.loadLocomotives()
            let index = try XCTUnwrap(locomotives.firstIndex { !$0.functions.isEmpty })
            vehicleID = try XCTUnwrap(locomotives[index].vehicleID)
            locomotives[index].railVehicleType = 1
            locomotives[index].functions[0].isActive = false
            try repository.save(&locomotives)
            try document.write()
        }

        let reopened = try Z21ArchiveDocument(url: temporary)
        let values = try Z21Repository(databaseURL: reopened.databaseURL).loadLocomotives()
        let changed = try XCTUnwrap(values.first { $0.vehicleID == vehicleID })
        XCTAssertEqual(changed.railVehicleType, 1)
        XCTAssertFalse(try XCTUnwrap(changed.functions.first).isActive)
    }

    func testExportIncludesImageAddedToUnsavedWorkingCopy() throws {
        let sourceDocument = try Z21ArchiveDocument(url: fixture)
        var selected = try XCTUnwrap(
            try Z21Repository(databaseURL: sourceDocument.databaseURL).loadLocomotives().first
        )
        let imageData = Data("unsaved-image-payload".utf8)
        let imageSource = FileManager.default.temporaryDirectory
            .appendingPathComponent("draft-image-\(UUID().uuidString).png")
        let target = FileManager.default.temporaryDirectory
            .appendingPathComponent("draft-image-export-\(UUID().uuidString).z21loco")
        try imageData.write(to: imageSource, options: .atomic)
        defer {
            try? FileManager.default.removeItem(at: imageSource)
            try? FileManager.default.removeItem(at: target)
        }

        selected.imageName = try sourceDocument.addImage(from: imageSource)
        try ImportExportService.exportLocomotive(selected, from: sourceDocument, to: target)

        let exportedDocument = try Z21ArchiveDocument(url: target)
        let exported = try XCTUnwrap(
            try Z21Repository(databaseURL: exportedDocument.databaseURL).loadLocomotives().first
        )
        let exportedImage = try XCTUnwrap(exportedDocument.imageURL(named: exported.imageName))
        XCTAssertEqual(try Data(contentsOf: exportedImage), imageData)
    }

    func testArchiveImageLookupRejectsParentTraversal() throws {
        let document = try Z21ArchiveDocument(url: fixture)
        let outside = document.workingDirectory.deletingLastPathComponent()
            .appendingPathComponent("outside-\(UUID().uuidString).png")
        try Data("outside".utf8).write(to: outside, options: .atomic)
        defer { try? FileManager.default.removeItem(at: outside) }

        XCTAssertNil(document.imageURL(named: "../\(outside.lastPathComponent)"))
    }

    @MainActor
    func testImportReviewAppliesToCapturedTargetAfterSelectionChanges() {
        let state = AppState()
        var first = Locomotive.blank(address: 1)
        first.name = "First"
        var second = Locomotive.blank(address: 2)
        second.name = "Second"
        state.locomotives = [first, second]
        state.selection = second.id
        state.importReviewSession = ImportReviewSession(
            source: "manual.pdf", targetID: first.id, target: first.name, stage: .fieldChanges
        )
        let proposal = FieldProposal(
            field: "railway", value: "DB", confidence: 1, evidence: "DB", page: 1
        )
        state.fieldProposals = [proposal]

        state.applyFields([proposal.id])

        XCTAssertEqual(state.locomotives[0].railway, "DB")
        XCTAssertEqual(state.locomotives[1].railway, "")
        XCTAssertTrue(state.isDirty)
    }

    @MainActor
    func testLocomotiveDetailBindingSurvivesTargetDeletion() {
        let state = AppState()
        var locomotive = Locomotive.blank(address: 1)
        locomotive.name = "Delete Me"
        state.locomotives = [locomotive]
        state.selection = locomotive.id
        let binding = LocomotiveDetailBinding.make(id: locomotive.id, fallback: locomotive, state: state)

        state.deleteSelected()

        XCTAssertTrue(state.locomotives.isEmpty)
        XCTAssertNil(state.selection)
        XCTAssertEqual(binding.wrappedValue.id, locomotive.id)
        var staleUpdate = binding.wrappedValue
        staleUpdate.name = "Should Not Reappear"
        binding.wrappedValue = staleUpdate
        XCTAssertTrue(state.locomotives.isEmpty)
    }

    func testRepositorySavePreservesSQLiteUserVersion() throws {
        let temporary = FileManager.default.temporaryDirectory
            .appendingPathComponent("user-version-\(UUID().uuidString).z21")
        try FileManager.default.copyItem(at: fixture, to: temporary)
        defer { try? FileManager.default.removeItem(at: temporary) }

        let document = try Z21ArchiveDocument(url: temporary)
        func userVersion() throws -> Int64? {
            try SQLiteDatabase(url: document.databaseURL).scalarInt("PRAGMA user_version")
        }
        let before = try userVersion()
        let repository = try Z21Repository(databaseURL: document.databaseURL)
        var locomotives = try repository.loadLocomotives()
        try repository.save(&locomotives)
        XCTAssertEqual(try userVersion(), before)
    }

    func testDocumentSessionLoadsArchiveOffMainState() async throws {
        let opened = try await DocumentSession.open(fixture)
        XCTAssertGreaterThan(opened.locomotives.count, 60)
        XCTAssertEqual(opened.session.fileURL, fixture)
    }

    @MainActor
    func testAirDropTemporaryExportCleanupRemovesOnlyGeneratedDirectory() throws {
        let target = try ImportExportService.airDropExportURL(filename: "test.z21loco")
        try Data("archive".utf8).write(to: target, options: .atomic)
        let directory = target.deletingLastPathComponent()
        XCTAssertTrue(FileManager.default.fileExists(atPath: directory.path))

        AirDropShareManager.cleanupTemporaryExport(at: target)

        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
    }

    func testFunctionKeyboardNavigationMovesAndClamps() {
        let numbers = [0, 2, 4]
        XCTAssertEqual(FunctionKeyboardNavigation.adjacentNumber(in: numbers, current: nil, offset: 1), 0)
        XCTAssertEqual(FunctionKeyboardNavigation.adjacentNumber(in: numbers, current: 2, offset: 1), 4)
        XCTAssertEqual(FunctionKeyboardNavigation.adjacentNumber(in: numbers, current: 4, offset: 1), 4)
        XCTAssertEqual(FunctionKeyboardNavigation.adjacentNumber(in: numbers, current: 0, offset: -1), 0)
    }

    @MainActor
    func testContinuityCaptureTemporaryFileIsRemovedAfterOCR() async throws {
        let image = NSImage(size: NSSize(width: 100, height: 100))
        image.lockFocus()
        NSColor.white.setFill()
        NSBezierPath(rect: NSRect(x: 0, y: 0, width: 100, height: 100)).fill()
        image.unlockFocus()
        let png = try XCTUnwrap(
            image.tiffRepresentation
                .flatMap(NSBitmapImageRep.init(data:))?
                .representation(using: .png, properties: [:])
        )
        let source = FileManager.default.temporaryDirectory
            .appendingPathComponent("continuity-test-\(UUID().uuidString).png")
        try png.write(to: source, options: .atomic)
        defer { try? FileManager.default.removeItem(at: source) }

        let state = AppState()
        var locomotive = Locomotive.blank(address: 1)
        locomotive.name = "OCR Target"
        state.locomotives = [locomotive]
        state.selection = locomotive.id
        state.recognize(source, functionTable: false, deleteSourceWhenFinished: true)
        for _ in 0..<200 where state.isBusy {
            try await Task.sleep(nanoseconds: 25_000_000)
        }

        XCTAssertFalse(state.isBusy)
        XCTAssertFalse(FileManager.default.fileExists(atPath: source.path))
    }
}
