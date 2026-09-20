import SwiftUI

struct MarketsView: View {
    let csrfToken: String
    @StateObject private var model = MarketsViewModel()
    @State private var path: [String] = []
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("Your market overview").font(.title2.bold())
                    Text("Quotes and Nova technical analysis").foregroundStyle(.secondary)
                    HStack {
                        TextField("Symbol, e.g. AAPL or BTC/USD", text: $model.search)
                            .textInputAutocapitalization(.characters).autocorrectionDisabled()
                            .submitLabel(.search).onSubmit(openSearch)
                        Button("Analyze", action: openSearch)
                            .disabled(model.search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }.padding().marketPanel()
                    Text("Market Watch").font(.headline)
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 145), spacing: 12)], spacing: 12) {
                        ForEach(MarketsViewModel.symbols, id: \.self) { symbol in
                            Button { path = [symbol] } label: { quoteCard(symbol) }.buttonStyle(.plain)
                        }
                    }
                    if let fetched = model.fetchedAt {
                        Text("Retrieved \(fetched.formatted(date: .omitted, time: .shortened)). Quotes may be cached for 60 seconds.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    if !model.errors.isEmpty {
                        Button("Reload quotes") { refreshID = UUID() }.disabled(model.loading)
                    }
                    Text("Research and paper-trading analysis. No brokerage execution.")
                        .font(.caption).foregroundStyle(.secondary)
                }.padding()
            }
            .background(marketBackground)
            .navigationTitle("Markets")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } } }
            .navigationDestination(for: String.self) { MarketDetailView(symbol: $0, csrfToken: csrfToken) }
            .task(id: refreshID) { await model.load(csrfToken: csrfToken, force: refreshID != nil) }
            .refreshable { await model.load(csrfToken: csrfToken, force: true) }
        }.preferredColorScheme(.dark).tint(.purple)
    }

    @State private var refreshID: UUID?

    private func openSearch() {
        let symbol = model.search.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !symbol.isEmpty, path.isEmpty else { return }
        path = [symbol]
    }

    private func quoteCard(_ symbol: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack { Text(symbol).font(.headline); Spacer(); Image(systemName: "chevron.right").font(.caption) }
            if let quote = model.quotes[symbol] {
                if let company = quote.company { Text(company).font(.caption).foregroundStyle(.secondary).lineLimit(2) }
                Text(marketNumber(quote.price)).font(.title3.bold()).monospacedDigit()
                Text(marketPercent(quote.change)).foregroundStyle((quote.change ?? 0) < 0 ? .orange : .mint)
            } else if let error = model.errors[symbol] {
                Text("Unavailable").foregroundStyle(.orange)
                Text(error).font(.caption).foregroundStyle(.secondary)
            } else if model.loading { ProgressView("Loading…") }
            else { Text("Not loaded").foregroundStyle(.secondary) }
        }.frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading).padding().marketPanel()
    }
}

let marketBackground = Color(red: 0.025, green: 0.03, blue: 0.07)

extension View {
    func marketPanel() -> some View {
        background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(.purple.opacity(0.18)))
    }
}

func marketNumber(_ value: Double?) -> String {
    guard let value, value.isFinite else { return "Unavailable" }
    return value.formatted(.number.precision(.fractionLength(2)))
}

func marketPercent(_ value: Double?) -> String {
    guard let value, value.isFinite else { return "Unavailable" }
    return (value > 0 ? "+" : "") + marketNumber(value) + "%"
}
