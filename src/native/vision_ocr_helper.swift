import AppKit
import Foundation
import PDFKit
import Vision

private struct Arguments {
    let input: URL
    let config: URL
    let output: URL

    static func parse() -> Arguments? {
        let arguments = CommandLine.arguments
        guard let input = value(after: "--input", in: arguments),
              let config = value(after: "--config", in: arguments),
              let output = value(after: "--output", in: arguments) else {
            return nil
        }
        return Arguments(
            input: URL(fileURLWithPath: input),
            config: URL(fileURLWithPath: config),
            output: URL(fileURLWithPath: output)
        )
    }

    private static func value(after flag: String,
                              in arguments: [String]) -> String? {
        guard let index = arguments.firstIndex(of: flag),
              arguments.indices.contains(index + 1) else { return nil }
        return arguments[index + 1]
    }
}

private struct Configuration: Decodable {
    let languages: [String]
    let customWords: [String]
}

private struct BoundingBox: Encodable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

private struct Candidate: Encodable {
    let text: String
    let confidence: Float
}

private struct Observation: Encodable {
    let text: String
    let confidence: Float
    let boundingBox: BoundingBox
    let candidates: [Candidate]
}

private struct PageResult: Encodable {
    let index: Int
    let width: Double
    let height: Double
    let observations: [Observation]
}

private struct SuccessResult: Encodable {
    let status = "ok"
    let engine = "apple-vision"
    let languages: [String]
    let pages: [PageResult]
}

private enum HelperError: LocalizedError {
    case invalidConfiguration
    case unreadableInput
    case unreadablePDFPage(Int)

    var errorDescription: String? {
        switch self {
        case .invalidConfiguration:
            return "The Apple Vision OCR configuration is invalid."
        case .unreadableInput:
            return "The input is not a readable image or PDF."
        case .unreadablePDFPage(let index):
            return "Unable to render PDF page \(index + 1)."
        }
    }
}

private struct InputPage {
    let index: Int
    let image: CGImage
}

private func loadConfiguration(from URL: URL) throws -> Configuration {
    let data = try Data(contentsOf: URL)
    guard let configuration = try? JSONDecoder().decode(
        Configuration.self, from: data
    ) else {
        throw HelperError.invalidConfiguration
    }
    return configuration
}

private func cgImage(from image: NSImage) -> CGImage? {
    var rect = NSRect(origin: .zero, size: image.size)
    return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

private func loadPages(from URL: URL) throws -> [InputPage] {
    if URL.pathExtension.lowercased() == "pdf" {
        guard let document = PDFDocument(url: URL) else {
            throw HelperError.unreadableInput
        }
        return try (0..<document.pageCount).map { index in
            guard let page = document.page(at: index) else {
                throw HelperError.unreadablePDFPage(index)
            }
            let bounds = page.bounds(for: .mediaBox)
            let longestSide = max(bounds.width, bounds.height)
            let scale = max(1.0, min(4.0, 4096.0 / longestSide))
            let size = NSSize(width: bounds.width * scale,
                              height: bounds.height * scale)
            let image = page.thumbnail(of: size, for: .mediaBox)
            guard let rendered = cgImage(from: image) else {
                throw HelperError.unreadablePDFPage(index)
            }
            return InputPage(index: index, image: rendered)
        }
    }

    guard let image = NSImage(contentsOf: URL),
          let rendered = cgImage(from: image) else {
        throw HelperError.unreadableInput
    }
    return [InputPage(index: 0, image: rendered)]
}

private func recognize(page: InputPage,
                       configuration: Configuration) throws -> PageResult {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.automaticallyDetectsLanguage = true
    request.customWords = configuration.customWords

    let supportedLanguages = try request.supportedRecognitionLanguages()
    let languages = configuration.languages.filter {
        supportedLanguages.contains($0)
    }
    if !languages.isEmpty {
        request.recognitionLanguages = languages
    }

    let handler = VNImageRequestHandler(cgImage: page.image, options: [:])
    try handler.perform([request])
    let recognized = request.results ?? []
    let observations = recognized.compactMap { item -> Observation? in
        let candidates = item.topCandidates(3).map {
            Candidate(text: $0.string, confidence: $0.confidence)
        }
        guard let top = candidates.first else { return nil }
        let box = item.boundingBox
        return Observation(
            text: top.text,
            confidence: top.confidence,
            boundingBox: BoundingBox(
                x: box.origin.x,
                y: box.origin.y,
                width: box.width,
                height: box.height
            ),
            candidates: candidates
        )
    }
    return PageResult(
        index: page.index,
        width: Double(page.image.width),
        height: Double(page.image.height),
        observations: observations
    )
}

private func run(arguments: Arguments) throws {
    let configuration = try loadConfiguration(from: arguments.config)
    let pages = try loadPages(from: arguments.input)
    let pageResults = try pages.map {
        try recognize(page: $0, configuration: configuration)
    }
    let result = SuccessResult(
        languages: configuration.languages,
        pages: pageResults
    )
    let data = try JSONEncoder().encode(result)
    try data.write(to: arguments.output, options: .atomic)
}

guard let arguments = Arguments.parse() else {
    fputs("Usage: vision-ocr-helper --input PATH --config PATH --output PATH\n",
          stderr)
    exit(2)
}

do {
    try run(arguments: arguments)
} catch {
    fputs("Apple Vision OCR failed: \(error.localizedDescription)\n", stderr)
    exit(1)
}
