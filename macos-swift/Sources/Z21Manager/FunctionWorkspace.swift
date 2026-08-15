import AppKit
import SwiftUI

struct FunctionWorkspace: View {
    @EnvironmentObject private var state: AppState
    @Binding var functions: [FunctionInfo]
    let locomotiveName: String

    @State private var mode: DisplayMode = .grid
    @State private var selection = Set<Int>()
    @State private var searchText = ""
    @FocusState private var focusedNumber: Int?

    private enum DisplayMode: String, CaseIterable, Identifiable {
        case grid = "Grid"
        case table = "Table"
        var id: Self { self }
    }

    private var displayedFunctions: [FunctionInfo] {
        functions
            .filter {
                searchText.isEmpty ||
                "F\($0.number)".localizedCaseInsensitiveContains(searchText) ||
                $0.shortcut.localizedCaseInsensitiveContains(searchText) ||
                $0.imageName.localizedCaseInsensitiveContains(searchText)
            }
            .sorted { $0.number < $1.number }
    }

    private var missingNumbers: [Int] { FunctionMatcher.missingNumbers(functions) }
    private var selectedNumber: Int? { selection.count == 1 ? selection.first : nil }

    var body: some View {
        VStack(spacing: 0) {
            workspaceToolbar
            Divider()
            workspaceContent
        }
        .searchable(text: $searchText, prompt: "Function number, shortcut, or icon")
        .inspector(isPresented: inspectorPresented) {
            if let binding = selectedFunctionBinding {
                FunctionInspector(function: binding, availableIcons: state.availableIcons) {
                    deleteSelection()
                }
                .inspectorColumnWidth(min: 280, ideal: 300, max: 320)
            }
        }
        .onDeleteCommand(perform: deleteSelection)
        .onMoveCommand(perform: moveSelection)
        .onExitCommand {
            focusedNumber = nil
            selection.removeAll()
        }
        .onChange(of: functions.map(\.number)) {
            selection = selection.intersection(Set(functions.map(\.number)))
            if let focusedNumber, !functions.contains(where: { $0.number == focusedNumber }) {
                self.focusedNumber = nil
            }
        }
        .onChange(of: focusedNumber) {
            if let focusedNumber { selection = [focusedNumber] }
        }
    }

    private var workspaceToolbar: some View {
        HStack(spacing: 12) {
            Text("\(functions.count) Functions")
                .font(.headline)

            if !missingNumbers.isEmpty {
                Label(missingLabel, systemImage: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .help("Function numbers are not contiguous")
            }

            Spacer()

            if !selection.isEmpty {
                Menu("Edit \(selection.count)") {
                    Button("Set as Switch") { setBehavior(0) }
                    Button("Set as Push Button") { setBehavior(1) }
                    Button("Set as Timed") { setBehavior(2) }
                    Divider()
                    Button("Delete Selected", role: .destructive, action: deleteSelection)
                }
            }

            Picker("Display", selection: $mode) {
                ForEach(DisplayMode.allCases) { value in
                    Label(value.rawValue, systemImage: value == .grid ? "square.grid.3x3" : "tablecells").tag(value)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(width: 160)

            Menu {
                Button("Scan with iPhone…") { state.captureFromIPhone(functionTable: true) }
                Button("Choose PDF or Image…") { state.chooseDocumentForOCR(functionTable: true) }
                Button("Import Function JSON…", action: state.importFunctionsJSON)
            } label: {
                Label("Scan Table", systemImage: "doc.viewfinder")
            }

            Button(action: addFunction) {
                Label("Add Function", systemImage: "plus")
            }
            .buttonStyle(.borderedProminent)
            .disabled(nextNumber == nil)
        }
        .padding(.vertical, 10)
    }

    @ViewBuilder private var workspaceContent: some View {
        if functions.isEmpty {
            ContentUnavailableView {
                Label("No functions configured", systemImage: "square.grid.3x3")
            } description: {
                Text("Add a function manually or scan a function table from a manual.")
            } actions: {
                Button("Add Function", systemImage: "plus", action: addFunction)
                Menu("Scan Function Table") {
                    Button("Scan with iPhone…") { state.captureFromIPhone(functionTable: true) }
                    Button("Choose PDF or Image…") { state.chooseDocumentForOCR(functionTable: true) }
                }
            }
        } else {
            switch mode {
            case .grid: gridContent
            case .table: tableContent
            }
        }
    }

    private var gridContent: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150, maximum: 210), spacing: 12)], alignment: .leading, spacing: 12) {
                ForEach(displayedFunctions) { function in
                    Button { select(function.number) } label: {
                        FunctionWorkspaceCard(function: function, isSelected: selection.contains(function.number))
                    }
                        .buttonStyle(.plain)
                        .focused($focusedNumber, equals: function.number)
                        .accessibilityAction(named: function.isActive ? "Deactivate Function" : "Activate Function") {
                            toggleActive(function.number)
                        }
                        .contextMenu {
                            Button("Edit") { select(function.number) }
                            Button("Duplicate") { duplicate(function) }
                            Divider()
                            Button("Delete", role: .destructive) { delete(function.number) }
                        }
                }
            }
            .padding(.vertical, 16)
        }
        .accessibilityLabel("Functions Grid")
    }

    private var tableContent: some View {
        ScrollView {
            LazyVStack(spacing: 0, pinnedViews: [.sectionHeaders]) {
                Section {
                    ForEach(displayedFunctions) { function in
                        FunctionTableRow(
                            function: function,
                            isSelected: selection.contains(function.number),
                            isActive: activeBinding(for: function.number),
                            onSelect: { select(function.number) },
                            onToggleActive: { toggleActive(function.number) }
                        )
                        .focusable()
                        .focused($focusedNumber, equals: function.number)
                        .onKeyPress(.return) {
                            select(function.number)
                            return .handled
                        }
                        .onKeyPress(.space) {
                            select(function.number)
                            return .handled
                        }
                        .contextMenu {
                            Button("Duplicate") { duplicate(function) }
                            Button("Delete", role: .destructive) { delete(function.number) }
                        }
                    }
                } header: {
                    FunctionTableHeader()
                }
            }
        }
        .accessibilityLabel("Functions Table")
    }

    private var inspectorPresented: Binding<Bool> {
        Binding(get: { selectedNumber != nil }, set: { if !$0 { selection.removeAll() } })
    }

    private var selectedFunctionBinding: Binding<FunctionInfo>? {
        guard let number = selectedNumber, let index = functions.firstIndex(where: { $0.number == number }) else { return nil }
        return Binding(get: { functions[index] }, set: { functions[index] = $0 })
    }

    private var missingLabel: String {
        let labels = missingNumbers.prefix(4).map { "F\($0)" }.joined(separator: "–")
        return missingNumbers.count > 4 ? "Missing \(labels)…" : "Missing \(labels)"
    }

    private var nextNumber: Int? { (0...127).first { number in !functions.contains { $0.number == number } } }

    private func addFunction() {
        guard let number = nextNumber else { return }
        functions.append(FunctionInfo(number: number, position: functions.count))
        normalizePositions(&functions)
        selection = [number]
    }

    private func duplicate(_ function: FunctionInfo) {
        guard let number = nextNumber else { return }
        var copy = function
        copy.number = number
        copy.position = functions.count
        functions.append(copy)
        normalizePositions(&functions)
        selection = [number]
    }

    private func delete(_ number: Int) {
        functions.removeAll { $0.number == number }
        selection.remove(number)
        normalizePositions(&functions)
    }

    private func deleteSelection() {
        guard !selection.isEmpty else { return }
        functions.removeAll { selection.contains($0.number) }
        selection.removeAll()
        normalizePositions(&functions)
    }

    private func setBehavior(_ value: Int) {
        for index in functions.indices where selection.contains(functions[index].number) {
            functions[index].buttonType = value
            if value == 2, functions[index].time == nil { functions[index].time = 1 }
        }
    }

    private func select(_ number: Int) {
        focusedNumber = number
        if NSEvent.modifierFlags.contains(.command) {
            if selection.contains(number) {
                selection.remove(number)
            } else {
                selection.insert(number)
            }
        } else {
            selection = [number]
        }
    }

    private func moveSelection(_ direction: MoveCommandDirection) {
        let numbers = displayedFunctions.map(\.number)
        let delta: Int
        switch direction {
        case .left, .up: delta = -1
        case .right, .down: delta = 1
        default: return
        }
        if let destination = FunctionKeyboardNavigation.adjacentNumber(
            in: numbers,
            current: focusedNumber ?? selectedNumber,
            offset: delta
        ) {
            select(destination)
        }
    }

    private func toggleActive(_ number: Int) {
        guard let index = functions.firstIndex(where: { $0.number == number }) else { return }
        functions[index].isActive.toggle()
    }

    private func activeBinding(for number: Int) -> Binding<Bool> {
        Binding(
            get: { functions.first(where: { $0.number == number })?.isActive ?? false },
            set: { value in
                if let index = functions.firstIndex(where: { $0.number == number }) { functions[index].isActive = value }
            }
        )
    }
}

enum FunctionKeyboardNavigation {
    static func adjacentNumber(in numbers: [Int], current: Int?, offset: Int) -> Int? {
        guard !numbers.isEmpty else { return nil }
        guard let current, let index = numbers.firstIndex(of: current) else { return numbers[0] }
        return numbers[min(numbers.count - 1, max(0, index + offset))]
    }
}

private struct FunctionWorkspaceCard: View {
    let function: FunctionInfo
    let isSelected: Bool

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("F\(function.number)").font(.headline)
                Spacer()
                Text(function.buttonTypeName).font(.caption).foregroundStyle(.secondary)
            }
            FunctionIcon(function: function).frame(height: 64)
            Text(function.shortcut.isEmpty ? function.imageName : function.shortcut)
                .lineLimit(1)
            if function.buttonType == 2 {
                Text("\(function.time ?? 0, specifier: "%.1f") seconds")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 142)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(isSelected ? Color.accentColor : Color(nsColor: .separatorColor), lineWidth: isSelected ? 2 : 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(FunctionAccessibility.summary(for: function, isSelected: isSelected))
        .accessibilityHint("Activate to select this function")
        .accessibilityAddTraits(.isButton)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

private struct FunctionTableHeader: View {
    var body: some View {
        HStack(spacing: 8) {
            Text("F").frame(width: 45, alignment: .leading)
            Text("Icon").frame(width: 50, alignment: .leading)
            Text("Shortcut").frame(maxWidth: .infinity, alignment: .leading)
            Text("Behavior").frame(width: 110, alignment: .leading)
            Text("Time").frame(width: 70, alignment: .leading)
            Text("Active").frame(width: 55, alignment: .center)
        }
        .font(.caption.weight(.semibold))
        .foregroundStyle(.secondary)
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.bar)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Function table columns: number, icon, shortcut, behavior, time, active")
    }
}

private struct FunctionTableRow: View {
    let function: FunctionInfo
    let isSelected: Bool
    @Binding var isActive: Bool
    let onSelect: () -> Void
    let onToggleActive: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            Button(action: onSelect) {
                HStack(spacing: 8) {
                    Text("F\(function.number)")
                        .fontWeight(.semibold)
                        .frame(width: 45, alignment: .leading)
                    FunctionIcon(function: function)
                        .frame(width: 50, height: 28)
                    Text(function.shortcut.isEmpty ? function.imageName : function.shortcut)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Text(function.buttonTypeName)
                        .frame(width: 110, alignment: .leading)
                    Text(function.buttonType == 2 ? "\(function.time ?? 0, specifier: "%.1f") s" : "—")
                        .foregroundStyle(function.buttonType == 2 ? .primary : .secondary)
                        .frame(width: 70, alignment: .leading)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(FunctionAccessibility.summary(for: function, isSelected: isSelected))
            .accessibilityHint("Activate to select this function")
            .accessibilityAddTraits(isSelected ? .isSelected : [])
            Toggle("F\(function.number) Active", isOn: $isActive)
                .labelsHidden()
                .frame(width: 55)
        }
        .padding(.horizontal, 10)
        .frame(minHeight: 42)
        .background(isSelected ? Color.accentColor.opacity(0.16) : Color.clear)
        .accessibilityElement(children: .contain)
        .accessibilityAction(named: function.isActive ? "Deactivate Function" : "Activate Function", onToggleActive)
        .overlay(alignment: .bottom) { Divider() }
    }
}

enum FunctionAccessibility {
    static func summary(for function: FunctionInfo, isSelected: Bool) -> String {
        let name = function.shortcut.isEmpty ? function.imageName : function.shortcut
        var parts = ["F\(function.number)", name, function.buttonTypeName]
        if function.buttonType == 2 {
            parts.append("\(String(format: "%.1f", function.time ?? 0)) seconds")
        }
        parts.append(function.isActive ? "active" : "inactive")
        if isSelected { parts.append("selected") }
        return parts.joined(separator: ", ")
    }
}

private struct FunctionIcon: View {
    let function: FunctionInfo

    var body: some View {
        Group {
            if let url = IconCatalog.url(named: function.imageName), let image = NSImage(contentsOf: url) {
                Image(nsImage: image).resizable().interpolation(.high).scaledToFit()
            } else {
                Image(systemName: "questionmark.square.dashed").font(.title2).foregroundStyle(.secondary)
            }
        }
        .accessibilityHidden(true)
    }
}

private struct FunctionInspector: View {
    @Binding var function: FunctionInfo
    let availableIcons: [String]
    let onDelete: () -> Void

    var body: some View {
        Form {
            Section("Function F\(function.number)") {
                LabeledContent("Number", value: "F\(function.number)")
                Picker("Icon", selection: $function.imageName) {
                    ForEach(availableIcons, id: \.self, content: Text.init)
                }
                TextField("Shortcut", text: $function.shortcut)
            }
            Section("Behavior") {
                Picker("Type", selection: $function.buttonType) {
                    Text("Switch").tag(0)
                    Text("Push Button").tag(1)
                    Text("Timed").tag(2)
                }
                if function.buttonType == 2 {
                    TextField("Time (seconds)", value: timedValue, format: .number)
                }
                Toggle("Active", isOn: $function.isActive)
            }
            Section {
                Button("Delete Function", role: .destructive, action: onDelete)
            }
        }
        .formStyle(.grouped)
    }

    private var timedValue: Binding<Double> {
        Binding(get: { function.time ?? 1 }, set: { function.time = max(0, $0) })
    }
}
