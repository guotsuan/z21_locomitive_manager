import AppKit
import SwiftUI

struct LocomotiveHeader: View {
    @EnvironmentObject private var state: AppState
    @Binding var locomotive: Locomotive
    private let contentHeight: CGFloat = 120

    var body: some View {
        HStack(spacing: DesignTokens.pagePadding) {
            LocomotiveImage(locomotive: locomotive)
                .frame(maxWidth: .infinity)
                .frame(height: contentHeight)
                .overlay(alignment: .bottomTrailing) {
                    Button(action: state.importLocomotiveImage) {
                        Image(systemName: "photo.badge.plus")
                    }
                    .buttonStyle(.bordered)
                    .buttonBorderShape(.circle)
                    .help("Change Locomotive Image")
                    .accessibilityLabel("Change Locomotive Image")
                    .padding(6)
                }

            HStack(alignment: .top, spacing: DesignTokens.contentSpacing) {
                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(locomotive.name.isEmpty ? "Unnamed Locomotive" : locomotive.name)
                            .font(.title2)
                            .fontWeight(.semibold)
                            .lineLimit(1)
                        if !locomotive.fullName.isEmpty {
                            Text(locomotive.fullName)
                                .font(.callout)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                    }

                    Spacer(minLength: 6)

                    HStack(spacing: 8) {
                        Label("Address \(locomotive.address)", systemImage: "number")
                        Text(locomotive.primaryCategory)
                        Text(locomotive.active ? "Active" : "Inactive")
                    }
                    .font(.body)
                    .fontWeight(.medium)
                    .foregroundStyle(.secondary)

                    Spacer(minLength: 8)
                    Divider()

                    Spacer(minLength: 8)
                    HStack(spacing: 28) {
                        fact("Max Speed", "\(locomotive.speed) km/h")
                        fact("Direction", locomotive.direction ? "Forward" : "Reverse")
                        fact("Decoder", locomotive.decoderType.isEmpty ? "Not set" : locomotive.decoderType)
                    }
                }
                .frame(height: contentHeight)
                .frame(maxWidth: .infinity, alignment: .leading)

                VStack(alignment: .trailing, spacing: 12) {
                    Toggle("Active", isOn: $locomotive.active)
                    saveStatus
                    Button("Save", systemImage: "checkmark") { state.save() }
                        .buttonStyle(.borderedProminent)
                        .disabled(!state.isDirty || state.isBusy)
                        .keyboardShortcut("s")
                }
                .fixedSize(horizontal: true, vertical: false)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(DesignTokens.contentSpacing)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: DesignTokens.imageCornerRadius))
        .accessibilityElement(children: .contain)
    }

    private var saveStatus: some View {
        Group {
            if state.isBusy {
                HStack(spacing: 6) {
                    ProgressView().controlSize(.small)
                    Text("Working…")
                }
            } else if state.isDirty {
                Label("Unsaved Changes", systemImage: "circle.fill")
                    .foregroundStyle(.orange)
            } else {
                Label("Saved", systemImage: "checkmark.circle")
                    .foregroundStyle(.secondary)
            }
        }
        .font(.caption)
        .accessibilityLabel(state.isDirty ? "Unsaved changes for \(locomotive.name)" : "Saved")
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(.callout)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.body)
                .fontWeight(.semibold)
                .lineLimit(1)
        }
    }
}

struct LocomotiveImage: View {
    @EnvironmentObject private var state: AppState
    let locomotive: Locomotive

    var body: some View {
        Group {
            if let url = state.imageURL(for: locomotive), let image = NSImage(contentsOf: url) {
                Image(nsImage: image).resizable().scaledToFit()
            } else {
                ZStack {
                    RoundedRectangle(cornerRadius: DesignTokens.imageCornerRadius).fill(.quaternary)
                    Image(systemName: "tram.fill").font(.system(size: 46)).foregroundStyle(.secondary)
                }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: DesignTokens.imageCornerRadius))
        .accessibilityLabel("Image of \(locomotive.name)")
    }
}
