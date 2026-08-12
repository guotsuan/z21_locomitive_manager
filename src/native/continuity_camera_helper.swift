import AppKit
import Foundation

private struct Arguments {
    let mode: String
    let outputDirectory: URL
    let resultFile: URL

    static func parse() -> Arguments? {
        let arguments = CommandLine.arguments
        guard !arguments.contains("--help"),
              let mode = value(after: "--mode", in: arguments),
              let outputPath = value(after: "--output-dir", in: arguments),
              let resultPath = value(after: "--result-file", in: arguments),
              mode == "scan" || mode == "photo" else {
            return nil
        }
        return Arguments(
            mode: mode,
            outputDirectory: URL(fileURLWithPath: outputPath,
                                 isDirectory: true),
            resultFile: URL(fileURLWithPath: resultPath)
        )
    }

    private static func value(after flag: String,
                              in arguments: [String]) -> String? {
        guard let index = arguments.firstIndex(of: flag),
              arguments.indices.contains(index + 1) else { return nil }
        return arguments[index + 1]
    }
}

private final class CaptureReceiverView: NSTextView {
    var onPasteboardReceived: ((NSPasteboard) -> Bool)?

    override func validRequestor(
        forSendType sendType: NSPasteboard.PasteboardType?,
        returnType: NSPasteboard.PasteboardType?
    ) -> Any? {
        if let returnType,
           returnType == .pdf || returnType == .fileURL ||
            NSImage.imageTypes.contains(returnType.rawValue) {
            return self
        }
        return super.validRequestor(forSendType: sendType,
                                    returnType: returnType)
    }

    override func readSelection(from pasteboard: NSPasteboard) -> Bool {
        if onPasteboardReceived?(pasteboard) == true {
            return true
        }
        return super.readSelection(from: pasteboard)
    }

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
        let menu = NSMenu(title: "Continuity Camera")
        NSMenu.popUpContextMenu(menu, with: event, for: self)
    }

}

private final class CameraAppDelegate: NSObject,
                                        NSApplicationDelegate,
                                        NSWindowDelegate {
    private let arguments: Arguments
    private var window: NSWindow!
    private var captureView: CaptureReceiverView!
    private var continuityMenu: NSMenu!
    private var completed = false

    init(arguments: Arguments) {
        self.arguments = arguments
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            try FileManager.default.createDirectory(
                at: arguments.outputDirectory,
                withIntermediateDirectories: true
            )
        } catch {
            finish(error: "Unable to create capture directory: \(error.localizedDescription)")
            return
        }

        createMainMenu()
        createWindow()
        NSApplication.shared.registerServicesMenuSendTypes(
            [],
            returnTypes: supportedPasteboardTypes
        )
        NSApplication.shared.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(captureView)

        // A bundled app with a registered responder allows AppKit to populate
        // this designated menu with the available iPhone actions.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.showContinuityCameraMenu(nil)
        }
    }

    private var supportedPasteboardTypes: [NSPasteboard.PasteboardType] {
        var types: [NSPasteboard.PasteboardType] = NSImage.imageTypes.map {
            NSPasteboard.PasteboardType(rawValue: $0)
        }
        types.append(NSPasteboard.PasteboardType.pdf)
        types.append(NSPasteboard.PasteboardType.fileURL)
        return Array(Set(types))
    }

    private func createMainMenu() {
        let mainMenu = NSMenu(title: "Main Menu")

        let applicationItem = NSMenuItem()
        mainMenu.addItem(applicationItem)
        let applicationMenu = NSMenu(title: "Continuity Camera Helper")
        applicationItem.submenu = applicationMenu
        applicationMenu.addItem(
            withTitle: "Quit Continuity Camera Helper",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )

        let fileItem = NSMenuItem(title: "File", action: nil,
                                  keyEquivalent: "")
        mainMenu.addItem(fileItem)
        continuityMenu = NSMenu(title: "File")
        fileItem.submenu = continuityMenu

        let importItem = NSMenuItem(
            title: "Import from iPhone",
            action: nil,
            keyEquivalent: ""
        )
        importItem.identifier = NSMenuItem.importFromDeviceIdentifier
        continuityMenu.addItem(importItem)
        continuityMenu.addItem(.separator())
        continuityMenu.addItem(
            withTitle: "Cancel",
            action: #selector(cancelCapture(_:)),
            keyEquivalent: ""
        ).target = self

        NSApplication.shared.mainMenu = mainMenu
    }

    private func createWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 540, height: 250),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = arguments.mode == "scan"
            ? "Scan Document with iPhone"
            : "Take Photo with iPhone"
        window.center()
        window.delegate = self

        let contentView = NSView(frame: window.contentView!.bounds)
        contentView.autoresizingMask = [.width, .height]
        window.contentView = contentView

        let instruction = NSTextField(labelWithString: instructionText)
        instruction.frame = NSRect(x: 30, y: 155, width: 480, height: 65)
        instruction.alignment = .center
        instruction.maximumNumberOfLines = 4
        instruction.lineBreakMode = .byWordWrapping
        contentView.addSubview(instruction)

        captureView = CaptureReceiverView(
            frame: NSRect(x: 55, y: 74, width: 430, height: 58)
        )
        captureView.isEditable = true
        captureView.isRichText = true
        captureView.isSelectable = true
        captureView.alignment = .center
        captureView.font = NSFont.systemFont(ofSize: 15, weight: .medium)
        captureView.string = "Click here to open the iPhone Camera menu"
        captureView.textContainerInset = NSSize(width: 8, height: 17)
        captureView.onPasteboardReceived = { [weak self] pasteboard in
            self?.receive(pasteboard: pasteboard) ?? false
        }
        contentView.addSubview(captureView)

        let showMenuButton = NSButton(
            title: "Show iPhone Camera Menu",
            target: self,
            action: #selector(showContinuityCameraMenu(_:))
        )
        showMenuButton.frame = NSRect(x: 150, y: 24, width: 240, height: 32)
        showMenuButton.bezelStyle = .rounded
        contentView.addSubview(showMenuButton)
    }

    private var instructionText: String {
        let requestedAction = arguments.mode == "scan"
            ? "Scan Documents"
            : "Take Photo"
        return "Select your iPhone, then choose \(requestedAction).\n"
            + "Apple requires the device action to be selected from its system menu."
    }

    @objc private func showContinuityCameraMenu(_ sender: Any?) {
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(captureView)
        let point = NSPoint(x: captureView.frame.midX,
                            y: captureView.frame.minY - 4)
        continuityMenu.popUp(positioning: continuityMenu.items.first,
                             at: point,
                             in: window.contentView)
    }

    @objc private func cancelCapture(_ sender: Any?) {
        finish(status: "cancelled")
    }

    private func receive(pasteboard: NSPasteboard) -> Bool {
        guard !completed else { return false }
        do {
            let resultURL = try save(pasteboard: pasteboard)
            finish(with: resultURL)
            return true
        } catch {
            finish(error: error.localizedDescription)
            return false
        }
    }

    private func save(pasteboard: NSPasteboard) throws -> URL {
        if let pdfData = pasteboard.data(forType: .pdf) {
            return try write(pdfData, extension: "pdf")
        }

        if let URLs = pasteboard.readObjects(
            forClasses: [NSURL.self],
            options: [.urlReadingFileURLsOnly: true]
        ) as? [URL], let sourceURL = URLs.first {
            let data = try Data(contentsOf: sourceURL)
            let fileExtension = sourceURL.pathExtension.isEmpty
                ? fallbackExtension
                : sourceURL.pathExtension
            return try write(data, extension: fileExtension)
        }

        guard let image = NSImage(pasteboard: pasteboard),
              let tiffData = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiffData),
              let pngData = bitmap.representation(using: .png,
                                                  properties: [:]) else {
            throw NSError(
                domain: "ContinuityCameraHelper",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey:
                    "Continuity Camera returned no readable image or PDF data."]
            )
        }
        return try write(pngData, extension: "png")
    }

    private var fallbackExtension: String {
        arguments.mode == "scan" ? "pdf" : "png"
    }

    private func write(_ data: Data, extension fileExtension: String) throws -> URL {
        let cleanExtension = fileExtension
            .trimmingCharacters(in: CharacterSet(charactersIn: "."))
        let prefix = arguments.mode == "scan" ? "scan" : "photo"
        let filename = "\(prefix)-\(UUID().uuidString).\(cleanExtension)"
        let outputURL = arguments.outputDirectory.appendingPathComponent(filename)
        try data.write(to: outputURL, options: .atomic)
        return outputURL
    }

    private func finish(with outputURL: URL) {
        finish(status: "ok", additionalValues: ["path": outputURL.path])
    }

    private func finish(error: String) {
        finish(status: "error", additionalValues: ["message": error])
    }

    private func finish(status: String,
                        additionalValues: [String: String] = [:]) {
        guard !completed else { return }
        completed = true
        var result = additionalValues
        result["status"] = status
        result["mode"] = arguments.mode
        do {
            let data = try JSONSerialization.data(withJSONObject: result)
            try data.write(to: arguments.resultFile, options: .atomic)
        } catch {
            fputs("Unable to write capture result: \(error)\n", stderr)
        }
        NSApplication.shared.terminate(nil)
    }

    func windowWillClose(_ notification: Notification) {
        finish(status: "cancelled")
    }
}

guard let arguments = Arguments.parse() else {
    fputs("Usage: ContinuityCameraHelper --mode scan|photo "
        + "--output-dir PATH --result-file PATH\n", stderr)
    exit(2)
}

let application = NSApplication.shared
application.setActivationPolicy(.regular)
private let delegate = CameraAppDelegate(arguments: arguments)
application.delegate = delegate
application.run()
