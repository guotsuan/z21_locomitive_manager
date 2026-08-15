import AppKit
import SwiftUI

@main
struct Z21ManagerApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(state)
                .onOpenURL { state.open($0) }
        }
        .defaultSize(width: 1180, height: 780)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Open…", action: state.openPanel).keyboardShortcut("o")
                Button("New Locomotive", action: state.addLocomotive).keyboardShortcut("n")
                    .disabled(state.fileURL == nil)
            }
            CommandGroup(replacing: .saveItem) {
                Button("Save", action: state.save).keyboardShortcut("s").disabled(state.fileURL == nil || !state.isDirty)
            }
            CommandMenu("Locomotive") {
                Button("Find Locomotive") {
                    NotificationCenter.default.post(name: .focusLibrarySearch, object: nil)
                }
                .keyboardShortcut("f")
                Button("Delete Locomotive…") {
                    NotificationCenter.default.post(name: .requestLocomotiveDeletion, object: nil)
                }
                .keyboardShortcut(.delete, modifiers: [.command])
                .disabled(state.selected == nil)
                Divider()
                Button("Show Overview") {
                    NotificationCenter.default.post(name: .showOverviewWorkspace, object: nil)
                }
                .keyboardShortcut("1")
                .disabled(state.selected == nil)
                Button("Show Functions") {
                    NotificationCenter.default.post(name: .showFunctionsWorkspace, object: nil)
                }
                .keyboardShortcut("2")
                .disabled(state.selected == nil)
                Divider()
                Button("Import .z21loco…", action: state.importLocomotive).disabled(state.fileURL == nil)
                    .keyboardShortcut("i", modifiers: [.command, .shift])
                Button("Export .z21loco…") { state.exportSelected() }.disabled(state.selected == nil)
                    .keyboardShortcut("e")
                Divider()
                Button("Import Manual with iPhone…") { state.captureFromIPhone() }.disabled(state.selected == nil)
                Button("OCR Manual…") { state.chooseDocumentForOCR() }.disabled(state.selected == nil)
                Button("Scan Function Table with iPhone…") { state.captureFromIPhone(functionTable: true) }.disabled(state.selected == nil)
                Button("OCR Function Table…") { state.chooseDocumentForOCR(functionTable: true) }.disabled(state.selected == nil)
            }
        }
        Settings { SettingsView() }
    }
}
