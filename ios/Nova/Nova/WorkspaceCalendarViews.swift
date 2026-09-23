import SwiftUI

struct WorkspaceEventDetail: View {
    let event: WorkspaceEvent
    let service: any GoogleWorkspaceService
    let connectionId: Int?
    @State private var current: WorkspaceEvent?
    @State private var state: WorkspaceLoadState = .idle
    @State private var editing = false
    @State private var reload = UUID()
    var body: some View {
        List {
            let item = current ?? event
            Section {
                Text(item.title).font(.title2.bold())
                Text(item.timing.display)
                if let location = item.location, !location.isEmpty { Label(location, systemImage: "mappin") }
                if let description = item.description { Text(description).textSelection(.enabled) }
            }
            Section {
                WorkspaceStateView(state: state, empty: "Event unavailable.") { reload = UUID() }
                Button("Edit event draft") { editing = true }.disabled(current == nil || !item.writable)
            }
        }.workspaceStyle().navigationTitle("Event").navigationBarTitleDisplayMode(.inline)
        .task(id: reload) {
            guard let connectionId, service.operations.contains(.event) else { state = .unavailable; return }
            state = .loading
            do {
                let result = try await service.event(connectionId: connectionId, calendarId: event.calendarId, id: event.id)
                try Task.checkCancellation(); current = result; state = .loaded
            } catch { state = Task.isCancelled ? .idle : .error(error.localizedDescription) }
        }
        .sheet(isPresented: $editing, onDismiss: { reload = UUID() }) {
            WorkspaceEventEditor(service: service, connectionId: connectionId, event: current)
        }
    }
}

struct WorkspaceEventEditor: View {
    let service: any GoogleWorkspaceService
    let connectionId: Int?
    let event: WorkspaceEvent?
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var location = ""
    @State private var notes = ""
    @State private var start = Date()
    @State private var end = Date().addingTimeInterval(3600)
    @State private var zone = TimeZone.current.identifier
    @State private var allDay = false
    @State private var calendarId: String?
    @State private var calendars: [WorkspaceCalendar] = []
    @State private var saving = false
    @State private var error: String?
    @State private var initialized = false
    @State private var confirm = false
    @State private var discard = false
    @State private var requestId = UUID()
    private var available: Bool {
        connectionId != nil && calendarId != nil && service.operations.contains(event == nil ? .createEvent : .updateEvent) && (event?.writable ?? true)
    }
    private var valid: Bool {
        !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && end > start && TimeZone(identifier: zone) != nil && (!allDay || day(end) > day(start))
    }
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Local draft only. Calendar APIs are not implemented yet; no event will be created or changed.").font(.footnote).foregroundStyle(.secondary)
                    TextField("Event title", text: $title)
                    if let event { LabeledContent("Calendar", value: event.calendarId) }
                    else {
                        Picker("Calendar", selection: $calendarId) {
                            Text("Unavailable").tag(nil as String?)
                            ForEach(calendars.filter(\.writable)) { Text($0.summary).tag(Optional($0.id)) }
                        }.disabled(calendars.isEmpty)
                    }
                    Toggle("All-day event", isOn: $allDay)
                    DatePicker("Start", selection: $start, displayedComponents: allDay ? [.date] : [.date, .hourAndMinute])
                    DatePicker(allDay ? "End date (exclusive)" : "End", selection: $end, displayedComponents: allDay ? [.date] : [.date, .hourAndMinute])
                    if !allDay {
                        Picker("Time zone", selection: $zone) {
                            ForEach(TimeZone.knownTimeZoneIdentifiers, id: \.self) { Text($0).tag($0) }
                        }
                    }
                    if end <= start || (allDay && day(end) <= day(start)) { Text("End must be after start.").foregroundStyle(.orange) }
                    TextField("Location", text: $location)
                }
                Section("Description") { TextEditor(text: $notes).frame(minHeight: 140).accessibilityLabel("Event description") }
                if let error { Section { Text(error).foregroundStyle(.orange) } }
                Section {
                    Button(saving ? "Saving…" : event == nil ? "Create event" : "Save changes") { confirm = true }.disabled(!available || !valid || saving)
                    if !available { Label("Saving is unavailable", systemImage: "lock").font(.caption).foregroundStyle(.secondary) }
                }
            }
            .environment(\.timeZone, TimeZone(identifier: zone) ?? .current)
            .workspaceStyle().disabled(saving)
            .navigationTitle(event == nil ? "New event" : "Edit event").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { discard = true }.disabled(saving) } }
            .confirmationDialog("Discard this local draft?", isPresented: $discard) { Button("Discard", role: .destructive) { dismiss() } }
            .confirmationDialog("Save this event to Google Calendar?", isPresented: $confirm) { Button("Save event") { Task { await save() } } }
        }.interactiveDismissDisabled()
        .task {
            guard !initialized else { return }; initialized = true
            if let event {
                title = event.title; notes = event.description ?? ""; location = event.location ?? ""; calendarId = event.calendarId
                switch event.timing {
                case let .timed(first, last, timeZone): start = first; end = last; zone = timeZone
                case let .allDay(first, last):
                    allDay = true; zone = "GMT"
                    let formatter = dateFormatter()
                    if let first = formatter.date(from: first), let last = formatter.date(from: last) { start = first; end = last }
                }
            }
            if event == nil, let connectionId, service.operations.contains(.calendars) {
                do { calendars = try await service.calendars(connectionId: connectionId) }
                catch { if !Task.isCancelled { self.error = error.localizedDescription } }
            }
        }
    }
    private func dateFormatter() -> DateFormatter {
        let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: zone); formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }
    private func day(_ date: Date) -> String { dateFormatter().string(from: date) }
    private func save() async {
        guard available, valid, !saving, let connectionId, let calendarId else { return }
        saving = true; error = nil
        defer { saving = false }
        let timing: WorkspaceEventTiming = allDay ? .allDay(startDate: day(start), endDateExclusive: day(end)) : .timed(start: start, end: end, timeZone: zone)
        do {
            try await service.saveEvent(connectionId: connectionId, calendarId: calendarId, id: event?.id, draft: .init(title: title, description: notes, location: location, timing: timing, expectedVersion: event?.version), requestId: requestId)
            dismiss()
        } catch { self.error = "\(error.localizedDescription) Check the calendar before retrying." }
    }
}
