import SwiftUI
import AVFoundation

struct JarvisView: View {
    let csrfToken: String
    @ObservedObject var model: JarvisViewModel
    @StateObject private var voice = JarvisVoiceManager()
    @State private var voiceReplies = true
    @State private var visible = false
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase

    private var state: JarvisState {
        if voice.listening { return .listening }
        if voice.speaking { return .speaking }
        if voice.errorMessage != nil { return .error }
        return model.state
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 22) {
                    orb
                    conversation
                    card("Quick Actions") {
                        ForEach(["List my projects", "Help me review my tasks", "What can you help me with?"], id: \.self) { command in
                            Button { model.command = command } label: {
                                Label(command, systemImage: "sparkles").frame(maxWidth: .infinity, alignment: .leading)
                            }
                            .padding(.vertical, 7)
                            .disabled(model.sending || voice.listening || voice.requestingPermission)
                        }
                    }
                    card("Google Workspace") {
                        NavigationLink {
                            GoogleWorkspaceView()
                        } label: {
                            Label("Gmail & Calendar", systemImage: "envelope.badge")
                        }
                        Text("Workspace APIs coming soon. Prepare local drafts; execution is unavailable.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    statusCard
                    card("Active Tasks") {
                        if model.loading { ProgressView("Loading tasks…") }
                        else if model.tasks.isEmpty {
                            Text(model.dashboardError == nil ? "No incomplete tasks." : "Task data is unavailable or incomplete.").foregroundStyle(.secondary)
                        }
                        ForEach(model.tasks) { row in
                            NavigationLink {
                                NovaProjectWorkspaceView(project: row.project, csrfToken: csrfToken)
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Label(row.task.title, systemImage: "circle")
                                    Text(row.project.name).font(.caption).foregroundStyle(.secondary)
                                }.padding(.vertical, 5)
                            }
                        }
                    }
                    card("Projects") {
                        if model.projects.isEmpty && !model.loading {
                            Text(model.dashboardError == nil ? "No projects yet." : "Projects could not be loaded.").foregroundStyle(.secondary)
                        }
                        ForEach(model.projects) { project in
                            NavigationLink {
                                NovaProjectWorkspaceView(project: project, csrfToken: csrfToken)
                            } label: {
                                Label(project.name, systemImage: "folder").padding(.vertical, 6)
                            }
                        }
                    }
                    if let error = model.dashboardError {
                        Text(error).font(.footnote).foregroundStyle(.orange)
                    }
                }.padding()
            }
            .background(Color(red: 0.015, green: 0.035, blue: 0.065))
            .safeAreaInset(edge: .bottom) { composer }
            .navigationTitle("Jarvis")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await model.refresh() } } label: { Image(systemName: "arrow.clockwise") }
                        .accessibilityLabel("Refresh dashboard").disabled(model.loading)
                }
            }
        }
        .preferredColorScheme(.dark)
        .tint(.cyan)
        .task { await model.refresh() }
        .onAppear {
            visible = true
            voice.onTranscript = { model.command = $0 }
            voice.onFinal = { send() }
        }
        .onDisappear {
            visible = false
            voice.stop()
            voice.onTranscript = nil
            voice.onFinal = nil
            model.stop()
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background || (phase == .inactive && !voice.requestingPermission) { voice.stop() }
        }
        .onReceive(NotificationCenter.default.publisher(for: AVAudioSession.interruptionNotification)) { notification in
            if let type = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
               type == AVAudioSession.InterruptionType.began.rawValue { voice.stop() }
        }
        .onReceive(NotificationCenter.default.publisher(for: AVAudioSession.routeChangeNotification)) { notification in
            if let reason = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
               reason == AVAudioSession.RouteChangeReason.oldDeviceUnavailable.rawValue { voice.stop() }
        }
    }

    private var orb: some View {
        VStack(spacing: 12) {
            Button {
                if voice.listening { voice.stopListening() }
                else if voice.speaking { voice.stop() }
                else { Task { await voice.start() } }
            } label: {
                ZStack {
                    Circle().fill(RadialGradient(colors: [.blue.opacity(0.15), .cyan.opacity(0.6), .blue.opacity(0.1)], center: .center, startRadius: 45, endRadius: 85))
                    Circle().stroke(.cyan.opacity(0.6), lineWidth: 2).padding(10)
                    VStack(spacing: 8) {
                        Image(systemName: voice.listening ? "waveform" : (voice.speaking ? "speaker.wave.2.fill" : "mic.fill")).font(.largeTitle)
                        Text("NOVA").font(.headline).tracking(5)
                    }.foregroundStyle(.white)
                }.frame(width: 170, height: 170).shadow(color: .cyan.opacity(0.3), radius: 18)
            }
            .disabled((model.sending && !voice.speaking) || voice.requestingPermission)
            .accessibilityLabel(voice.listening ? "Stop listening" : voice.speaking ? "Stop speaking" : "Start voice command")
            Text(state.rawValue).font(.headline).foregroundStyle(state == .error ? .orange : .cyan)
            Text(voice.requestingPermission ? "Requesting voice permissions…" : voice.listening ? "Speak your command. Tap to stop and review." : "Tap to speak, or type below.")
                .font(.caption).foregroundStyle(.secondary)
        }.padding(.vertical, 8)
    }

    private var conversation: some View {
        card("Conversation") {
            if model.messages.isEmpty { Text("Ask Nova about your work.").foregroundStyle(.secondary) }
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(model.messages) { message in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(message.role == "user" ? "YOU" : "NOVA").font(.caption2.bold()).foregroundStyle(.cyan)
                                Text(message.text.isEmpty ? (model.sending ? "Thinking…" : "No response received.") : message.text).textSelection(.enabled)
                            }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                        }
                        Color.clear.frame(height: 1).id("latest")
                    }
                }
                .frame(height: model.messages.isEmpty ? 0 : 280)
                .onChange(of: model.messages.last?.text) { _, _ in proxy.scrollTo("latest", anchor: .bottom) }
            }
            if model.sending { ProgressView("Receiving response…") }
            if let error = model.errorMessage ?? voice.errorMessage {
                Text(error).font(.footnote).foregroundStyle(.orange)
            }
            Text("When Nova asks for approval, reply Confirm or Cancel in this conversation.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private var statusCard: some View {
        card("System Status") {
            if let status = model.status {
                statusRow("Jarvis tools", status.jarvis.tools_available)
                statusRow("AI planner", status.jarvis.planner_available)
                statusRow("Confirmations", status.jarvis.confirmations_available)
                statusRow("Project resolution", status.jarvis.project_resolution_available)
                Text("\(status.capabilities.read_tools.count + status.capabilities.write_tools.count + status.capabilities.destructive_tools.count) installed tools")
                    .font(.caption).foregroundStyle(.secondary)
                Text("Installed capabilities; provider availability is checked when you send a command.")
                    .font(.caption2).foregroundStyle(.secondary)
            } else { Text(model.loading ? "Checking Nova…" : "Status unavailable").foregroundStyle(.secondary) }
        }
    }

    private var composer: some View {
        VStack(spacing: 8) {
            Toggle("Speak responses", isOn: $voiceReplies).font(.caption)
                .onChange(of: voiceReplies) { _, enabled in if !enabled { voice.stop() } }
            HStack(alignment: .bottom) {
                TextField("Ask Jarvis…", text: $model.command, axis: .vertical)
                    .lineLimit(1...5).padding(12).background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 14))
                    .disabled(model.sending || voice.listening || voice.requestingPermission)
                Button(action: send) { Image(systemName: "arrow.up.circle.fill").font(.largeTitle) }
                    .accessibilityLabel("Send command")
                    .disabled(model.sending || voice.listening || voice.requestingPermission || model.command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }.padding().background(.ultraThinMaterial)
    }

    private func send() {
        voice.stop()
        voice.errorMessage = nil
        model.send(csrfToken: csrfToken) { reply in
            if visible && voiceReplies && scenePhase == .active { voice.speak(reply) }
            Task { await model.refresh() }
        }
    }

    private func statusRow(_ name: String, _ available: Bool) -> some View {
        HStack { Text(name); Spacer(); Text(available ? "Available" : "Unavailable").foregroundStyle(available ? .cyan : .orange) }.font(.subheadline)
    }

    private func card<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.headline)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(16)
        .background(.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(.cyan.opacity(0.15)))
    }
}
