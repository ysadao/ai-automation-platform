import { type CSSProperties, type FormEvent, useEffect, useMemo, useState } from "react";
import { api, type Task, type Template, type Usage, type Workflow } from "./api";

type Tab = "tasks" | "templates" | "workflows";

export default function App() {
  const [tab, setTab] = useState<Tab>("tasks");
  const [prompt, setPrompt] = useState("Draft a night-shift brief for the amber warehouse.");
  const [workflowId, setWorkflowId] = useState("wf_draft");
  const [templateId, setTemplateId] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => tasks.find((t) => t.id === selectedId) ?? tasks[0] ?? null,
    [tasks, selectedId],
  );

  async function refresh() {
    const [taskRes, tplRes, wfRes, usageRes] = await Promise.all([
      api.tasks(),
      api.templates(),
      api.workflows(),
      api.usage(),
    ]);
    setTasks(taskRes.items);
    setTemplates(tplRes.items);
    setWorkflows(wfRes.items);
    setUsage(usageRes);
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
    const timer = setInterval(() => {
      refresh().catch(() => undefined);
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createTask({
        prompt,
        workflowId: workflowId || undefined,
        templateId: templateId || undefined,
      });
      setSelectedId(created.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.shell}>
      <aside style={styles.rail}>
        <div style={styles.mark}>INKWORKS</div>
        <div style={styles.sub}>automation desk</div>
        <p style={styles.blurb}>
          Dark-room operator console for mock LLM workflows. Amber on ink — not another purple dashboard.
        </p>
        <nav style={styles.nav}>
          {(["tasks", "templates", "workflows"] as Tab[]).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              style={{ ...styles.navBtn, ...(tab === id ? styles.navBtnOn : {}) }}
            >
              {id}
            </button>
          ))}
        </nav>
        <div style={styles.usage}>
          <div className="mono" style={styles.usageNum}>
            {usage?.totalTokens ?? 0}
          </div>
          <div style={styles.muted}>tokens simulated</div>
          <div className="mono" style={{ marginTop: 8 }}>
            {usage?.taskCount ?? 0} tasks
          </div>
        </div>
      </aside>

      <main style={styles.main}>
        {error ? <div style={styles.error}>{error}</div> : null}

        {tab === "tasks" ? (
          <div style={styles.split}>
            <section style={styles.card}>
              <h1 style={styles.h1}>Dispatch a task</h1>
              <form onSubmit={onSubmit}>
                <label style={styles.label}>
                  Prompt
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    rows={6}
                    style={styles.textarea}
                    required
                  />
                </label>
                <div style={styles.row}>
                  <label style={styles.label}>
                    Workflow
                    <select
                      value={workflowId}
                      onChange={(e) => setWorkflowId(e.target.value)}
                      style={styles.select}
                    >
                      <option value="">ai_complete only</option>
                      {workflows.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={styles.label}>
                    Template
                    <select
                      value={templateId}
                      onChange={(e) => setTemplateId(e.target.value)}
                      style={styles.select}
                    >
                      <option value="">none</option>
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button type="submit" disabled={busy} style={styles.primary}>
                  {busy ? "Queuing…" : "Run workflow"}
                </button>
              </form>
              <h2 style={styles.h2}>Queue</h2>
              <ul style={styles.list}>
                {tasks.map((task) => (
                  <li key={task.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(task.id)}
                      style={{
                        ...styles.item,
                        outline: selected?.id === task.id ? "1px solid #e0a03a" : "none",
                      }}
                    >
                      <span className="mono" style={styles.status}>
                        {task.status}
                      </span>
                      <span>{task.prompt.slice(0, 72)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
            <section style={styles.parchment}>
              <h2 style={styles.h2}>Result</h2>
              {selected ? (
                <>
                  <div className="mono" style={styles.muted}>
                    {selected.id} · {selected.tokensUsed ?? 0} tok
                  </div>
                  <p style={styles.promptCopy}>{selected.prompt}</p>
                  <pre style={styles.result}>{selected.result || selected.error || "waiting for worker…"}</pre>
                </>
              ) : (
                <p style={styles.muted}>No tasks yet. Dispatch one from the left.</p>
              )}
            </section>
          </div>
        ) : null}

        {tab === "templates" ? (
          <section style={styles.card}>
            <h1 style={styles.h1}>Prompt templates</h1>
            <ul style={styles.cardGrid}>
              {templates.map((tpl) => (
                <li key={tpl.id} style={styles.tile}>
                  <div style={styles.tileName}>{tpl.name}</div>
                  <pre style={styles.tileBody}>{tpl.body}</pre>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {tab === "workflows" ? (
          <section style={styles.card}>
            <h1 style={styles.h1}>Workflows</h1>
            <ul style={styles.cardGrid}>
              {workflows.map((wf) => (
                <li key={wf.id} style={styles.tile}>
                  <div style={styles.tileName}>{wf.name}</div>
                  <p style={styles.muted}>{wf.description}</p>
                  <ol className="mono" style={styles.steps}>
                    {wf.steps.map((step, i) => (
                      <li key={`${wf.id}-${i}`}>{step.type}</li>
                    ))}
                  </ol>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  shell: {
    display: "grid",
    gridTemplateColumns: "260px 1fr",
    minHeight: "100vh",
  },
  rail: {
    borderRight: "1px solid var(--line)",
    padding: "28px 22px",
    background: "linear-gradient(180deg, #1c1611 0%, #120f0c 100%)",
  },
  mark: {
    fontSize: 22,
    letterSpacing: "0.28em",
    color: "var(--amber)",
    fontWeight: 700,
  },
  sub: {
    marginTop: 4,
    color: "var(--muted)",
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    fontSize: 11,
  },
  blurb: {
    color: "var(--muted)",
    lineHeight: 1.5,
    fontSize: 14,
  },
  nav: { display: "flex", flexDirection: "column", gap: 8, marginTop: 28 },
  navBtn: {
    background: "transparent",
    color: "var(--cream)",
    border: "1px solid var(--line)",
    padding: "8px 12px",
    textAlign: "left",
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontSize: 12,
  },
  navBtnOn: {
    background: "#2b2218",
    borderColor: "var(--amber)",
    color: "var(--amber-2)",
  },
  usage: { marginTop: 36 },
  usageNum: { fontSize: 28, color: "var(--amber-2)" },
  muted: { color: "var(--muted)", fontSize: 13 },
  main: { padding: 28 },
  split: { display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 20 },
  card: {
    background: "var(--panel)",
    border: "1px solid var(--line)",
    padding: 22,
  },
  parchment: {
    background: "#d9c6a3",
    color: "#24180f",
    padding: 22,
    border: "1px solid #b89b6a",
  },
  h1: { margin: "0 0 16px", fontSize: 26, fontWeight: 600 },
  h2: { margin: "24px 0 12px", fontSize: 16, letterSpacing: "0.08em", textTransform: "uppercase" },
  label: { display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--muted)", flex: 1 },
  textarea: {
    background: "var(--ink-2)",
    color: "var(--cream)",
    border: "1px solid var(--line)",
    padding: 12,
    resize: "vertical",
  },
  select: {
    background: "var(--ink-2)",
    color: "var(--cream)",
    border: "1px solid var(--line)",
    padding: 8,
  },
  row: { display: "flex", gap: 12, margin: "12px 0 16px" },
  primary: {
    background: "var(--amber)",
    color: "#1a1208",
    border: 0,
    padding: "10px 18px",
    fontWeight: 700,
    letterSpacing: "0.04em",
  },
  list: { listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 },
  item: {
    width: "100%",
    textAlign: "left",
    background: "var(--ink-2)",
    color: "var(--cream)",
    border: "1px solid var(--line)",
    padding: 10,
    display: "flex",
    gap: 10,
    alignItems: "center",
  },
  status: { color: "var(--amber)", fontSize: 11, minWidth: 72, textTransform: "uppercase" },
  promptCopy: { fontStyle: "italic" },
  result: {
    whiteSpace: "pre-wrap",
    background: "#efe3cc",
    padding: 12,
    border: "1px dashed #b89b6a",
    fontFamily: "Georgia, serif",
  },
  error: {
    background: "#3a1e18",
    color: "#f0c2b4",
    padding: 10,
    marginBottom: 16,
    border: "1px solid var(--danger)",
  },
  cardGrid: { listStyle: "none", padding: 0, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 },
  tile: { background: "var(--ink-2)", border: "1px solid var(--line)", padding: 16 },
  tileName: { color: "var(--amber-2)", marginBottom: 8, letterSpacing: "0.06em" },
  tileBody: { whiteSpace: "pre-wrap", color: "var(--cream)", fontSize: 13 },
  steps: { margin: "8px 0 0 18px", color: "var(--amber)" },
};
