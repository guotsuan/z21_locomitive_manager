import Foundation

struct OCRAIService: Sendable {
    func recognize(_ url: URL) async throws -> OCRResult {
        try await Task.detached(priority: .userInitiated) {
            try AppleVisionOCR.recognize(url)
        }.value
    }

    func extractFields(text: String, existing: Locomotive) async throws -> [FieldProposal] {
        guard let key = try DeepSeekKeychain.get() else {
            throw Z21Error.service("Add a DeepSeek API key in Settings first.")
        }
        return try await DeepSeekService(apiKey: key).extractFields(text: text, existing: existing)
    }

    func extractFunctions(result: OCRResult, availableIcons: [String]) async throws -> [FunctionProposal] {
        guard let key = try DeepSeekKeychain.get() else {
            throw Z21Error.service("Add a DeepSeek API key in Settings first.")
        }
        return try await DeepSeekService(apiKey: key).extractFunctions(
            result: result,
            availableIcons: availableIcons
        )
    }
}
