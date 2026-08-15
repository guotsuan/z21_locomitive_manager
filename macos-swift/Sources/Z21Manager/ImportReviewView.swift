import SwiftUI

struct ImportReviewView: View {
    @EnvironmentObject private var state: AppState
    @State private var selectedFields = Set<UUID>()
    @State private var selectedFunctions = Set<Int>()
    @State private var selectedJSONFields = Set<String>()

    private var session: ImportReviewSession? { state.importReviewSession }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                header
                Divider()
                content
                Divider()
                footer
            }
            .navigationTitle(session?.stage.title ?? "Import Review")
        }
        .frame(minWidth: 900, minHeight: 560)
        .interactiveDismissDisabled()
        .onAppear(perform: initializeSelection)
        .onChange(of: state.importReviewSession?.stage) { initializeSelection() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(session?.source ?? "Import", systemImage: "doc.badge.arrow.up")
                Image(systemName: "arrow.right").foregroundStyle(.secondary)
                Label(session?.target ?? "Locomotive", systemImage: "tram.fill")
                Spacer()
                Label("Draft only", systemImage: "square.and.pencil")
                    .font(.caption).foregroundStyle(.secondary)
            }
            ImportProgress(stage: session?.stage ?? .ocrText)
            Text("Review and select changes before applying. The archive is not written until you click Save.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(20)
    }

    @ViewBuilder private var content: some View {
        switch session?.stage {
        case .ocrText:
            TextEditor(text: $state.ocrText)
                .font(.system(.body, design: .monospaced))
                .padding(16)
                .accessibilityLabel("Recognized text")
        case .fieldChanges: fieldTable
        case .functionChanges: functionProposalTable
        case .jsonFieldChanges: jsonFieldTable
        case .jsonFunctionChanges: jsonFunctionTable
        case nil: ProgressView()
        }
    }

    private var fieldTable: some View {
        Table(state.fieldProposals) {
            TableColumn("") { item in Toggle("Select \(item.field) change", isOn: fieldToggle(item.id)).labelsHidden() }.width(28)
            TableColumn("Field", value: \.field).width(min: 120)
            TableColumn("Current") { _ in Text("Empty").foregroundStyle(.secondary) }.width(min: 90)
            TableColumn("Proposed", value: \.value).width(min: 150)
            TableColumn("Confidence") { ConfidenceLabel(value: $0.confidence) }.width(120)
            TableColumn("Evidence", value: \.evidence)
        }
    }

    private var functionProposalTable: some View {
        Table($state.functionProposals) {
            TableColumn("") { $item in Toggle("Select F\(item.number) change", isOn: functionToggle(item.number)).labelsHidden() }.width(28)
            TableColumn("F") { $item in Text("F\(item.number)").fontWeight(.semibold) }.width(45)
            TableColumn("Change") { $item in changeLabel(item.number) }.width(75)
            TableColumn("Description") { $item in Text(item.name) }.width(min: 150)
            TableColumn("Icon") { $item in
                Picker("Icon", selection: $item.iconName) { ForEach(state.availableIcons, id: \.self, content: Text.init) }.labelsHidden()
            }.width(min: 140)
            TableColumn("Behavior") { $item in behaviorPicker($item.buttonType) }.width(105)
            TableColumn("Confidence") { $item in ConfidenceLabel(value: item.confidence) }.width(120)
            TableColumn("Evidence") { $item in Text(item.evidence).lineLimit(1) }
        }
    }

    private var jsonFieldTable: some View {
        Table(state.pendingFieldChanges) {
            TableColumn("") { item in Toggle("Select \(item.label) change", isOn: jsonFieldToggle(item.id)).labelsHidden() }.width(28)
            TableColumn("Field", value: \.label).width(min: 130)
            TableColumn("Current", value: \.current).width(min: 180)
            TableColumn("") { _ in Image(systemName: "arrow.right").foregroundStyle(.secondary) }.width(30)
            TableColumn("Proposed", value: \.proposed).width(min: 180)
        }
    }

    private var jsonFunctionTable: some View {
        Table($state.pendingFunctionChanges) {
            TableColumn("") { $item in Toggle("Select F\(item.number) change", isOn: functionToggle(item.number)).labelsHidden() }.width(28)
            TableColumn("F") { $item in Text("F\(item.number)").fontWeight(.semibold) }.width(45)
            TableColumn("Change") { $item in changeLabel(item.number) }.width(75)
            TableColumn("Shortcut") { $item in Text(item.shortcut) }
            TableColumn("Icon") { $item in
                Picker("Icon", selection: $item.imageName) { ForEach(state.availableIcons, id: \.self, content: Text.init) }.labelsHidden()
            }.width(min: 140)
            TableColumn("Behavior") { $item in behaviorPicker($item.buttonType) }.width(105)
        }
    }

    private var footer: some View {
        HStack {
            Button("Cancel", role: .cancel, action: state.cancelImportReview)
            Spacer()
            if session?.stage == .ocrText {
                Button("Analyze", systemImage: "sparkles", action: state.analyzeFields)
                    .buttonStyle(.borderedProminent)
                    .disabled(state.ocrText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || state.isBusy)
                    .keyboardShortcut(.defaultAction)
            } else {
                Button("Apply \(selectionCount) Changes", systemImage: "checkmark", action: applySelection)
                    .buttonStyle(.borderedProminent)
                    .disabled(selectionCount == 0 || state.isBusy)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(16)
    }

    private var selectionCount: Int {
        switch session?.stage {
        case .fieldChanges: selectedFields.count
        case .functionChanges, .jsonFunctionChanges: selectedFunctions.count
        case .jsonFieldChanges: selectedJSONFields.count
        default: 0
        }
    }

    private func initializeSelection() {
        switch session?.stage {
        case .fieldChanges:
            selectedFields = Set(state.fieldProposals.map(\.id))
        case .functionChanges:
            selectNewFunctions(state.functionProposals.map(\.number))
        case .jsonFieldChanges:
            selectedJSONFields = Set(state.pendingFieldChanges.map(\.id))
        case .jsonFunctionChanges:
            selectNewFunctions(state.pendingFunctionChanges.map(\.number))
        default: break
        }
    }

    private func selectNewFunctions(_ numbers: [Int]) {
        let existing = Set(state.importTarget?.functions.map(\.number) ?? [])
        selectedFunctions = Set(numbers).subtracting(existing)
    }

    private func applySelection() {
        switch session?.stage {
        case .fieldChanges: state.applyFields(selectedFields)
        case .functionChanges: state.applyFunctions(selectedFunctions)
        case .jsonFieldChanges: state.applyJSONFields(selectedJSONFields)
        case .jsonFunctionChanges: state.applyJSONFunctions(selectedFunctions)
        default: break
        }
    }

    private func changeLabel(_ number: Int) -> some View {
        Text(state.importTarget?.functions.contains(where: { $0.number == number }) == true ? "Update" : "Add")
            .font(.caption).foregroundStyle(.secondary)
    }

    private func behaviorPicker(_ binding: Binding<Int>) -> some View {
        Picker("Behavior", selection: binding) {
            Text("Switch").tag(0); Text("Push").tag(1); Text("Timed").tag(2)
        }.labelsHidden()
    }

    private func fieldToggle(_ id: UUID) -> Binding<Bool> {
        Binding(get: { selectedFields.contains(id) }, set: { enabled in
            if enabled { selectedFields.insert(id) } else { selectedFields.remove(id) }
        })
    }
    private func functionToggle(_ number: Int) -> Binding<Bool> {
        Binding(get: { selectedFunctions.contains(number) }, set: { enabled in
            if enabled { selectedFunctions.insert(number) } else { selectedFunctions.remove(number) }
        })
    }
    private func jsonFieldToggle(_ id: String) -> Binding<Bool> {
        Binding(get: { selectedJSONFields.contains(id) }, set: { enabled in
            if enabled { selectedJSONFields.insert(id) } else { selectedJSONFields.remove(id) }
        })
    }
}

private struct ImportProgress: View {
    let stage: ImportReviewStage
    var body: some View {
        HStack(spacing: 8) {
            step("1", "Source", complete: true)
            step("2", "Parse", complete: true)
            step("3", "Review", complete: stage != .ocrText)
            step("4", "Apply", complete: false)
        }
    }
    private func step(_ number: String, _ label: String, complete: Bool) -> some View {
        HStack(spacing: 5) {
            Image(systemName: complete ? "checkmark.circle.fill" : "\(number).circle")
            Text(label)
        }
        .font(.caption)
        .foregroundStyle(complete ? Color.accentColor : Color.secondary)
        .frame(maxWidth: .infinity)
    }
}

private struct ConfidenceLabel: View {
    let value: Double
    var body: some View {
        Label(value.formatted(.percent.precision(.fractionLength(0))),
              systemImage: value >= 0.85 ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
            .foregroundStyle(value >= 0.85 ? Color.green : Color.orange)
            .accessibilityLabel("\(value.formatted(.percent.precision(.fractionLength(0)))) confidence")
    }
}
