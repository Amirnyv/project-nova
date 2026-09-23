import SwiftUI

struct GoogleWorkspaceView: View {
    @StateObject private var model = GoogleWorkspaceViewModel()
    @StateObject private var connections = ConnectionsViewModel()
    @State private var tab = 0
    @State private var compose = false
    @State private var createEvent = false
    @State private var week = Date()
    @State private var request: Task<Void, Never>?
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        List {
            Section {
                Label("Google workspace", systemImage: "square.grid.2x2.fill").font(.title2.bold()).foregroundStyle(.cyan)
                Text("Mail and calendar, alongside Jarvis.").foregroundStyle(.secondary)
                Text("Workspace APIs are not available yet. You can prepare a local draft, but search, send, and event changes are disabled.")
                    .font(.footnote).foregroundStyle(.orange)
                NavigationLink("Manage Google connections") { ConnectionsView() }
                if connections.loading { ProgressView("Checking accounts…") }
                if let error = connections.error {
                    Text(error).font(.footnote).foregroundStyle(.orange)
                    Button("Retry accounts") { Task { await connections.refresh() } }
                } else if connections.loaded {
                    let accounts = connections.accounts.filter { $0.provider == "google" && $0.status == "connected" }
                    if accounts.isEmpty { Text("No connected Google account.").foregroundStyle(.secondary) }
                    else {
                        Picker("Account", selection: $model.connectionId) {
                            Text("Select an account").tag(nil as Int?)
                            ForEach(accounts) { account in
                                Text(account.display_name ?? account.provider_account_id ?? "Google account").tag(Optional(account.id))
                            }
                        }
                    }
                }
            }
            Section {
                Picker("Workspace", selection: $tab) { Text("Gmail").tag(0); Text("Calendar").tag(1) }.pickerStyle(.segmented)
            }
            if tab == 0 { mail } else { agenda }
        }
        .workspaceStyle()
        .navigationTitle("Workspace").navigationBarTitleDisplayMode(.inline)
        .task { await connections.refresh() }
        .refreshable { await connections.refresh() }
        .onChange(of: scenePhase) { _, phase in if phase == .active { Task { await connections.refresh() } } }
        .onChange(of: model.query) { _, _ in request?.cancel(); model.resetMail() }
        .onChange(of: week) { _, _ in request?.cancel(); model.resetAgenda() }
        .onChange(of: model.connectionId) { _, _ in request?.cancel(); model.resetAccount() }
        .onChange(of: connections.accounts.filter { $0.provider == "google" && $0.status == "connected" }.map(\.id)) { _, ids in
            if let selected = model.connectionId, !ids.contains(selected) { model.connectionId = nil }
        }
        .onDisappear { request?.cancel() }
        .sheet(isPresented: $compose) { WorkspaceMailEditor(service: model.service, connectionId: model.connectionId, reply: nil) }
        .sheet(isPresented: $createEvent) { WorkspaceEventEditor(service: model.service, connectionId: model.connectionId, event: nil) }
    }

    private var mail: some View {
        Section("Gmail") {
            HStack {
                TextField("Search Gmail", text: $model.query).autocorrectionDisabled().textInputAutocapitalization(.never)
                    .disabled(!model.enabled(.search) || model.mailState == .loading)
                Button("Search") { request = Task { await model.search() } }
                    .disabled(!model.enabled(.search) || model.mailState == .loading)
            }
            Button { compose = true } label: { Label("Prepare email draft", systemImage: "square.and.pencil") }
            WorkspaceStateView(state: model.mailState, empty: "No messages match your search.") {
                request = Task { await model.search() }
            }
            ForEach(model.messages) { message in
                NavigationLink {
                    WorkspaceMessageDetail(summary: message, service: model.service, connectionId: model.connectionId)
                } label: {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(message.from.display).font(.headline)
                        Text(message.subject.isEmpty ? "(No subject)" : message.subject)
                        Text(message.snippet).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                        Text(message.receivedAt.formatted()).font(.caption2).foregroundStyle(.secondary)
                    }.accessibilityElement(children: .combine)
                }
            }
            if model.mailPage != nil {
                Button("More messages") { request = Task { await model.search(more: true) } }.disabled(model.mailState == .loading)
            }
        }
    }
    private var agenda: some View {
        Section("Calendar · Seven-day agenda") {
            DatePicker("Starting", selection: $week, displayedComponents: .date).disabled(!model.enabled(.agenda) || model.agendaState == .loading)
            Button("Load agenda") { request = Task { await model.loadAgenda(start: week) } }
                .disabled(!model.enabled(.agenda) || model.agendaState == .loading)
            Button { createEvent = true } label: { Label("Prepare event draft", systemImage: "calendar.badge.plus") }
            WorkspaceStateView(state: model.agendaState, empty: "No events in this date range.") {
                request = Task { await model.loadAgenda(start: week) }
            }
            ForEach(model.events, id: \.calendarEventKey) { event in
                NavigationLink {
                    WorkspaceEventDetail(event: event, service: model.service, connectionId: model.connectionId)
                } label: {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(event.title).font(.headline)
                        Text(event.timing.display).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            if model.agendaPage != nil {
                Button("More events") { request = Task { await model.loadAgenda(start: week, more: true) } }.disabled(model.agendaState == .loading)
            }
        }
    }
}

extension WorkspaceEvent { var calendarEventKey: String { "\(calendarId):\(id)" } }

struct WorkspaceStateView: View {
    let state: WorkspaceLoadState
    let empty: String
    let retry: () -> Void
    var body: some View {
        switch state {
        case .unavailable: Label("Not available until Nova workspace APIs are connected.", systemImage: "lock").font(.footnote).foregroundStyle(.secondary)
        case .idle: Text("Ready when you are.").foregroundStyle(.secondary)
        case .loading: ProgressView("Loading…")
        case .empty: Text(empty).foregroundStyle(.secondary)
        case .loaded: EmptyView()
        case .error(let message): VStack(alignment: .leading) { Text(message).foregroundStyle(.orange); Button("Retry", action: retry) }
        }
    }
}
extension View {
    func workspaceStyle() -> some View {
        scrollContentBackground(.hidden)
            .background(Color(red: 0.025, green: 0.03, blue: 0.07)).preferredColorScheme(.dark).tint(.cyan)
    }
}
