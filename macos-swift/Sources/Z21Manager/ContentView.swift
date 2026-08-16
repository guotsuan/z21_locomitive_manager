import AppKit
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            NavigationSplitView {
                LibrarySidebar()
                    .navigationSplitViewColumnWidth(min: 260, ideal: 300, max: 380)
            } detail: {
                if let id = state.selection,
                   let fallback = state.locomotives.first(where: { $0.id == id }) {
                    LocomotiveDetail(
                        locomotive: LocomotiveDetailBinding.make(id: id, fallback: fallback, state: state)
                    )
                    .id(id)
                } else {
                    ContentUnavailableView("No Locomotive Selected", systemImage: "tram",
                                           description: Text(state.fileURL == nil ? "Open a Z21 archive to begin." : "Choose or create a locomotive."))
                }
            }

            Divider()
            StatusPresenter()
        }
        .frame(minWidth: 980, minHeight: 660)
        .background(WindowCloseGuard(state: state).frame(width: 0, height: 0))
        .toolbar { toolbar }
        .alert("Z21 Manager", isPresented: Binding(
            get: { state.errorMessage != nil },
            set: { if !$0 { state.errorMessage = nil } })) {
                Button("OK") { state.errorMessage = nil }
            } message: { Text(state.errorMessage ?? "") }
        .sheet(item: $state.importReviewSession) { _ in ImportReviewView() }
        .sheet(isPresented: $state.showingSettings) { SettingsView() }
        .sheet(isPresented: Binding(
            get: { state.cropSourceURL != nil },
            set: { if !$0 { state.cropSourceURL = nil } })) {
                if let url = state.cropSourceURL { ImageCropView(source: url) }
            }
        .onAppear {
            let arguments = Array(CommandLine.arguments.dropFirst())
            if state.fileURL == nil, let path = arguments.first, !path.hasPrefix("-") {
                state.open(URL(fileURLWithPath: path))
            }
        }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .navigation) {
            Button(action: state.openPanel) { Label("Open", systemImage: "folder") }
            Button(action: state.save) { Label("Save", systemImage: "square.and.arrow.down") }
                .disabled(state.fileURL == nil || !state.isDirty)
        }
        ToolbarItemGroup(placement: .primaryAction) {
            Menu {
                Button("Import .z21loco…", action: state.importLocomotive)
                Button("Import Details from JSON…", action: state.importLocomotiveJSON)
                    .disabled(state.selected == nil)
                Button("Import Functions from JSON…", action: state.importFunctionsJSON)
                    .disabled(state.selected == nil)
                Divider()
                Button("Import Locomotive Image…", action: state.importLocomotiveImage).disabled(state.selected == nil)
                Button("Import Manual with iPhone…") { state.captureFromIPhone() }.disabled(state.selected == nil)
                Button("OCR Manual…") { state.chooseDocumentForOCR() }.disabled(state.selected == nil)
                Button("Scan Function Table with iPhone…") { state.captureFromIPhone(functionTable: true) }.disabled(state.selected == nil)
                Button("OCR Function Table…") { state.chooseDocumentForOCR(functionTable: true) }.disabled(state.selected == nil)
            } label: { Label("Import", systemImage: "square.and.arrow.down.on.square") }
            .disabled(state.fileURL == nil)
            Menu {
                Button("Export .z21loco…") { state.exportSelected() }
                Button("Export with AirDrop…") { state.exportSelected(airDrop: true) }
            } label: { Label("Export", systemImage: "square.and.arrow.up") }
            .disabled(state.selected == nil)
            Button { state.showingSettings = true } label: { Label("Settings", systemImage: "gearshape") }
        }
    }

}

@MainActor
enum LocomotiveDetailBinding {
    static func make(id: UUID, fallback: Locomotive, state: AppState) -> Binding<Locomotive> {
        Binding(
            get: {
                state.locomotives.first(where: { $0.id == id }) ?? fallback
            },
            set: { updated in
                guard let index = state.locomotives.firstIndex(where: { $0.id == id }) else { return }
                state.locomotives[index] = updated
                state.markDirty()
            }
        )
    }
}

struct LocomotiveDetail: View {
    @EnvironmentObject private var state: AppState
    @Binding var locomotive: Locomotive
    @State private var section: DetailSection = .overview

    private enum DetailSection: String, CaseIterable, Identifiable {
        case overview = "Overview"
        case functions = "Functions"
        var id: Self { self }
    }

    var body: some View {
        VStack(spacing: 0) {
            LocomotiveHeader(locomotive: $locomotive)
                .padding(.horizontal, DesignTokens.pagePadding)
                .padding(.top, DesignTokens.contentSpacing)

            HStack {
                Spacer()
                Picker("Workspace", selection: $section) {
                    ForEach(DetailSection.allCases) { value in
                        Text(value.rawValue).tag(value)
                    }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(width: 240)
                .accessibilityLabel("Detail Workspace")
                .accessibilityHint("Choose Overview or Functions")
                Spacer()
            }
            .padding(.horizontal, DesignTokens.pagePadding)
            .padding(.vertical, 12)

            Divider()
            Group {
                switch section {
                case .overview:
                    OverviewWorkspace(locomotive: $locomotive)
                case .functions:
                    FunctionWorkspace(functions: $locomotive.functions, locomotiveName: locomotive.name)
                        .padding(.horizontal, DesignTokens.pagePadding)
                }
            }
        }
        .navigationTitle(locomotive.name.isEmpty ? "Locomotive" : locomotive.name)
        .onReceive(NotificationCenter.default.publisher(for: .showOverviewWorkspace)) { _ in section = .overview }
        .onReceive(NotificationCenter.default.publisher(for: .showFunctionsWorkspace)) { _ in section = .functions }
    }
}

extension Notification.Name {
    static let showOverviewWorkspace = Notification.Name("showOverviewWorkspace")
    static let showFunctionsWorkspace = Notification.Name("showFunctionsWorkspace")
    static let focusLibrarySearch = Notification.Name("focusLibrarySearch")
    static let requestLocomotiveDeletion = Notification.Name("requestLocomotiveDeletion")
}
