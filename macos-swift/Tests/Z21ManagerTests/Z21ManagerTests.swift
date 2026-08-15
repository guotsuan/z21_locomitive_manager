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

        try ImportExportService.exportLocomotive(selected, from: fixture, to: target)

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
}
