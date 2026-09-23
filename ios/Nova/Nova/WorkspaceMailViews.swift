import SwiftUI

struct WorkspaceMessageDetail: View {
    let summary: WorkspaceMessage
    let service: any GoogleWorkspaceService
    let connectionId: Int?
    @State private var message: WorkspaceMessage?
    @State private var state: WorkspaceLoadState = .idle
    @State private var reply = false
    @State private var reload = UUID()

    var body: some View {
        List {
            let item = message ?? summary
            Section {
                Text(item.subject.isEmpty ? "(No subject)" : item.subject).font(.title2.bold())
                LabeledContent("From", value: item.from.display)
                LabeledContent("To", value: item.to.map(\.display).joined(separator: ", "))
                Text(item.receivedAt.formatted()).font(.caption).foregroundStyle(.secondary)
            }
            Section("Message") {
                WorkspaceStateView(state: state, empty: "This message has no text body.") { reload = UUID() }
                if let body = message?.bodyText { Text(body).textSelection(.enabled) }
            }
            Section {
                Button("Prepare reply") { reply = true }.disabled(message == nil)
                Label("Archive, trash, and label changes are unavailable until authenticated mutation APIs exist.", systemImage: "lock").font(.footnote).foregroundStyle(.secondary)
            }
        }.workspaceStyle().navigationTitle("Message").navigationBarTitleDisplayMode(.inline)
        .task(id: reload) {
            guard let connectionId, service.operations.contains(.read) else { state = .unavailable; return }
            state = .loading
            do {
                let result = try await service.message(connectionId: connectionId, id: summary.id)
                try Task.checkCancellation()
                message = result
                state = result.bodyText?.isEmpty == false ? .loaded : .empty
            } catch { state = Task.isCancelled ? .idle : .error(error.localizedDescription) }
        }
        .sheet(isPresented: $reply) { WorkspaceMailEditor(service: service, connectionId: connectionId, reply: message) }
    }
}

struct WorkspaceMailEditor: View {
    let service: any GoogleWorkspaceService
    let connectionId: Int?
    let reply: WorkspaceMessage?
    @State private var recipient = ""
    @State private var subject = ""
    @State private var text = ""
    @State private var sending = false
    @State private var error: String?
    @State private var confirmSend = false
    @State private var confirmDiscard = false
    @State private var initialized = false
    @State private var requestId = UUID()
    @Environment(\.dismiss) private var dismiss

    private var available: Bool { connectionId != nil && service.operations.contains(reply == nil ? .send : .reply) }
    private var valid: Bool { recipient.contains("@") && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Local draft only. Nothing is saved or sent until an authenticated send API is available.").font(.footnote).foregroundStyle(.secondary)
                    TextField("Recipient email", text: $recipient).textContentType(.emailAddress).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                    TextField("Subject", text: $subject)
                }
                Section("Message") { TextEditor(text: $text).frame(minHeight: 220).accessibilityLabel("Message body") }
                if let error { Section { Text(error).foregroundStyle(.orange) } }
                Section {
                    Button(sending ? "Sending…" : "Send") { confirmSend = true }.disabled(!available || !valid || sending)
                    if !available { Label("Sending is unavailable", systemImage: "lock").font(.caption).foregroundStyle(.secondary) }
                }
            }.workspaceStyle().disabled(sending)
            .navigationTitle(reply == nil ? "Compose" : "Reply").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { confirmDiscard = true }.disabled(sending) } }
            .confirmationDialog("Discard this local draft?", isPresented: $confirmDiscard) { Button("Discard", role: .destructive) { dismiss() } }
            .confirmationDialog("Send this email?", isPresented: $confirmSend, titleVisibility: .visible) {
                Button("Send") { Task { await send() } }
            } message: { Text("To: \(recipient)\nSubject: \(subject)") }
        }.interactiveDismissDisabled()
        .onAppear {
            guard !initialized else { return }; initialized = true
            if let reply {
                recipient = (reply.replyTo.first ?? reply.from).email
                subject = reply.subject.lowercased().hasPrefix("re:") ? reply.subject : "Re: \(reply.subject)"
            }
        }
    }
    private func send() async {
        guard available, valid, !sending, let connectionId else { return }
        sending = true; error = nil
        defer { sending = false }
        do {
            try await service.send(connectionId: connectionId, draft: WorkspaceMailDraft(to: [.init(name: nil, email: recipient.trimmingCharacters(in: .whitespacesAndNewlines))], subject: subject, bodyText: text, replyToMessageId: reply?.id), requestId: requestId)
            dismiss()
        } catch { self.error = "\(error.localizedDescription) Check delivery before retrying; drafts are not persisted." }
    }
}
