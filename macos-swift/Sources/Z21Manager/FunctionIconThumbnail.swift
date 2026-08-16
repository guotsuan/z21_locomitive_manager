import AppKit
import SwiftUI

struct FunctionIconThumbnail: View {
    let iconName: String
    let size: CGFloat

    var body: some View {
        Group {
            if let image = thumbnailImage {
                Image(nsImage: image)
            } else {
                Image(systemName: "questionmark.square.dashed")
                    .foregroundStyle(.secondary)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }

    private var thumbnailImage: NSImage? {
        guard let url = IconCatalog.url(named: iconName),
              let source = NSImage(contentsOf: url),
              let copy = source.copy() as? NSImage else { return nil }
        copy.size = NSSize(width: size, height: size)
        return copy
    }
}
