import Foundation

@MainActor
final class TestWorkspaceService: GoogleWorkspaceService {
    let operations: Set<WorkspaceOperation> = [.search, .agenda]
    var shouldFail = false
    var delay = false
    var calls = 0
    private let unavailable = UnavailableGoogleWorkspaceService()
    func search(connectionId: Int, query: String, pageToken: String?) async throws -> WorkspacePage<WorkspaceMessage> {
        calls += 1
        if delay { try await Task.sleep(for: .seconds(10)) }
        if shouldFail { throw WorkspaceUnavailable() }
        return WorkspacePage(items: [], nextPageToken: nil)
    }
    func agenda(connectionId: Int, start: Date, end: Date, pageToken: String?) async throws -> WorkspacePage<WorkspaceEvent> {
        if shouldFail { throw WorkspaceUnavailable() }
        return WorkspacePage(items: [], nextPageToken: nil)
    }
    func message(connectionId: Int, id: String) async throws -> WorkspaceMessage { throw WorkspaceUnavailable() }
    func send(connectionId: Int, draft: WorkspaceMailDraft, requestId: UUID) async throws { throw WorkspaceUnavailable() }
    func calendars(connectionId: Int) async throws -> [WorkspaceCalendar] { throw WorkspaceUnavailable() }
    func event(connectionId: Int, calendarId: String, id: String) async throws -> WorkspaceEvent { throw WorkspaceUnavailable() }
    func saveEvent(connectionId: Int, calendarId: String, id: String?, draft: WorkspaceEventDraft, requestId: UUID) async throws { throw WorkspaceUnavailable() }
}

@main struct WorkspaceChecks {
    @MainActor static func main() async throws {
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let message = try decoder.decode(WorkspaceMessage.self, from: Data(#"{"id":"fixture","threadId":"thread","subject":"","from":{"name":null,"email":"fixture@example.invalid"},"to":[],"replyTo":[],"receivedAt":"2026-09-22T12:00:00Z","snippet":"","bodyText":null,"unread":true,"labelIds":[]}"#.utf8))
        precondition(message.bodyText == nil && message.unread && message.replyTo.isEmpty)
        let timing = try decoder.decode(WorkspaceEventTiming.self, from: Data(#"{"kind":"all_day","startDate":"2026-09-22","endDateExclusive":"2026-09-23"}"#.utf8))
        if case .allDay(let first, let end) = timing { precondition(first == "2026-09-22" && end == "2026-09-23") }
        else { fatalError("Expected all-day date semantics") }
        for invalid in [#"{"kind":"all_day","startDate":"2026-02-30","endDateExclusive":"2026-03-02"}"#, #"{"kind":"timed","start":"2026-09-22T12:00:00Z","end":"2026-09-22T11:00:00Z","timeZone":"UTC"}"#] {
            do { _ = try decoder.decode(WorkspaceEventTiming.self, from: Data(invalid.utf8)); fatalError("Invalid interval accepted") }
            catch is DecodingError {}
        }
        let shipping = GoogleWorkspaceViewModel()
        shipping.connectionId = 1
        await shipping.search(); await shipping.loadAgenda(start: Date())
        precondition(shipping.mailState == .unavailable && shipping.agendaState == .unavailable)
        precondition(shipping.service.operations.isEmpty && shipping.messages.isEmpty && shipping.events.isEmpty)
        do { try await shipping.service.send(connectionId: 1, draft: .init(to: [], subject: "", bodyText: "", replyToMessageId: nil), requestId: UUID()); fatalError("Unavailable send succeeded") }
        catch is WorkspaceUnavailable {}
        let stub = TestWorkspaceService()
        let model = GoogleWorkspaceViewModel(service: stub)
        await model.search()
        precondition(stub.calls == 0, "Missing account must not dispatch")
        model.connectionId = 1; model.resetAccount()
        precondition(model.mailState == .idle)
        await model.search(); await model.loadAgenda(start: Date())
        precondition(model.mailState == .empty && model.agendaState == .empty)
        stub.shouldFail = true; await model.search()
        if case .error = model.mailState {} else { fatalError("Expected error state") }
        stub.shouldFail = false; stub.delay = true
        let task = Task { await model.search() }
        while model.mailState != .loading { await Task.yield() }
        let count = stub.calls
        await model.search()
        precondition(stub.calls == count, "Duplicate loading request dispatched")
        task.cancel(); await task.value
        precondition(model.mailState == .idle)
        let stale = Task { await model.search() }
        while model.mailState != .loading { await Task.yield() }
        model.connectionId = nil; model.resetAccount(); stale.cancel(); await stale.value
        precondition(model.mailState == .unavailable && model.messages.isEmpty)
        print("PASS: DTO decoding, date validation, unavailable transport, account gating, empty/error/loading/cancellation states, duplicate prevention, stale-account reset")
    }
}
