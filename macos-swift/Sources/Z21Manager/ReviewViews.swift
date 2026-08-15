import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var apiKey = ""
    @State private var configured = false
    @State private var message = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("External Services").font(.title2).fontWeight(.semibold)
            GroupBox("DeepSeek API") {
                VStack(alignment: .leading, spacing: 10) {
                    Label(configured ? "API key saved in macOS Keychain" : "No API key configured",
                          systemImage: configured ? "checkmark.shield" : "key")
                        .foregroundStyle(configured ? .green : .secondary)
                    SecureField("Enter a new DeepSeek API key", text: $apiKey)
                    Text("Only editable OCR text and layout are sent. Captured images and API keys are never included in prompts.")
                        .font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Button("Remove") { remove() }.disabled(!configured)
                        Spacer(); Button("Save Key") { save() }.disabled(apiKey.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                    if !message.isEmpty { Text(message).font(.caption).foregroundStyle(.red) }
                }.padding(8)
            }
            HStack { Spacer(); Button("Close") { dismiss() }.keyboardShortcut(.defaultAction) }
        }.padding(24).frame(width: 540, height: 300).onAppear { configured = ((try? DeepSeekKeychain.get()) ?? nil) != nil }
    }
    private func save() { do { try DeepSeekKeychain.set(apiKey); apiKey = ""; configured = true; message = "" } catch { message = error.localizedDescription } }
    private func remove() { do { try DeepSeekKeychain.delete(); configured = false; message = "" } catch { message = error.localizedDescription } }
}
