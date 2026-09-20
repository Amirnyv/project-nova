import Foundation
import Combine

@MainActor
final class MarketsViewModel: ObservableObject {
    static let symbols = ["SPY", "QQQ", "BTC/USD", "ETH/USD", "AAPL", "TSLA", "NVDA", "AMZN", "MSFT"]
    @Published var search = ""
    @Published private(set) var quotes: [String: MarketQuote] = [:]
    @Published private(set) var errors: [String: String] = [:]
    @Published private(set) var loading = false
    @Published private(set) var fetchedAt: Date?

    func load(csrfToken: String, force: Bool = false) async {
        guard !loading else { return }
        if !force, let fetchedAt, Date().timeIntervalSince(fetchedAt) < 60 { return }
        loading = true
        errors = [:]
        quotes = [:]
        defer { loading = false }
        let api = MarketsAPIService(csrfToken: csrfToken)
        // Three independent requests at a time; publish each result as it arrives.
        await withTaskGroup(of: (String, MarketQuote?, String?).self) { group in
            var next = 0
            func enqueue(_ symbol: String) {
                group.addTask {
                    do { return (symbol, try await api.quote(symbol), nil) }
                    catch { return (symbol, nil, error.localizedDescription) }
                }
            }
            for _ in 0..<3 { enqueue(Self.symbols[next]); next += 1 }
            for await (symbol, quote, error) in group {
                if Task.isCancelled { group.cancelAll(); break }
                quotes[symbol] = quote
                errors[symbol] = error
                if next < Self.symbols.count { enqueue(Self.symbols[next]); next += 1 }
            }
        }
        if !Task.isCancelled { fetchedAt = Date() }
    }
}

@MainActor
final class MarketDetailViewModel: ObservableObject {
    @Published private(set) var analysis: MarketAnalysis?
    @Published private(set) var loading = false
    @Published private(set) var error: String?
    @Published private(set) var fetchedAt: Date?
    private var generation = UUID()

    func load(symbol: String, csrfToken: String) async {
        guard !loading else { return }
        let token = UUID()
        generation = token
        loading = true
        error = nil
        analysis = nil
        defer { if generation == token { loading = false } }
        do {
            let result = try await MarketsAPIService(csrfToken: csrfToken).analyze(symbol)
            try Task.checkCancellation()
            guard generation == token else { return }
            analysis = result
            fetchedAt = Date()
        } catch {
            guard generation == token, !Task.isCancelled else { return }
            self.error = error.localizedDescription
        }
    }
}
