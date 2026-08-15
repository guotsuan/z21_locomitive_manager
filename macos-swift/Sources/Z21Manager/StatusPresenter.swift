import SwiftUI

enum AppStatusKind: Equatable {
    case information
    case working
    case success
    case warning
    case failure

    var symbolName: String {
        switch self {
        case .information: "info.circle"
        case .working: "arrow.triangle.2.circlepath"
        case .success: "checkmark.circle.fill"
        case .warning: "exclamationmark.triangle.fill"
        case .failure: "xmark.octagon.fill"
        }
    }
}

struct AppStatus {
    var kind: AppStatusKind
    var message: String

    static func information(_ message: String) -> Self { .init(kind: .information, message: message) }
    static func working(_ message: String) -> Self { .init(kind: .working, message: message) }
    static func success(_ message: String) -> Self { .init(kind: .success, message: message) }
    static func warning(_ message: String) -> Self { .init(kind: .warning, message: message) }
    static func failure(_ message: String) -> Self { .init(kind: .failure, message: message) }
}

struct StatusPresenter: View {
    @EnvironmentObject private var state: AppState

    private var displayStatus: AppStatus {
        if state.isBusy { return .working(state.appStatus.message) }
        if state.isDirty, state.appStatus.kind == .information { return .warning(state.appStatus.message) }
        return state.appStatus
    }

    var body: some View {
        HStack(spacing: 8) {
            if displayStatus.kind == .working {
                ProgressView().controlSize(.small)
            } else {
                Image(systemName: displayStatus.kind.symbolName)
                    .foregroundStyle(statusColor)
            }
            Text(displayStatus.message)
                .font(.caption)
                .lineLimit(1)
            Spacer()
            if state.isDirty {
                Label("Unsaved changes", systemImage: "circle.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
            Text("\(state.locomotives.count) locomotives")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.bar)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityText)
        .accessibilityAddTraits(.updatesFrequently)
    }

    private var statusColor: Color {
        switch displayStatus.kind {
        case .success: .green
        case .warning: .orange
        case .failure: .red
        default: .secondary
        }
    }

    private var accessibilityText: String {
        displayStatus.message + (state.isDirty ? ". Unsaved changes." : ". All changes saved.")
    }
}
