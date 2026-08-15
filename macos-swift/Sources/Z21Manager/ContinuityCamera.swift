import AppKit
import Foundation

private final class CaptureTextView: NSTextView {
    var received: ((NSPasteboard) -> Bool)?

    override func validRequestor(forSendType sendType: NSPasteboard.PasteboardType?,
                                 returnType: NSPasteboard.PasteboardType?) -> Any? {
        if let returnType,
           returnType == .pdf || returnType == .fileURL || NSImage.imageTypes.contains(returnType.rawValue) {
            return self
        }
        return super.validRequestor(forSendType: sendType, returnType: returnType)
    }

    override func readSelection(from pasteboard: NSPasteboard) -> Bool {
        received?(pasteboard) == true || super.readSelection(from: pasteboard)
    }
}

/// Bridges AppKit's system-provided Continuity Camera menu to the SwiftUI app.
/// macOS requires the user to choose a nearby device from that menu, but no
/// intermediate application-owned window is needed.
@MainActor
final class ContinuityCameraCapture: NSObject {
    private var receiver: CaptureTextView?
    private var menu: NSMenu?
    private var completion: ((URL?) -> Void)?

    @discardableResult
    func capture(completion: @escaping (URL?) -> Void) -> Bool {
        cleanup()
        guard let window = NSApplication.shared.keyWindow ?? NSApplication.shared.mainWindow,
              let contentView = window.contentView else {
            return false
        }

        self.completion = completion

        // Continuity Camera delivers its result to the current Services requestor.
        // Keep a nearly invisible requestor in the existing window while scanning.
        let receiver = CaptureTextView(frame: NSRect(x: 0, y: 0, width: 1, height: 1))
        receiver.isEditable = true
        receiver.drawsBackground = false
        receiver.alphaValue = 0.01
        receiver.received = { [weak self] pasteboard in self?.receive(pasteboard) ?? false }
        contentView.addSubview(receiver)
        self.receiver = receiver

        var types = NSImage.imageTypes.map(NSPasteboard.PasteboardType.init(rawValue:))
        types.append(contentsOf: [.pdf, .fileURL])
        NSApplication.shared.registerServicesMenuSendTypes([], returnTypes: Array(Set(types)))
        window.makeFirstResponder(receiver)

        let menu = NSMenu(title: "Import from iPhone")
        self.menu = menu

        // For contextual menus AppKit, rather than the app, must insert the
        // Continuity Camera item. A manually inserted identifier is only
        // supported in the application's main menu and appears disabled here.
        // The triggering event belongs to SwiftUI's temporary menu window.
        // Create an equivalent event owned by the document window; AppKit uses
        // that window's responder chain when deciding whether devices are valid.
        let event = NSEvent.mouseEvent(
            with: .rightMouseDown,
            location: window.convertPoint(fromScreen: NSEvent.mouseLocation),
            modifierFlags: [],
            timestamp: ProcessInfo.processInfo.systemUptime,
            windowNumber: window.windowNumber,
            context: nil,
            eventNumber: 0,
            clickCount: 1,
            pressure: 1
        )
        guard let event else {
            cleanup()
            return false
        }

        // SwiftUI Menu actions arrive before their owning menu has completely
        // dismissed. Defer one run-loop turn so the system device menu can take
        // ownership of tracking and validation.
        DispatchQueue.main.async { [weak receiver] in
            guard let receiver, receiver.window != nil else { return }
            window.makeFirstResponder(receiver)
            NSMenu.popUpContextMenu(menu, with: event, for: receiver)
        }
        return true
    }

    private func receive(_ pasteboard: NSPasteboard) -> Bool {
        do {
            let data: Data
            let ext: String
            if let pdf = pasteboard.data(forType: .pdf) {
                data = pdf
                ext = "pdf"
            } else if let urls = pasteboard.readObjects(
                forClasses: [NSURL.self],
                options: [.urlReadingFileURLsOnly: true]
            ) as? [URL], let source = urls.first {
                data = try Data(contentsOf: source)
                ext = source.pathExtension.isEmpty ? "png" : source.pathExtension
            } else if let image = NSImage(pasteboard: pasteboard),
                      let tiff = image.tiffRepresentation,
                      let bitmap = NSBitmapImageRep(data: tiff),
                      let png = bitmap.representation(using: .png, properties: [:]) {
                data = png
                ext = "png"
            } else {
                return false
            }

            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent("continuity-camera-\(UUID().uuidString).\(ext)")
            try data.write(to: url, options: .atomic)
            let completion = self.completion
            cleanup()
            completion?(url)
            return true
        } catch {
            let completion = self.completion
            cleanup()
            completion?(nil)
            return false
        }
    }

    private func cleanup() {
        receiver?.removeFromSuperview()
        receiver = nil
        menu = nil
        completion = nil
    }
}
