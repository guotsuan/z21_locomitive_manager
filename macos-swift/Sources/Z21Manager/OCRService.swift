import AppKit
import Foundation
import PDFKit
import Vision

struct OCRBoundingBox: Codable, Hashable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct OCRObservation: Codable, Hashable, Identifiable {
    let id = UUID()
    let text: String
    let confidence: Float
    let boundingBox: OCRBoundingBox

    enum CodingKeys: String, CodingKey { case text, confidence, boundingBox }
}

struct OCRPage: Codable, Hashable {
    let index: Int
    let width: Int
    let height: Int
    let observations: [OCRObservation]

    var text: String {
        observations.sorted {
            if abs($0.boundingBox.y - $1.boundingBox.y) > 0.025 {
                return $0.boundingBox.y > $1.boundingBox.y
            }
            return $0.boundingBox.x < $1.boundingBox.x
        }.map(\.text).joined(separator: "\n")
    }
}

struct OCRResult: Codable, Hashable {
    let engine: String
    let languages: [String]
    let pages: [OCRPage]
    var text: String { pages.map(\.text).joined(separator: "\n\n") }
}

enum AppleVisionOCR {
    static let languages = ["de-DE", "en-US", "fr-FR"]
    static let railwayWords = [
        "DCC", "RailCom", "PluX22", "NEM 652", "SUSI", "Roco", "Z21",
        "Bremsenquietschen", "Führerstand", "Pantograph", "Kupplung"
    ] + (0...32).map { "F\($0)" }

    static func recognize(_ url: URL) throws -> OCRResult {
        let images = try loadImages(url)
        let pages = try images.enumerated().map { index, image -> OCRPage in
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true
            request.automaticallyDetectsLanguage = true
            request.customWords = railwayWords
            let supported = try request.supportedRecognitionLanguages()
            let selected = languages.filter(supported.contains)
            if !selected.isEmpty { request.recognitionLanguages = selected }
            try VNImageRequestHandler(cgImage: image).perform([request])
            let observations = (request.results ?? []).compactMap { item -> OCRObservation? in
                guard let candidate = item.topCandidates(1).first else { return nil }
                let box = item.boundingBox
                return OCRObservation(
                    text: candidate.string,
                    confidence: candidate.confidence,
                    boundingBox: OCRBoundingBox(x: box.origin.x, y: box.origin.y,
                                                width: box.width, height: box.height))
            }
            return OCRPage(index: index, width: image.width, height: image.height,
                           observations: observations)
        }
        return OCRResult(engine: "apple-vision", languages: languages, pages: pages)
    }

    private static func loadImages(_ url: URL) throws -> [CGImage] {
        if url.pathExtension.lowercased() == "pdf" {
            guard let document = PDFDocument(url: url) else {
                throw Z21Error.service("The selected PDF could not be read.")
            }
            return try (0..<document.pageCount).map { index in
                guard let page = document.page(at: index) else {
                    throw Z21Error.service("PDF page \(index + 1) could not be read.")
                }
                let bounds = page.bounds(for: .mediaBox)
                let scale = min(4, max(1, 4096 / max(bounds.width, bounds.height)))
                let image = page.thumbnail(
                    of: NSSize(width: bounds.width * scale, height: bounds.height * scale),
                    for: .mediaBox)
                return try cgImage(image)
            }
        }
        guard let image = NSImage(contentsOf: url) else {
            throw Z21Error.service("The selected image could not be read.")
        }
        return [try cgImage(image)]
    }

    private static func cgImage(_ image: NSImage) throws -> CGImage {
        var rect = NSRect(origin: .zero, size: image.size)
        guard let result = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
            throw Z21Error.service("Unable to render the selected document.")
        }
        return result
    }
}
