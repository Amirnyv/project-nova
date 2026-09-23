import Foundation
import Combine

enum WorkspaceLoadState: Equatable { case unavailable, idle, loading, empty, loaded, error(String) }

@MainActor
final class GoogleWorkspaceViewModel: ObservableObject {
    let service: any GoogleWorkspaceService
    @Published var connectionId: Int?
    @Published var query = ""
    @Published private(set) var mailState: WorkspaceLoadState = .unavailable
    @Published private(set) var agendaState: WorkspaceLoadState = .unavailable
    @Published private(set) var messages: [WorkspaceMessage] = []
    @Published private(set) var events: [WorkspaceEvent] = []
    @Published private(set) var mailPage: String?
    @Published private(set) var agendaPage: String?
    private var mailGeneration = UUID()
    private var agendaGeneration = UUID()

    init(service: (any GoogleWorkspaceService)? = nil) { self.service = service ?? UnavailableGoogleWorkspaceService() }
    func enabled(_ operation: WorkspaceOperation) -> Bool { connectionId != nil && service.operations.contains(operation) }
    func resetAccount() {
        resetMail(); resetAgenda()
    }
    func resetMail() {
        mailGeneration = UUID(); messages = []; mailPage = nil
        mailState = enabled(.search) ? .idle : .unavailable
    }
    func resetAgenda() {
        agendaGeneration = UUID(); events = []; agendaPage = nil
        agendaState = enabled(.agenda) ? .idle : .unavailable
    }
    func search(more: Bool = false) async {
        guard enabled(.search), let connectionId else { mailState = .unavailable; return }
        guard mailState != .loading else { return }
        let generation = UUID(); mailGeneration = generation
        let token = more ? mailPage : nil
        if more && token == nil { return }
        mailState = .loading
        do {
            let result = try await service.search(connectionId: connectionId, query: query, pageToken: token)
            try Task.checkCancellation()
            guard generation == mailGeneration else { return }
            let combined = (more ? messages : []) + result.items
            var ids = Set<String>()
            messages = combined.filter { ids.insert($0.id).inserted }
            mailPage = result.nextPageToken
            mailState = messages.isEmpty ? .empty : .loaded
        } catch {
            guard generation == mailGeneration else { return }
            mailState = Task.isCancelled ? .idle : .error(error.localizedDescription)
        }
    }
    func loadAgenda(start: Date, more: Bool = false) async {
        guard enabled(.agenda), let connectionId else { agendaState = .unavailable; return }
        guard agendaState != .loading else { return }
        let generation = UUID(); agendaGeneration = generation
        let token = more ? agendaPage : nil
        if more && token == nil { return }
        agendaState = .loading
        do {
            let end = Calendar.current.date(byAdding: .day, value: 7, to: start)!
            let result = try await service.agenda(connectionId: connectionId, start: start, end: end, pageToken: token)
            try Task.checkCancellation()
            guard generation == agendaGeneration else { return }
            var ids = Set<String>()
            events = ((more ? events : []) + result.items).filter { ids.insert("\($0.calendarId):\($0.id)").inserted }
            agendaPage = result.nextPageToken
            agendaState = events.isEmpty ? .empty : .loaded
        } catch {
            guard generation == agendaGeneration else { return }
            agendaState = Task.isCancelled ? .idle : .error(error.localizedDescription)
        }
    }
}
