import Foundation

/// Bindings describe implemented execution paths, not permission grants.
/// Server authorization, subscriptions, and tool confirmations remain authoritative.
enum AgentExecution: Equatable {
    case projects, markets
    case chat(mode: String)
}

struct AgentCapability: Identifiable {
    let id: String
    let title: String
    let execution: AgentExecution?
    var available: Bool { execution != nil }
}

struct NovaAgent: Identifiable {
    let id: String
    let name: String
    let summary: String
    let icon: String
    let execution: AgentExecution?
    let requirement: String?
    let capabilities: [AgentCapability]
    var active: Bool { execution != nil }
}

enum AgentCatalog {
    private static func capabilities(_ entries: [(String, String)], execution: AgentExecution? = nil) -> [AgentCapability] {
        entries.map { AgentCapability(id: $0.0, title: $0.1, execution: execution) }
    }

    static let agents: [NovaAgent] = [
        NovaAgent(id: "projects", name: "Project Agent", summary: "Work with your Nova projects, notes, tasks, and files.", icon: "folder", execution: .projects, requirement: nil,
                  capabilities: capabilities([("projects.read", "Browse projects"), ("tasks.read", "Read tasks"), ("tasks.create", "Create tasks in the workspace"), ("notes.read", "Read project notes"), ("files.read", "Browse project files")], execution: .projects)
                  + capabilities([("projects.manage", "Create and manage projects through the agent")])),
        NovaAgent(id: "research", name: "Research Agent", summary: "Investigate topics, compare sources, and organize findings.", icon: "magnifyingglass", execution: nil, requirement: nil,
                  capabilities: capabilities([("research.web", "Research the web"), ("research.summarize", "Summarize findings"), ("research.compare", "Compare sources"), ("research.extract", "Extract information")])),
        NovaAgent(id: "markets", name: "Markets Agent", summary: "Explore real quotes, technical indicators, and Nova market signals.", icon: "chart.xyaxis.line", execution: .markets, requirement: "Research and paper-trading analysis; no brokerage execution.",
                  capabilities: capabilities([("markets.quote", "View market quotes"), ("markets.analyze", "Analyze symbols"), ("markets.history", "Chart available price history")], execution: .markets)),
        NovaAgent(id: "study", name: "Study Agent", summary: "Understand material, review notes you provide, and prepare for exams.", icon: "book", execution: .chat(mode: "study"), requirement: "Requires an active Nova AI subscription and available usage.",
                  capabilities: capabilities([("study.explain", "Explain concepts"), ("study.quiz", "Generate practice questions"), ("study.review", "Review supplied material"), ("study.summarize", "Summarize study material")], execution: .chat(mode: "study"))),
        NovaAgent(id: "writing", name: "Writing Agent", summary: "Draft, rewrite, and improve written work while preserving your voice.", icon: "pencil.line", execution: .chat(mode: "writing"), requirement: "Requires an active Nova AI subscription and available usage.",
                  capabilities: capabilities([("writing.draft", "Draft text"), ("writing.rewrite", "Rewrite text"), ("writing.edit", "Edit wording and grammar"), ("writing.structure", "Organize written work")], execution: .chat(mode: "writing"))),
        NovaAgent(id: "coding", name: "Coding Agent", summary: "Explain code, investigate bugs, and plan or generate software changes in chat.", icon: "chevron.left.forwardslash.chevron.right", execution: .chat(mode: "coding"), requirement: "Requires Nova Max. Produces guidance and code in chat; does not execute or deploy code.",
                  capabilities: capabilities([("code.explain", "Explain code"), ("code.debug", "Help diagnose bugs"), ("code.plan", "Plan implementation"), ("code.generate", "Generate code")], execution: .chat(mode: "coding"))),
        NovaAgent(id: "productivity", name: "Productivity Agent", summary: "Turn priorities into focused plans and action items.", icon: "checklist", execution: nil, requirement: nil,
                  capabilities: capabilities([("tasks.read", "Review tasks"), ("tasks.create", "Create tasks"), ("planning.organize", "Organize work"), ("planning.prioritize", "Prioritize work")])),
        NovaAgent(id: "connections", name: "Connections Agent", summary: "Work across connected services when Nova integrations become available.", icon: "link", execution: nil, requirement: "Connected-service execution and OAuth are not available in this app.",
                  capabilities: capabilities([("connections.list", "List connections"), ("connections.capabilities", "Discover connected capabilities"), ("email.read", "Read email"), ("email.search", "Search email"), ("email.send", "Send email"), ("calendar.read", "Read calendars"), ("calendar.create", "Create events"), ("calendar.update", "Update events")])),
        NovaAgent(id: "data", name: "Data Agent", summary: "Inspect structured data, find patterns, and communicate results.", icon: "tablecells", execution: nil, requirement: nil,
                  capabilities: capabilities([("data.inspect", "Inspect datasets"), ("data.summarize", "Summarize data"), ("data.analyze", "Analyze patterns"), ("data.visualize", "Visualize results")])),
        NovaAgent(id: "business", name: "Business Agent", summary: "Support planning, proposals, customer communication, and operations.", icon: "briefcase", execution: nil, requirement: nil,
                  capabilities: capabilities([("business.plan", "Plan business work"), ("business.write", "Draft business documents"), ("business.organize", "Organize operations"), ("business.analyze", "Analyze business questions")]))
    ]
}
