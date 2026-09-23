import Foundation

// Proposed transport DTOs, not a claim that these APIs are deployed.
struct WorkspacePage<Item: Decodable>: Decodable {
    let items: [Item]
    let nextPageToken: String?
}
struct WorkspaceAddress: Codable, Hashable {
    var name: String?
    var email: String
    var display: String { name.map { "\($0) <\(email)>" } ?? email }
}
struct WorkspaceMessage: Decodable, Identifiable {
    let id: String
    let threadId: String
    let subject: String
    let from: WorkspaceAddress
    let to: [WorkspaceAddress]
    let replyTo: [WorkspaceAddress]
    let receivedAt: Date
    let snippet: String
    let bodyText: String?
    let unread: Bool
    let labelIds: [String]
}
struct WorkspaceMailDraft: Encodable {
    var to: [WorkspaceAddress]
    var subject: String
    var bodyText: String
    var replyToMessageId: String?
}
struct WorkspaceCalendar: Decodable, Identifiable {
    let id: String
    let summary: String
    let timeZone: String
    let writable: Bool
}
struct WorkspaceEvent: Decodable, Identifiable {
    let id: String
    let calendarId: String
    let version: String
    let title: String
    let description: String?
    let location: String?
    let timing: WorkspaceEventTiming
    let writable: Bool
}
/// All-day dates are calendar dates, never UTC instants. End is exclusive.
enum WorkspaceEventTiming: Codable {
    case timed(start: Date, end: Date, timeZone: String)
    case allDay(startDate: String, endDateExclusive: String)

    private enum CodingKeys: String, CodingKey { case kind, start, end, timeZone, startDate, endDateExclusive }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        switch try values.decode(String.self, forKey: .kind) {
        case "timed":
            let start = try values.decode(Date.self, forKey: .start)
            let end = try values.decode(Date.self, forKey: .end)
            let zone = try values.decode(String.self, forKey: .timeZone)
            guard end > start, TimeZone(identifier: zone) != nil else {
                throw DecodingError.dataCorruptedError(forKey: .end, in: values, debugDescription: "Invalid event interval or timezone")
            }
            self = .timed(start: start, end: end, timeZone: zone)
        case "all_day":
            let start = try values.decode(String.self, forKey: .startDate)
            let end = try values.decode(String.self, forKey: .endDateExclusive)
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = TimeZone(secondsFromGMT: 0)
            formatter.dateFormat = "yyyy-MM-dd"
            guard let first = formatter.date(from: start), let last = formatter.date(from: end),
                  formatter.string(from: first) == start, formatter.string(from: last) == end, last > first else {
                throw DecodingError.dataCorruptedError(forKey: .endDateExclusive, in: values, debugDescription: "Invalid all-day dates")
            }
            self = .allDay(startDate: start, endDateExclusive: end)
        default: throw DecodingError.dataCorruptedError(forKey: .kind, in: values, debugDescription: "Unknown event timing")
        }
    }
    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case let .timed(start, end, timeZone):
            try values.encode("timed", forKey: .kind)
            try values.encode(start, forKey: .start)
            try values.encode(end, forKey: .end)
            try values.encode(timeZone, forKey: .timeZone)
        case let .allDay(start, end):
            try values.encode("all_day", forKey: .kind)
            try values.encode(start, forKey: .startDate)
            try values.encode(end, forKey: .endDateExclusive)
        }
    }
    var display: String {
        switch self {
        case let .timed(start, end, zone):
            let formatter = DateFormatter()
            formatter.timeZone = TimeZone(identifier: zone)
            formatter.dateStyle = .medium; formatter.timeStyle = .short
            return "\(formatter.string(from: start)) – \(formatter.string(from: end)) · \(zone)"
        case let .allDay(start, end): return "All day · \(start) to \(end) (end exclusive)"
        }
    }
}
struct WorkspaceEventDraft: Encodable {
    var title: String
    var description: String
    var location: String
    var timing: WorkspaceEventTiming
    var expectedVersion: String?
}
