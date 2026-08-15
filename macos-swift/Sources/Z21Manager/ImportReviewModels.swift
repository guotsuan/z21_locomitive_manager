import Foundation

enum ImportReviewStage: String {
    case ocrText
    case fieldChanges
    case functionChanges
    case jsonFieldChanges
    case jsonFunctionChanges

    var title: String {
        switch self {
        case .ocrText: "Review Recognized Text"
        case .fieldChanges, .jsonFieldChanges: "Review Detail Changes"
        case .functionChanges, .jsonFunctionChanges: "Review Function Changes"
        }
    }
}

struct ImportReviewSession: Identifiable {
    let id = UUID()
    let source: String
    let targetID: UUID
    let target: String
    var stage: ImportReviewStage
}

struct ImportFieldChange: Identifiable, Hashable {
    let id: String
    let label: String
    let current: String
    let proposed: String
}
