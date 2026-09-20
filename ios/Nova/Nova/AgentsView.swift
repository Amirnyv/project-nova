import SwiftUI

struct AgentsView: View {
    let csrfToken: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Choose a specialist for your work. Active agents use existing Nova features; coming-soon agents describe planned capabilities.")
                        .foregroundStyle(.secondary)
                }
                agentSection("Active Agents", active: true)
                agentSection("Coming Soon", active: false)
            }
            .scrollContentBackground(.hidden)
            .background(Color(red: 0.025, green: 0.03, blue: 0.07))
            .navigationTitle("AI Agents")
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } } }
        }.preferredColorScheme(.dark).tint(.purple)
    }

    private func agentSection(_ title: String, active: Bool) -> some View {
        Section(title) {
            ForEach(AgentCatalog.agents.filter { $0.active == active }) { agent in
                NavigationLink {
                    AgentInfoView(agent: agent, csrfToken: csrfToken)
                } label: {
                    HStack(alignment: .top, spacing: 14) {
                        Image(systemName: agent.icon).foregroundStyle(.purple).frame(width: 25)
                        VStack(alignment: .leading, spacing: 6) {
                            Text(agent.name).font(.headline)
                            Text(agent.summary).font(.subheadline).foregroundStyle(.secondary)
                            Text(agent.active ? "Active" : "Coming soon · Unavailable")
                                .font(.caption.bold()).foregroundStyle(agent.active ? .mint : .orange)
                        }
                    }.padding(.vertical, 7)
                }
            }
        }
    }
}

private struct AgentInfoView: View {
    let agent: NovaAgent
    let csrfToken: String
    @State private var launch = false

    var body: some View {
        List {
            Section {
                Label(agent.name, systemImage: agent.icon).font(.title2.bold())
                Text(agent.summary)
                Text(agent.active ? "Active · Uses Nova’s existing backend" : "Coming soon · Execution unavailable")
                    .foregroundStyle(agent.active ? .mint : .orange)
                if let requirement = agent.requirement { Text(requirement).font(.footnote).foregroundStyle(.secondary) }
            }
            Section("Capabilities in this agent") {
                ForEach(agent.capabilities) { capability in
                    VStack(alignment: .leading, spacing: 5) {
                        Text(capability.title)
                        Text(capability.available ? "Available" : "Planned · Not executable")
                            .font(.caption).foregroundStyle(capability.available ? .mint : .orange)
                    }
                }
            }
            Section {
                Button(agent.active ? "Open \(agent.name)" : "Coming soon") { launch = true }
                    .disabled(!agent.active)
                if !agent.active { Text("These are planned capabilities. This agent cannot send requests or perform actions yet.").font(.footnote).foregroundStyle(.secondary) }
            }
        }
        .navigationTitle(agent.name).navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $launch) {
            switch agent.execution {
            case .projects: NovaProjectsView(csrfToken: csrfToken)
            case .markets: MarketsView(csrfToken: csrfToken)
            case .chat(let mode): AgentChatView(agent: agent, mode: mode, csrfToken: csrfToken)
            case nil: EmptyView()
            }
        }
    }
}

private struct AgentChatView: View {
    let agent: NovaAgent
    let csrfToken: String
    @StateObject private var model: JarvisViewModel
    @Environment(\.dismiss) private var dismiss

    init(agent: NovaAgent, mode: String, csrfToken: String) {
        self.agent = agent
        self.csrfToken = csrfToken
        _model = StateObject(wrappedValue: JarvisViewModel(agentMode: mode))
    }

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 20) {
                        Text(agent.requirement ?? "").font(.caption).foregroundStyle(.secondary)
                        if model.messages.isEmpty { Text("What would you like help with?").foregroundStyle(.secondary) }
                        ForEach(model.messages) { message in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(message.role == "user" ? "You" : agent.name).font(.caption.bold()).foregroundStyle(.purple)
                                Text(message.text.isEmpty ? "Thinking…" : message.text).textSelection(.enabled)
                            }
                        }
                        if model.sending { ProgressView("Responding…") }
                        if let error = model.errorMessage { Text(error).foregroundStyle(.orange) }
                        Color.clear.frame(height: 1).id("bottom")
                    }.frame(maxWidth: .infinity, alignment: .leading).padding()
                }
                .onChange(of: model.messages.last?.text) { _, _ in proxy.scrollTo("bottom", anchor: .bottom) }
            }
            .safeAreaInset(edge: .bottom) {
                HStack {
                    TextField("Message \(agent.name)…", text: $model.command, axis: .vertical).lineLimit(1...6)
                    Button { model.send(csrfToken: csrfToken) { _ in } } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }
                        .accessibilityLabel("Send message")
                        .disabled(model.sending || model.command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }.padding().background(.ultraThinMaterial)
            }
            .navigationTitle(agent.name).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } } }
        }.onDisappear { model.stop() }
    }
}
