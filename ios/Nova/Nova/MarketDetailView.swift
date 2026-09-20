import SwiftUI
import Charts

struct MarketDetailView: View {
    let symbol: String
    let csrfToken: String
    @StateObject private var model = MarketDetailViewModel()
    @State private var range: MarketRange = .month
    @State private var reload = UUID()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if model.loading { ProgressView("Analyzing \(symbol)…").frame(maxWidth: .infinity).padding(40) }
                if let error = model.error {
                    ContentUnavailableView {
                        Label("Analysis unavailable", systemImage: "chart.xyaxis.line")
                    } description: { Text(error) } actions: {
                        Button("Try again") { reload = UUID() }
                    }
                }
                if let data = model.analysis {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(data.symbol).font(.largeTitle.bold())
                        if let company = data.company { Text(company).foregroundStyle(.secondary) }
                        Text(marketNumber(data.price)).font(.system(.largeTitle, design: .rounded).bold()).monospacedDigit()
                        Text("\(marketPercent(data.change)) daily").foregroundStyle((data.change ?? 0) < 0 ? .orange : .mint)
                    }
                    priceChart(data)
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 140))], spacing: 12) {
                        metric("Nova signal", data.signal ?? "Unavailable")
                        metric("Nova score", data.score.map { "\(marketNumber($0)) / 100" } ?? "Unavailable")
                        metric("RSI", marketNumber(data.rsi))
                        metric("MA20", marketNumber(data.ma20))
                        metric("MA50", marketNumber(data.ma50))
                        metric("5-day momentum", marketPercent(data.momentum))
                        metric("Volatility", data.volatility.map { marketNumber($0) + "%" } ?? "Unavailable")
                        metric("Risk", data.risk ?? "Unavailable")
                    }
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Nova reasoning").font(.headline)
                        Text(data.reason ?? "No reasoning returned.").textSelection(.enabled)
                    }.frame(maxWidth: .infinity, alignment: .leading).padding().marketPanel()
                    Text("Server analysis may be cached for five minutes. Prices are shown in the instrument’s quote units; Nova does not return currency metadata.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }.padding()
        }
        .background(marketBackground)
        .navigationTitle(symbol).navigationBarTitleDisplayMode(.inline)
        .task(id: reload) { await model.load(symbol: symbol, csrfToken: csrfToken) }
        .refreshable { await model.load(symbol: symbol, csrfToken: csrfToken) }
    }

    private func metric(_ name: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(name).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.headline)
        }.frame(maxWidth: .infinity, minHeight: 60, alignment: .leading).padding().marketPanel()
    }

    private func priceChart(_ data: MarketAnalysis) -> some View {
        let history = data.history
        let end = history.last?.date ?? Date()
        let start = range.start(ending: end)
        let points = history.filter { $0.date >= start }
        return VStack(alignment: .leading, spacing: 14) {
            Text("Daily closing prices").font(.headline)
            Picker("Chart range", selection: $range) {
                ForEach(MarketRange.allCases, id: \.self) { Text($0.rawValue).tag($0) }
            }.pickerStyle(.segmented)
            if points.count >= 2 {
                Chart(points) { point in
                    LineMark(x: .value("Date", point.date), y: .value("Close", point.price))
                        .foregroundStyle(.purple).interpolationMethod(.linear)
                }
                .chartYScale(domain: .automatic(includesZero: false))
                .frame(height: 230)
                Text("\(points.first!.date.formatted(date: .abbreviated, time: .omitted)) – \(end.formatted(date: .abbreviated, time: .omitted)) · \(points.count) observations")
                    .font(.caption).foregroundStyle(.secondary)
                if let first = history.first, first.date > start {
                    Text("Partial \(range.rawValue) history: showing only dates returned by Nova.")
                        .font(.caption).foregroundStyle(.orange)
                }
            } else { Text("Not enough dated price history for this range.").foregroundStyle(.secondary).frame(height: 150) }
        }.padding().marketPanel()
    }
}
