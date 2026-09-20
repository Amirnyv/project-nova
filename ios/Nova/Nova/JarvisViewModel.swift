import Foundation
import Combine

enum JarvisState: String {
    case ready = "Ready", listening = "Listening", thinking = "Thinking"
    case executing = "Executing", speaking = "Speaking", complete = "Complete", error = "Error"
}

@MainActor
final class JarvisViewModel: ObservableObject {
    struct TaskRow: Identifiable {
        let project: NovaProject
        let task: NovaProjectTask
        var id: String { "\(project.id)-\(task.id)" }
    }
    @Published var state: JarvisState = .ready
    @Published var command = ""
    @Published var messages: [ChatMessage] = []
    @Published var status: JarvisStatus?
    @Published var projects: [NovaProject] = []
    @Published var tasks: [TaskRow] = []
    @Published var dashboardError: String?
    @Published var errorMessage: String?
    @Published var loading = false
    @Published var sending = false
    private(set) var conversationID: Int?
    private let api = JarvisAPIService()
    private let agentMode: String

    init(agentMode: String = "default") { self.agentMode = agentMode }
    private var requestTask: Task<Void, Never>?

    func refresh() async {
        guard !loading else { return }
        loading = true
        dashboardError = nil
        defer { loading = false }
        do { status = try await api.get("api/jarvis/status") }
        catch { status = nil; dashboardError = error.localizedDescription }
        do {
            let result: NovaProjectsResponse = try await api.get("api/projects")
            projects = result.projects
            var rows: [TaskRow] = []
            for project in projects {
                try Task.checkCancellation()
                do {
                    let result: NovaProjectTasksResponse = try await api.get("api/projects/\(project.id)/tasks")
                    rows += result.tasks.filter { !$0.completed }.map { TaskRow(project: project, task: $0) }
                } catch {
                    dashboardError = "Some tasks could not be loaded. \(error.localizedDescription)"
                }
            }
            tasks = rows
        } catch { projects = []; tasks = []; dashboardError = error.localizedDescription }
    }

    func send(csrfToken: String, completion: @escaping (String) -> Void) {
        let text = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        command = ""
        errorMessage = nil
        sending = true
        state = .thinking
        messages.append(ChatMessage(role: "user", text: text))
        messages.append(ChatMessage(role: "assistant", text: ""))
        let index = messages.count - 1
        requestTask = Task {
            defer { sending = false; requestTask = nil }
            do {
                try await api.chat(message: text, conversationID: conversationID, csrfToken: csrfToken, agentMode: agentMode) { event in
                    if let id = event.conversation_id { self.conversationID = id }
                    if event.type == "delta" {
                        // The backend exposes response deltas, not separate tool progress events.
                        self.state = .executing
                        self.messages[index].text += event.delta ?? ""
                    } else if event.type == "done" {
                        if let reply = event.reply { self.messages[index].text = reply }
                        else if self.messages[index].text.isEmpty { self.messages[index].text = event.message ?? "" }
                    }
                }
                try Task.checkCancellation()
                state = .complete
                sending = false
                completion(messages[index].text)
            } catch {
                state = .error
                if !Task.isCancelled { errorMessage = error.localizedDescription }
                if messages[index].text.isEmpty { messages[index].text = "No response received." }
            }
        }
    }

    func stop() {
        if sending {
            requestTask?.cancel()
            errorMessage = "Response interrupted. A server action may still finish; check your tasks before repeating it."
            state = .error
        }
    }
}
