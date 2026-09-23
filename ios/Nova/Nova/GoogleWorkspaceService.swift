import Foundation

enum WorkspaceOperation: String, CaseIterable {
    case search = "gmail.search", read = "gmail.read", send = "gmail.send", reply = "gmail.reply"
    case archive = "gmail.archive", trash = "gmail.trash", labels = "gmail.labels"
    case calendars = "calendar.list", agenda = "calendar.agenda", event = "calendar.read"
    case createEvent = "calendar.create", updateEvent = "calendar.update"
}
struct WorkspaceUnavailable: LocalizedError {
    var errorDescription: String? { "Nova’s authenticated workspace APIs are not available yet. No request was sent." }
}

/// An adapter must only enable operations exposed by real, authenticated APIs.
/// Catalog capabilities and a connected Google identity are NOT execution grants.
@MainActor
protocol GoogleWorkspaceService {
    var operations: Set<WorkspaceOperation> { get }
    func search(connectionId: Int, query: String, pageToken: String?) async throws -> WorkspacePage<WorkspaceMessage>
    func message(connectionId: Int, id: String) async throws -> WorkspaceMessage
    func send(connectionId: Int, draft: WorkspaceMailDraft, requestId: UUID) async throws
    func calendars(connectionId: Int) async throws -> [WorkspaceCalendar]
    func agenda(connectionId: Int, start: Date, end: Date, pageToken: String?) async throws -> WorkspacePage<WorkspaceEvent>
    func event(connectionId: Int, calendarId: String, id: String) async throws -> WorkspaceEvent
    func saveEvent(connectionId: Int, calendarId: String, id: String?, draft: WorkspaceEventDraft, requestId: UUID) async throws
}

/// Production default until backend routes and confirmation semantics are agreed.
/// No fabricated URL, network request, sample response, or successful mutation.
struct UnavailableGoogleWorkspaceService: GoogleWorkspaceService {
    let operations: Set<WorkspaceOperation> = []
    func search(connectionId: Int, query: String, pageToken: String?) async throws -> WorkspacePage<WorkspaceMessage> { throw WorkspaceUnavailable() }
    func message(connectionId: Int, id: String) async throws -> WorkspaceMessage { throw WorkspaceUnavailable() }
    func send(connectionId: Int, draft: WorkspaceMailDraft, requestId: UUID) async throws { throw WorkspaceUnavailable() }
    func calendars(connectionId: Int) async throws -> [WorkspaceCalendar] { throw WorkspaceUnavailable() }
    func agenda(connectionId: Int, start: Date, end: Date, pageToken: String?) async throws -> WorkspacePage<WorkspaceEvent> { throw WorkspaceUnavailable() }
    func event(connectionId: Int, calendarId: String, id: String) async throws -> WorkspaceEvent { throw WorkspaceUnavailable() }
    func saveEvent(connectionId: Int, calendarId: String, id: String?, draft: WorkspaceEventDraft, requestId: UUID) async throws { throw WorkspaceUnavailable() }
}
