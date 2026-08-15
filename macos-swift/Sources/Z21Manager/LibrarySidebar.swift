import SwiftUI

struct LibrarySidebar: View {
    @EnvironmentObject private var state: AppState
    @State private var activeOnly = false
    @State private var hasImageOnly = false
    @State private var hasFunctionsOnly = false
    @State private var category: String?
    @State private var confirmingDeletion = false
    @State private var searchIsPresented = false

    private var visibleLocomotives: [Locomotive] {
        state.filteredLocomotives.filter { locomotive in
            (!activeOnly || locomotive.active) &&
            (!hasImageOnly || !locomotive.imageName.isEmpty) &&
            (!hasFunctionsOnly || !locomotive.functions.isEmpty) &&
            (category == nil || locomotive.categories.contains(category!))
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            filterBar
            List(visibleLocomotives, selection: $state.selection) { locomotive in
                LocomotiveRow(locomotive: locomotive)
                    .tag(locomotive.id)
                    .contextMenu {
                        Button("Delete Locomotive…", role: .destructive) {
                            state.selection = locomotive.id
                            confirmingDeletion = true
                        }
                    }
            }
            Divider()
            bottomBar
        }
        .searchable(text: $state.searchText, isPresented: $searchIsPresented, prompt: "Name or address")
        .navigationTitle(state.fileURL?.deletingPathExtension().lastPathComponent ?? "Locomotive Library")
        .onReceive(NotificationCenter.default.publisher(for: .focusLibrarySearch)) { _ in
            searchIsPresented = true
        }
        .onReceive(NotificationCenter.default.publisher(for: .requestLocomotiveDeletion)) { _ in
            if state.selected != nil { confirmingDeletion = true }
        }
        .alert("Delete Locomotive?", isPresented: $confirmingDeletion) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive, action: state.deleteSelected)
        } message: {
            Text("\(state.selected?.name ?? "This locomotive") will be removed from the draft. Save the archive to persist the deletion.")
        }
    }

    private var filterBar: some View {
        HStack {
            Text("Library")
                .font(.headline)
            Spacer()
            Menu {
                Toggle("Active", isOn: $activeOnly)
                Toggle("Has Image", isOn: $hasImageOnly)
                Toggle("Has Functions", isOn: $hasFunctionsOnly)
                Divider()
                Button("All Categories") { category = nil }
                ForEach(LocomotiveValidator.defaultCategories, id: \.self) { value in
                    Button {
                        category = value
                    } label: {
                        if category == value { Label(value, systemImage: "checkmark") }
                        else { Text(value) }
                    }
                }
            } label: {
                Label("Filter", systemImage: filtersAreActive ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                    .labelStyle(.iconOnly)
            }
            .menuStyle(.borderlessButton)
            .help("Filter Locomotives")
            .accessibilityLabel("Filter Locomotives")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    private var bottomBar: some View {
        VStack(alignment: .leading, spacing: DesignTokens.compactSpacing) {
            Text(resultCount)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.85)

            HStack(spacing: DesignTokens.compactSpacing) {
                Button(action: state.addLocomotive) {
                    Label("New", systemImage: "plus")
                        .frame(maxWidth: .infinity)
                }
                .keyboardShortcut("n")
                .help("New Locomotive")
                .accessibilityLabel("New Locomotive")
                .frame(maxWidth: .infinity)

                Button(role: .destructive) { confirmingDeletion = true } label: {
                    Label("Delete", systemImage: "trash")
                        .frame(maxWidth: .infinity)
                }
                .disabled(state.selected == nil)
                .help("Delete Locomotive")
                .accessibilityLabel("Delete Locomotive")
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.regular)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
    }

    private var filtersAreActive: Bool {
        activeOnly || hasImageOnly || hasFunctionsOnly || category != nil
    }

    private var resultCount: String {
        if visibleLocomotives.count == state.locomotives.count {
            return "\(state.locomotives.count) locomotives"
        }
        return "\(visibleLocomotives.count) of \(state.locomotives.count)"
    }
}

private struct LocomotiveRow: View {
    let locomotive: Locomotive

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: locomotive.symbolName)
                .frame(width: 22)
                .foregroundStyle(locomotive.active ? Color.accentColor : Color.secondary)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(locomotive.name.isEmpty ? "Unnamed" : locomotive.name)
                        .fontWeight(.medium)
                        .lineLimit(1)
                    if !locomotive.active {
                        Text("Inactive")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                Text("#\(locomotive.address) · \(locomotive.primaryCategory) · \(locomotive.functions.count) functions")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(.vertical, 3)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(locomotive.name), address \(locomotive.address), \(locomotive.primaryCategory), \(locomotive.active ? "active" : "inactive"), \(locomotive.functions.count) functions")
    }
}

extension Locomotive {
    var primaryCategory: String { categories.first ?? "Uncategorized" }

    var symbolName: String {
        switch primaryCategory.lowercased() {
        case "steam": return "cloud.fill"
        case "electrical": return "bolt.fill"
        case "diesel": return "fuelpump.fill"
        case "train bus": return "bus.fill"
        default: return "tram.fill"
        }
    }
}
