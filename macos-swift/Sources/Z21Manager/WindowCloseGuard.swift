import AppKit
import SwiftUI

struct WindowCloseGuard: NSViewRepresentable {
    let state: AppState

    func makeCoordinator() -> Coordinator {
        Coordinator(state: state)
    }

    func makeNSView(context: Context) -> WindowCloseHostingView {
        let view = WindowCloseHostingView(frame: .zero)
        view.onWindowChange = { [weak coordinator = context.coordinator] window in
            if let window { coordinator?.install(on: window) }
        }
        return view
    }

    func updateNSView(_ nsView: WindowCloseHostingView, context: Context) {
        context.coordinator.state = state
        if let window = nsView.window { context.coordinator.install(on: window) }
    }

    static func dismantleNSView(_ nsView: WindowCloseHostingView, coordinator: Coordinator) {
        nsView.onWindowChange = nil
        coordinator.uninstall()
    }

    @MainActor
    final class Coordinator: NSObject, NSWindowDelegate {
        weak var state: AppState?
        private weak var window: NSWindow?
        private weak var originalDelegate: NSWindowDelegate?
        private var closeRequestInProgress = false
        private var allowNextClose = false

        init(state: AppState) {
            self.state = state
        }

        func install(on window: NSWindow) {
            guard (window.delegate as AnyObject?) !== self else { return }
            uninstall()
            self.window = window
            originalDelegate = window.delegate
            window.delegate = self
        }

        func uninstall() {
            if let window, (window.delegate as AnyObject?) === self {
                window.delegate = originalDelegate
            }
            window = nil
            originalDelegate = nil
        }

        func windowShouldClose(_ sender: NSWindow) -> Bool {
            if allowNextClose {
                allowNextClose = false
                return originalDelegate?.windowShouldClose?(sender) ?? true
            }
            guard let state, state.isDirty else {
                return originalDelegate?.windowShouldClose?(sender) ?? true
            }
            guard !closeRequestInProgress else { return false }
            closeRequestInProgress = true
            state.requestAbandonChanges(markDiscarded: true) { [weak self, weak sender] proceed in
                guard let self else { return }
                closeRequestInProgress = false
                guard proceed, let sender else { return }
                allowNextClose = true
                Task { @MainActor in sender.performClose(nil) }
            }
            return false
        }

        override func responds(to selector: Selector!) -> Bool {
            super.responds(to: selector) || originalDelegate?.responds(to: selector) == true
        }

        override func forwardingTarget(for selector: Selector!) -> Any? {
            if originalDelegate?.responds(to: selector) == true { return originalDelegate }
            return super.forwardingTarget(for: selector)
        }
    }
}

final class WindowCloseHostingView: NSView {
    var onWindowChange: ((NSWindow?) -> Void)?

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        onWindowChange?(window)
    }
}
