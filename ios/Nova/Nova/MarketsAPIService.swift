import Foundation

struct MarketQuote: Decodable, Sendable {
    let symbol: String
    let company: String?
    let price: Double?
    let change: Double?
}

struct MarketAnalysis: Decodable, Sendable {
    let symbol: String
    let company: String?
    let price: Double?
    let change: Double?
    let signal: String?
    let score: Double?
    let rsi: Double?
    let ma20: Double?
    let ma50: Double?
    let momentum: Double?
    let volatility: Double?
    let risk: String?
    let reason: String?
    let chart_dates: [String]?
    let chart_prices: [Double]?

    var history: [MarketPricePoint] {
        guard let dates = chart_dates, let prices = chart_prices, dates.count == prices.count else { return [] }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        var points: [MarketPricePoint] = []
        for (date, price) in zip(dates, prices) {
            guard let parsed = formatter.date(from: date), price.isFinite else { return [] }
            points.append(MarketPricePoint(date: parsed, price: price))
        }
        guard Set(points.map(\.date)).count == points.count else { return [] }
        return points.sorted { $0.date < $1.date }
    }
}

struct MarketPricePoint: Identifiable {
    let date: Date
    let price: Double
    var id: Date { date }
}

enum MarketRange: String, CaseIterable {
    case week = "1W", month = "1M", quarter = "3M"

    func start(ending date: Date) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        switch self {
        case .week: return calendar.date(byAdding: .day, value: -7, to: date)!
        case .month: return calendar.date(byAdding: .month, value: -1, to: date)!
        case .quarter: return calendar.date(byAdding: .month, value: -3, to: date)!
        }
    }
}

struct MarketsFailure: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Same session and cookie storage used by Nova's existing native sign-in.
struct MarketsAPIService: Sendable {
    private struct ErrorResponse: Decodable { let error: String?; let message: String? }
    let csrfToken: String

    func quote(_ symbol: String) async throws -> MarketQuote {
        try await post("quote", symbol: symbol)
    }

    func analyze(_ symbol: String) async throws -> MarketAnalysis {
        try await post("analyze", symbol: symbol)
    }

    private func post<T: Decodable>(_ endpoint: String, symbol: String) async throws -> T {
        let url = URL(string: "https://workfieldhq.com/api/markets/\(endpoint)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 45
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        // These read-only POST routes are not currently in Flask's CSRF-protected
        // endpoint set. Send the existing token consistently with native Nova.
        if !csrfToken.isEmpty { request.setValue(csrfToken, forHTTPHeaderField: "X-CSRF-Token") }
        request.httpBody = try JSONEncoder().encode(["symbol": symbol])
        let (data, response) = try await URLSession.shared.data(for: request)
        try Task.checkCancellation()
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        if http.statusCode == 401 || http.url?.path == "/login" {
            throw MarketsFailure(message: "Your Nova session expired. Please sign in again.")
        }
        let failure = try? JSONDecoder().decode(ErrorResponse.self, from: data)
        if !(200..<300).contains(http.statusCode) || failure?.error != nil {
            throw MarketsFailure(message: failure?.message ?? failure?.error ?? "Markets returned HTTP \(http.statusCode). Please try again.")
        }
        guard http.mimeType == "application/json" else {
            throw MarketsFailure(message: "Nova returned an unexpected market response.")
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw MarketsFailure(message: "Nova returned unreadable market data. Please try again.") }
    }
}
