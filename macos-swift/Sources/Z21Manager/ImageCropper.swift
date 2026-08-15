import AppKit
import SwiftUI

enum ImageCropper {
    static func crop(_ source: URL, normalized: CGRect) throws -> URL {
        guard let image = NSImage(contentsOf: source) else { throw Z21Error.service("Unable to read the selected image.") }
        var proposed = NSRect(origin: .zero, size: image.size)
        guard let cgImage = image.cgImage(forProposedRect: &proposed, context: nil, hints: nil) else {
            throw Z21Error.service("Unable to render the selected image.")
        }
        let x = max(0, min(CGFloat(cgImage.width - 1), normalized.minX * CGFloat(cgImage.width)))
        let y = max(0, min(CGFloat(cgImage.height - 1), normalized.minY * CGFloat(cgImage.height)))
        let width = max(1, min(CGFloat(cgImage.width) - x, normalized.width * CGFloat(cgImage.width)))
        let height = max(1, min(CGFloat(cgImage.height) - y, normalized.height * CGFloat(cgImage.height)))
        guard let cropped = cgImage.cropping(to: CGRect(x: x, y: y, width: width, height: height)) else {
            throw Z21Error.service("The crop area is invalid.")
        }
        let bitmap = NSBitmapImageRep(cgImage: cropped)
        guard let data = bitmap.representation(using: .png, properties: [:]) else {
            throw Z21Error.service("Unable to encode the cropped image.")
        }
        let target = FileManager.default.temporaryDirectory.appendingPathComponent("loco-\(UUID().uuidString).png")
        try data.write(to: target, options: .atomic)
        return target
    }
}

struct ImageCropView: View {
    @EnvironmentObject private var state: AppState
    @Environment(\.dismiss) private var dismiss
    let source: URL
    @State private var left = 0.05
    @State private var top = 0.05
    @State private var width = 0.90
    @State private var height = 0.90

    private var selection: CGRect {
        CGRect(x: left, y: top, width: min(width, 1 - left), height: min(height, 1 - top))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Crop Locomotive Image").font(.title2).fontWeight(.semibold)
            if let image = NSImage(contentsOf: source) {
                GeometryReader { proxy in
                    let fit = fittedRect(imageSize: image.size, in: proxy.size)
                    ZStack(alignment: .topLeading) {
                        Image(nsImage: image).resizable().scaledToFit().frame(width: proxy.size.width, height: proxy.size.height)
                        Rectangle().stroke(Color.accentColor, lineWidth: 3)
                            .background(Color.accentColor.opacity(0.08))
                            .frame(width: fit.width * selection.width, height: fit.height * selection.height)
                            .offset(x: fit.minX + fit.width * selection.minX, y: fit.minY + fit.height * selection.minY)
                    }
                }.frame(minHeight: 360).background(.black.opacity(0.06), in: RoundedRectangle(cornerRadius: 8))
            }
            Grid(alignment: .leading) {
                slider("Left", value: $left, limit: max(0, 1 - width))
                slider("Top", value: $top, limit: max(0, 1 - height))
                slider("Width", value: $width, limit: max(0.05, 1 - left), minimum: 0.05)
                slider("Height", value: $height, limit: max(0.05, 1 - top), minimum: 0.05)
            }
            HStack {
                Button("Cancel") { dismiss() }
                Spacer()
                Button("Use Full Image") { left = 0; top = 0; width = 1; height = 1 }
                Button("Save Crop") { state.applyCroppedImage(source, rect: selection); dismiss() }.keyboardShortcut(.defaultAction)
            }
        }.padding(22).frame(minWidth: 720, minHeight: 620)
    }

    private func slider(_ label: String, value: Binding<Double>, limit: Double, minimum: Double = 0) -> some View {
        GridRow { Text(label).frame(width: 55, alignment: .trailing); Slider(value: value, in: minimum...max(minimum, limit)); Text(value.wrappedValue, format: .percent.precision(.fractionLength(0))).frame(width: 45) }
    }

    private func fittedRect(imageSize: CGSize, in available: CGSize) -> CGRect {
        let scale = min(available.width / imageSize.width, available.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(x: (available.width - size.width) / 2, y: (available.height - size.height) / 2,
                      width: size.width, height: size.height)
    }
}
