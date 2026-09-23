import SwiftUI

struct SettingsView: View {
    let csrfToken: String
    let onSignOut: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var plan: NovaPlanResponse?
    @State private var planError: String?
    @State private var loading = false
    @State private var signingOut = false
    @State private var confirmSignOut = false
    @State private var signOutError: String?
    private let api = SettingsAPIService()

    var body: some View {
        NavigationStack {
            List {
                Section("Account") {
                    Label("Nova account", systemImage: "person.crop.circle").font(.headline)
                    Text("Profile and email details are not available in this app yet.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button(role: .destructive) { confirmSignOut = true } label: {
                        HStack {
                            Label(signingOut ? "Signing out…" : "Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                            if signingOut { Spacer(); ProgressView() }
                        }
                    }.disabled(signingOut)
                    if let signOutError { Text(signOutError).font(.footnote).foregroundStyle(.orange) }
                }
                Section("Nova Plan") {
                    if loading { ProgressView("Loading plan…") }
                    if let plan {
                        LabeledContent("Current plan", value: plan.subscription.plan == "none" ? "No active plan" : plan.subscription.plan.capitalized)
                        LabeledContent("Status", value: plan.subscription.status.capitalized)
                    } else if !loading { Text("Plan unavailable").foregroundStyle(.secondary) }
                    if let planError {
                        Text(planError).font(.footnote).foregroundStyle(.orange)
                        Button("Retry plan lookup") { Task { await loadPlan() } }.disabled(loading)
                    }
                    unavailable("Manage plan", icon: "creditcard", detail: "Not available in iOS yet")
                    Text("App Store subscription management is planned.").font(.footnote).foregroundStyle(.secondary)
                }
                Section("Connections") {
                    NavigationLink {
                        ConnectionsView()
                    } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            Label("Connections", systemImage: "link")
                            Text("Accounts, providers & capabilities").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                Section("Security") {
                    unavailable("Face ID", icon: "faceid", detail: "Coming soon")
                    unavailable("Session & security settings", icon: "lock.shield", detail: "Coming soon")
                }
                Section("Jarvis & Voice") {
                    unavailable("Voice selection", icon: "waveform", detail: "Coming soon")
                    Label("Spoken responses", systemImage: "speaker.wave.2")
                    Text("Use Speak responses inside Jarvis. App-wide voice preferences are not available yet.")
                        .font(.footnote).foregroundStyle(.secondary)
                    unavailable("Jarvis preferences", icon: "slider.horizontal.3", detail: "Coming soon")
                }
                Section("Appearance") {
                    unavailable("Theme preferences", icon: "paintpalette", detail: "Coming soon")
                }
                Section("About Nova") {
                    Label("Nova", systemImage: "sparkles").font(.headline)
                    LabeledContent("Version", value: bundleValue("CFBundleShortVersionString"))
                    LabeledContent("Build", value: bundleValue("CFBundleVersion"))
                    Link(destination: URL(string: "https://workfieldhq.com/privacy")!) { Label("Privacy", systemImage: "hand.raised") }
                    Link(destination: URL(string: "https://workfieldhq.com/terms")!) { Label("Terms", systemImage: "doc.text") }
                    unavailable("Help / Support", icon: "questionmark.circle", detail: "Coming soon")
                }
                .listRowBackground(Color.white.opacity(0.045))
            }
            .listStyle(.insetGrouped).scrollContentBackground(.hidden)
            .background(Color(red: 0.025, green: 0.03, blue: 0.07))
            .navigationTitle("Settings")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() }.disabled(signingOut) } }
            .refreshable { await loadPlan() }
            .task { await loadPlan() }
            .confirmationDialog("Sign out of Nova?", isPresented: $confirmSignOut, titleVisibility: .visible) {
                Button("Sign Out", role: .destructive) { Task { await signOut() } }
                Button("Cancel", role: .cancel) {}
            } message: { Text("You’ll return to the login screen.") }
        }
        .preferredColorScheme(.dark).tint(.cyan)
        .interactiveDismissDisabled(signingOut)
    }

    private func unavailable(_ title: String, icon: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Label(title, systemImage: icon)
            Text(detail).font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }

    private func bundleValue(_ key: String) -> String {
        Bundle.main.object(forInfoDictionaryKey: key) as? String ?? "Unavailable"
    }

    private func loadPlan() async {
        guard !loading, !signingOut else { return }
        loading = true
        planError = nil
        defer { loading = false }
        do {
            let result = try await api.plan()
            try Task.checkCancellation()
            plan = result
        } catch {
            if !Task.isCancelled { plan = nil; planError = error.localizedDescription }
        }
    }

    private func signOut() async {
        guard !signingOut else { return }
        signingOut = true
        signOutError = nil
        defer { signingOut = false }
        do {
            try await api.signOut(csrfToken: csrfToken)
            onSignOut()
        } catch { signOutError = error.localizedDescription }
    }
}
