import SwiftUI

struct ConnectionsView: View {
    @StateObject private var model = ConnectionsViewModel()
    @State private var showBrowser = false
    @State private var explainBrowser = false
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        List {
            Section {
                Label("Your connected workspace", systemImage: "link.circle.fill")
                    .font(.title2.bold()).foregroundStyle(.cyan)
                Text("Connect your apps so Nova can work across your digital life.")
                    .foregroundStyle(.secondary)
                if model.loaded {
                    Text("\(model.accounts.filter { $0.status == "connected" }.count) connected · \(model.accounts.filter { $0.status == "pending" }.count) pending")
                        .font(.subheadline.weight(.medium))
                }
            }
            if model.loading { Section { ProgressView("Refreshing connections…") } }
            if let error = model.error {
                Section {
                    Label("Connections unavailable", systemImage: "exclamationmark.circle").foregroundStyle(.orange)
                    Text(error).font(.footnote)
                    Button("Retry") { Task { await model.refresh() } }.disabled(model.loading)
                }
            }
            if model.browserStarted {
                Section("Back to Nova") {
                    Text("Finish authorization in the browser, then tap Done or return to Nova. Only a refreshed server status confirms a connection.")
                    Button("Check connection status") { Task { await model.refresh() } }.disabled(model.loading)
                }
            }
            if model.loaded {
                Section("Accounts") {
                    if model.accounts.isEmpty {
                        Label("No accounts connected", systemImage: "person.crop.circle.badge.plus")
                        Text("Choose a provider below to get started.").font(.footnote).foregroundStyle(.secondary)
                    }
                    ForEach(model.accounts) { account in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(account.display_name?.isEmpty == false ? account.display_name! : account.provider.capitalized).font(.headline)
                            Text(account.provider.capitalized).font(.caption).foregroundStyle(.secondary)
                            Label(statusTitle(account.status), systemImage: statusIcon(account.status))
                                .foregroundStyle(account.status == "connected" ? .mint : .orange)
                            if let identity = account.provider_account_id, !identity.isEmpty, identity != account.display_name {
                                Text("Account: \(identity)").font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                            }
                            Text("Connection type: \(account.connection_type)").font(.caption).foregroundStyle(.secondary)
                            if account.status == "pending" { Text("Setup is pending on Nova. Refresh after completing authorization.").font(.footnote) }
                        }.padding(.vertical, 5).accessibilityElement(children: .combine)
                    }
                }
                Section("Available providers") {
                    if model.providers.isEmpty { Text("No providers are available from Nova yet.").foregroundStyle(.secondary) }
                    ForEach(model.providers) { provider in
                        VStack(alignment: .leading, spacing: 14) {
                            Text(provider.display_name).font(.title3.bold())
                            Text(provider.connected ? "Connected according to Nova" : "Not connected").foregroundStyle(.secondary)
                            if provider.connected {
                                Text("\(provider.accounts.count) linked account(s)").font(.caption).foregroundStyle(.secondary)
                            }
                            Text("Provider capability catalog").font(.subheadline.bold())
                            ForEach(provider.services) { service in
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(service.display_name).font(.headline)
                                    ForEach(service.capabilities, id: \.self) { capability in
                                        Text("• \(capabilityTitle(capability))").font(.subheadline).foregroundStyle(.secondary)
                                    }
                                }
                            }
                            Text("These capabilities describe planned service support, not permission to use your email or calendar. Google setup currently links your account identity only.")
                                .font(.footnote).foregroundStyle(.secondary)
                            if provider.provider == "google" && provider.oauth {
                                Button(provider.connected ? "Connect another Google account" : "Connect Google") { explainBrowser = true }
                                    .buttonStyle(.borderedProminent).tint(.indigo)
                                    .disabled(model.loading)
                            }
                        }.padding(.vertical, 8)
                    }
                }
            }
        }
        .listStyle(.insetGrouped).scrollContentBackground(.hidden)
        .background(Color(red: 0.025, green: 0.03, blue: 0.07))
        .navigationTitle("Connections").navigationBarTitleDisplayMode(.inline)
        .tint(.cyan).preferredColorScheme(.dark)
        .toolbar {
            Button { Task { await model.refresh() } } label: { Image(systemName: "arrow.clockwise") }
                .accessibilityLabel("Refresh connections").disabled(model.loading)
        }
        .task { await model.refresh() }
        .refreshable { await model.refresh() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.refresh() } }
        }
        .alert("Continue in the browser", isPresented: $explainBrowser) {
            Button("Open Google setup") { model.browserStarted = true; showBrowser = true }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("The browser has a separate Nova session. Sign in to the SAME Nova account if asked. Login returns to the web workspace. If that happens before Google setup, tap Done and open Google setup again here to continue with that browser session. After Google authorization, tap Done to return here. Your native session stays unchanged.")
        }
        .sheet(isPresented: $showBrowser, onDismiss: { Task { await model.refresh() } }) {
            ConnectionsBrowser { showBrowser = false }.ignoresSafeArea()
        }
    }

    private func statusTitle(_ status: String) -> String {
        switch status {
        case "connected": return "Connected"
        case "pending": return "Pending"
        case "disconnected": return "Disconnected"
        case "error", "failed": return "Connection needs attention"
        default: return "Status: \(status)"
        }
    }
    private func statusIcon(_ status: String) -> String {
        switch status {
        case "connected": return "checkmark.circle.fill"
        case "pending": return "clock"
        case "disconnected": return "minus.circle"
        default: return "exclamationmark.circle"
        }
    }
    private func capabilityTitle(_ id: String) -> String {
        ["email.read": "Read email", "email.search": "Search email", "email.send": "Send email",
         "calendar.read": "Read calendars", "calendar.create": "Create events", "calendar.update": "Update events"][id] ?? id
    }
}
