import { useEffect, useMemo, useState } from "react";

const ACTION_COPY = {
  add: "ADD",
  hold: "HOLD",
  trim: "TRIM",
  avoid: "AVOID",
  watch: "WATCH",
};

function labelClass(label) {
  if (!label) return "";
  if (label.includes("buy")) return "pos";
  if (label.includes("sell")) return "neg";
  if (label === "conflicting" || label === "unavailable") return "warn";
  return "mut";
}

export default function App() {
  const [users, setUsers] = useState([]);
  const [market, setMarket] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [userId, setUserId] = useState("priya");
  const [symbol, setSymbol] = useState("RELIANCE");
  const [scenario, setScenario] = useState("base");
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const user = useMemo(() => users.find((u) => u.user_id === userId), [users, userId]);

  async function loadStatic() {
    const [u, m, s] = await Promise.all([
      fetch("/api/users").then((r) => r.json()),
      fetch("/api/market").then((r) => r.json()),
      fetch("/api/sessions").then((r) => r.json()),
    ]);
    setUsers(u);
    setMarket(m);
    setSessions(s);
  }

  useEffect(() => {
    loadStatic().catch((e) => setError(String(e)));
    const id = setInterval(() => {
      fetch("/api/market")
        .then((r) => r.json())
        .then(setMarket)
        .catch(() => {});
    }, 4000);
    return () => clearInterval(id);
  }, []);

  async function run(next = {}) {
    const body = {
      symbol: next.symbol ?? symbol,
      user_id: next.user_id ?? userId,
      scenario: next.scenario ?? scenario,
    };
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setAnalysis(data);
      const [m, s] = await Promise.all([
        fetch("/api/market").then((r) => r.json()),
        fetch("/api/sessions").then((r) => r.json()),
      ]);
      setMarket(m);
      setSessions(s);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (users.length) run({ symbol: "RELIANCE", user_id: "priya", scenario: "base" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [users.length]);

  const rec = analysis?.recommendation;
  const tick = analysis?.tick;

  return (
    <div className="shell">
      <header className="top">
        <div>
          <p className="kicker">PS-01 · India retail</p>
          <h1>FinIntel</h1>
          <p className="sub">
            Multi-agent research: tape, filings, flows — personalized and cited in one pass.
          </p>
        </div>
        <div className="controls">
          <label>
            Investor
            <select
              value={userId}
              onChange={(e) => {
                setUserId(e.target.value);
                run({ user_id: e.target.value });
              }}
            >
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.name} · {u.risk_tolerance}
                </option>
              ))}
            </select>
          </label>
          <label>
            Scenario
            <select
              value={scenario}
              onChange={(e) => {
                setScenario(e.target.value);
                run({ scenario: e.target.value });
              }}
            >
              <option value="base">Base (full data)</option>
              <option value="feed_down">Degraded: feed down</option>
              <option value="missing_filing">Degraded: missing filing</option>
              <option value="conflict">Conflict: Zomato tape vs filings</option>
            </select>
          </label>
          <button disabled={busy} onClick={() => run()}>
            {busy ? "Running agents…" : "Re-run research"}
          </button>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="tape">
        {market.map((t) => (
          <button
            key={t.symbol}
            className={`chip ${symbol === t.symbol ? "on" : ""} ${t.change_pct >= 0 ? "up" : "dn"}`}
            onClick={() => {
              setSymbol(t.symbol);
              run({ symbol: t.symbol });
            }}
          >
            <span className="sym">{t.symbol}</span>
            <span className="px">₹{Number(t.last).toFixed(2)}</span>
            <span className="ch">
              {t.change_pct >= 0 ? "+" : ""}
              {Number(t.change_pct).toFixed(2)}%
            </span>
            <span className="st">{t.feed_status}</span>
          </button>
        ))}
      </section>

      <main className="grid">
        <article className="card rec">
          <h2>Synthesized recommendation</h2>
          {rec && tick ? (
            <>
              <div className={`action ${rec.action}`}>
                <span>{ACTION_COPY[rec.action]}</span>
                <strong>{rec.symbol}</strong>
                <em>{Math.round(rec.confidence * 100)}% confidence</em>
              </div>
              <p className="headline">{rec.headline}</p>
              <p className="rationale">{rec.rationale}</p>
              {rec.personalization_notes?.length ? (
                <ul className="notes">
                  {rec.personalization_notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              ) : null}
              {rec.conflicts?.length ? (
                <div className="conflict">
                  {rec.conflicts.map((c) => (
                    <p key={c}>{c}</p>
                  ))}
                </div>
              ) : null}
              <h3>Source attribution</h3>
              <ul className="cites">
                {rec.citations.map((c) => (
                  <li key={c.source_id}>
                    <strong>{c.title}</strong>
                    <span>
                      {c.source_id} · {c.as_of}
                      {c.score != null ? ` · sim ${c.score}` : ""}
                    </span>
                    <p>{c.excerpt}</p>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="mut">Waiting for first research pass.</p>
          )}
        </article>

        <article className="card">
          <h2>Signal classification</h2>
          <ul className="signals">
            {(analysis?.signals || []).map((s) => (
              <li key={s.dimension}>
                <header>
                  <span>{s.dimension.replaceAll("_", " ")}</span>
                  <b className={labelClass(s.label)}>{s.label.replaceAll("_", " ")}</b>
                </header>
                <p>
                  score {s.score.toFixed(2)} · conf {Math.round(s.confidence * 100)}%
                  {s.degraded ? " · degraded" : ""}
                </p>
                <p>{s.reasoning}</p>
              </li>
            ))}
          </ul>
        </article>

        <article className="card">
          <h2>Agent traces</h2>
          <ul className="agents">
            {(analysis?.agents || []).map((a) => (
              <li key={a.agent_id}>
                <header>
                  <span>{a.agent_id}</span>
                  <b className={a.stance}>{a.stance}</b>
                  {a.degraded ? <i>degraded</i> : null}
                </header>
                <p className="role">{a.role}</p>
                <p>{a.thesis}</p>
                <p className="meta">
                  conf {Math.round(a.confidence * 100)}% · weight {a.weight_applied ?? "—"} · {a.latency_ms} ms
                </p>
                {a.citations.map((c) => (
                  <p key={c.source_id} className="cite-inline">
                    ↳ {c.title}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        </article>

        <article className="card">
          <h2>Portfolio / watchlist</h2>
          {user ? (
            <>
              <p className="meta">
                {user.name} · {user.age}y · horizon {user.horizon_years}y · max name{" "}
                {Math.round(user.max_single_name_pct * 100)}% · F&O{" "}
                {user.fno_allowed ? "on" : "blocked"}
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Qty</th>
                    <th>Avg</th>
                    <th>Last</th>
                    <th>P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {(analysis?.portfolio || user.holdings).map((h) => {
                    const last = h.last ?? h.avg_cost;
                    const pnl = ((last - h.avg_cost) / h.avg_cost) * 100;
                    return (
                      <tr key={h.symbol}>
                        <td>{h.symbol}</td>
                        <td>{h.qty}</td>
                        <td>₹{h.avg_cost.toFixed(0)}</td>
                        <td>₹{Number(last).toFixed(2)}</td>
                        <td className={pnl >= 0 ? "pos" : "neg"}>{pnl.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="meta">Watchlist: {(user.watchlist || []).join(" · ")}</p>
            </>
          ) : null}
        </article>

        <article className="card span">
          <h2>Reasoning chain</h2>
          <ol className="chain">
            {(analysis?.reasoning_chain || []).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </article>

        <article className="card">
          <h2>Session metrics</h2>
          {analysis?.metrics ? (
            <ul className="metrics">
              <li>
                <span>Agent latency (max parallel)</span>
                <b>{analysis.metrics.agent_response_latency_ms} ms</b>
              </li>
              <li>
                <span>Signal accuracy vs 30d forward return</span>
                <b>
                  {analysis.metrics.signal_accuracy_proxy == null
                    ? "n/a (degraded)"
                    : analysis.metrics.signal_accuracy_proxy
                      ? "aligned"
                      : "miss"}
                </b>
              </li>
              <li>
                <span>Portfolio HHI concentration</span>
                <b>{analysis.metrics.portfolio_risk_concentration}</b>
              </li>
              <li>
                <span>Degraded agents</span>
                <b>{analysis.metrics.degraded_agents}</b>
              </li>
            </ul>
          ) : null}
          <h3>Recent sessions</h3>
          <ul className="log">
            {sessions.slice(0, 8).map((s) => (
              <li key={s.session_id}>
                {s.session_id} · {s.user_id} · {s.symbol} · {s.agent_response_latency_ms}ms · HHI{" "}
                {s.portfolio_risk_concentration}
              </li>
            ))}
          </ul>
        </article>
      </main>

      <footer>
        Not investment advice. Simulated / delayed demo tape plus synthetic SEBI-style corpus.
        Cash-equity recommendations only unless the profile explicitly allows F&O, which this
        system still refuses to size.
      </footer>
    </div>
  );
}
