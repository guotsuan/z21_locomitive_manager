import SwiftUI

struct OverviewWorkspace: View {
    @Binding var locomotive: Locomotive
    @State private var categoryDraft = ""
    @State private var showingAddCategory = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DesignTokens.sectionSpacing) {
                identitySection
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: DesignTokens.sectionSpacing) {
                        productSection.frame(minWidth: 380)
                        technicalSection.frame(minWidth: 380)
                    }
                    VStack(spacing: DesignTokens.sectionSpacing) {
                        productSection
                        technicalSection
                    }
                }
                classificationSection
            }
            .frame(maxWidth: DesignTokens.detailMaxWidth)
            .frame(maxWidth: .infinity)
            .padding(.vertical, DesignTokens.contentSpacing)
        }
        .alert("Add New Category", isPresented: $showingAddCategory) {
            TextField("Category name", text: $categoryDraft)
            Button("Cancel", role: .cancel) { categoryDraft = "" }
            Button("Add", action: addCategory)
                .disabled(categoryDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        } message: {
            Text("Enter a short English Title Case category name.")
        }
    }

    private var identitySection: some View {
        GroupBox("Identity & Operation") {
            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 12) {
                GridRow {
                    field("Name", text: $locomotive.name, error: nameError)
                    numberField("Address", value: $locomotive.address, error: addressError)
                }
                GridRow {
                    numberField("Max Speed", value: $locomotive.speed, suffix: "km/h", error: speedError)
                    labeled("Direction") {
                        Picker("Direction", selection: $locomotive.direction) {
                            Text("Forward").tag(true)
                            Text("Reverse").tag(false)
                        }
                        .labelsHidden()
                    }
                }
                GridRow {
                    Toggle("Active", isOn: $locomotive.active)
                    Toggle("Crane", isOn: $locomotive.crane)
                }
            }
            .textFieldStyle(.roundedBorder)
            .padding(8)
        }
    }

    private var productSection: some View {
        GroupBox("Product") {
            VStack(spacing: 12) {
                field("Full Name", text: $locomotive.fullName)
                field("Railway", text: $locomotive.railway)
                field("Article Number", text: $locomotive.articleNumber)
                field("Decoder / Interface", text: $locomotive.decoderType)
                field("Build Year", text: $locomotive.buildYear, prompt: "YYYY")
                field("In Stock Since", text: $locomotive.inStockSince, prompt: "YYYY-MM-DD")
                categoriesField
                labeled("Vehicle Type") {
                    Picker("Vehicle Type", selection: $locomotive.railVehicleType) {
                        Text("Loco").tag(0); Text("Wagon").tag(1); Text("Accessory").tag(2)
                    }.labelsHidden()
                }
            }
            .textFieldStyle(.roundedBorder)
            .padding(8)
        }
    }

    private var technicalSection: some View {
        GroupBox("Technical Data") {
            VStack(spacing: 12) {
                field("Buffer Length", text: $locomotive.bufferLength)
                field("Model Buffer Length", text: $locomotive.modelBufferLength)
                field("Service Weight", text: $locomotive.serviceWeight)
                field("Model Weight", text: $locomotive.modelWeight)
                field("Minimum Radius", text: $locomotive.rmin)
                field("IP Address", text: $locomotive.ip)
                field("Driver’s Cab", text: $locomotive.driversCab)
                labeled("Speed Display") {
                    Picker("Speed Display", selection: $locomotive.speedDisplay) {
                        Text("km/h").tag(0); Text("Regulation Step").tag(1); Text("mph").tag(2)
                    }.labelsHidden()
                }
                labeled("Regulation Step") {
                    Picker("Regulation Step", selection: $locomotive.regulationStep) {
                        Text("128").tag(0); Text("28").tag(1); Text("14").tag(2)
                    }.labelsHidden()
                }
            }
            .textFieldStyle(.roundedBorder)
            .padding(8)
        }
    }

    private var classificationSection: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 12) {
                Text("Description").font(.caption).foregroundStyle(.secondary)
                TextEditor(text: $locomotive.description)
                    .font(.body)
                    .frame(minHeight: 110)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(.separator))
            }
            .padding(8)
        }
    }

    private var categoriesField: some View {
        labeled("Categories") {
            VStack(alignment: .leading, spacing: 8) {
                Menu {
                    ForEach(LocomotiveValidator.defaultCategories, id: \.self) { category in
                        Button {
                            toggleCategory(category)
                        } label: {
                            Label(category, systemImage: hasCategory(category) ? "checkmark" : "circle")
                        }
                    }
                    Divider()
                    Button {
                        categoryDraft = ""
                        showingAddCategory = true
                    } label: {
                        Label("Add New…", systemImage: "plus")
                    }
                } label: {
                    HStack {
                        Text(categorySelectionLabel)
                            .foregroundStyle(locomotive.categories.isEmpty ? .secondary : .primary)
                            .lineLimit(1)
                        Spacer()
                        Image(systemName: "chevron.up.chevron.down")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.horizontal, 8)
                    .frame(height: 26)
                    .background(.background, in: RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(.separator))
                }
                .menuStyle(.borderlessButton)
                .accessibilityLabel("Categories")
                .accessibilityValue(categorySelectionLabel)

                if !locomotive.categories.isEmpty {
                    ScrollView(.horizontal) {
                        HStack(spacing: 6) {
                            ForEach(locomotive.categories, id: \.self) { category in
                                HStack(spacing: 4) {
                                    Text(category)
                                    Button { removeCategory(category) } label: {
                                        Image(systemName: "xmark.circle.fill")
                                    }
                                    .buttonStyle(.plain)
                                    .accessibilityLabel("Remove category \(category)")
                                }
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(.quaternary, in: Capsule())
                            }
                        }
                    }
                    .scrollIndicators(.hidden)
                }
            }
        }
    }

    private func addCategory() {
        let value = categoryDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty, !hasCategory(value) else {
            categoryDraft = ""
            return
        }
        locomotive.categories = LocomotiveValidator.normalizeCategories(locomotive.categories + [value])
        categoryDraft = ""
    }

    private var categorySelectionLabel: String {
        locomotive.categories.isEmpty ? "Select categories" : locomotive.categories.joined(separator: ", ")
    }

    private func hasCategory(_ category: String) -> Bool {
        locomotive.categories.contains { $0.caseInsensitiveCompare(category) == .orderedSame }
    }

    private func toggleCategory(_ category: String) {
        if hasCategory(category) {
            removeCategory(category)
        } else {
            locomotive.categories = LocomotiveValidator.normalizeCategories(locomotive.categories + [category])
        }
    }

    private func removeCategory(_ category: String) {
        locomotive.categories.removeAll { $0.caseInsensitiveCompare(category) == .orderedSame }
    }

    private var nameError: String? {
        locomotive.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "Name is required." : nil
    }
    private var addressError: String? { (1...9999).contains(locomotive.address) ? nil : "Use an address from 1 to 9999." }
    private var speedError: String? { (0...999).contains(locomotive.speed) ? nil : "Use a speed from 0 to 999." }

    private func field(_ label: String, text: Binding<String>, prompt: String = "", error: String? = nil) -> some View {
        labeled(label, error: error) { TextField(prompt, text: text) }
    }

    private func numberField(_ label: String, value: Binding<Int>, suffix: String? = nil, error: String? = nil) -> some View {
        labeled(label, error: error) {
            HStack {
                TextField(label, value: value, format: .number)
                if let suffix { Text(suffix).foregroundStyle(.secondary) }
            }
        }
    }

    private func labeled<Content: View>(_ label: String, error: String? = nil, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label).font(.caption).foregroundStyle(.secondary)
            content()
            if let error {
                Label(error, systemImage: "exclamationmark.circle.fill")
                    .font(.caption2)
                    .foregroundStyle(.red)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
