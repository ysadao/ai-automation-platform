import { type CSSProperties, type FormEvent, useEffect, useMemo, useState } from "react";
import {
  api,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
  type Session,
  type Task,
  type Template,
  type Usage,
  type User,
  type Workflow,
} from "./api";

type Tab = "tasks" | "templates" | "workflows" | "sessions";
type Gate = "boot" | "login" | "register" | "forgot" | "reset" | "verify" | "desk";

function hashGate(): Gate {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const page = raw.split("?")[0];
  if (page === "register") return "register";
  if (page === "forgot") return "forgot";
  if (page === "reset") return "reset";
  if (page === "verify") return "verify";
  if (page === "login") return "login";
  return getAccessToken() ? "desk" : "login";
}

function hashParam(name: string): string {
  const q = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(q).get(name) ?? "";
}

export default function App() {
  const [gate, setGate] = useState<Gate>("boot");
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setGate(hashGate() === "desk" && !getAccessToken() ? "login" : hashGate());
    window.addEventListener("hashchange", onHash);
    const token = getAccessToken();
    if (!token) {
      setGate(hashGate() === "desk" ? "login" : hashGate());
      return () => window.removeEventListener("hashchange", onHash);
    }
    api
      .me()
      .then((me) => {
        setUser(me);
        setGate(hashGate() === "login" ? "desk" : hashGate() === "boot" ? "desk" : hashGate());
      })
      .catch(() => {
        clearTokens();
        setGate(hashGate() === "desk" ? "login" : hashGate());
      });
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function go(next: Gate) {
    window.location.hash = next === "desk" ? "" : `/${next}`;
    setGate(next);
  }

  async function onAuthed(access: string, refresh: string, nextUser: User, extra?: string) {
    setTokens(access, refresh);
    setUser(nextUser);
    setNotice(extra ?? null);
    go("desk");
  }

  async function onLogout() {
    try {
      await api.logout(getRefreshToken() ?? undefined);
    } catch {
      /* still clear local session */
    }
    clearTokens();
    setUser(null);
    go("login");
  }

  if (gate === "boot") {
    return (
      <div style={styles.authShell}>
        <p style={styles.muted}>Opening the desk…</p>
      </div>
    );
  }

  if (gate !== "desk") {
    return (
      <AuthScreens
        gate={gate}
        notice={notice}
        onNotice={setNotice}
        onGo={go}
        onAuthed={onAuthed}
      />
    );
  }

  return <Desk user={user} notice={notice} onLogout={onLogout} onNotice={setNotice} />;
}

function AuthScreens({
  gate,
  notice,
  onNotice,
  onGo,
  onAuthed,
}: {
  gate: Exclude<Gate, "boot" | "desk">;
  notice: string | null;
  onNotice: (v: string | null) => void;
  onGo: (g: Gate) => void;
  onAuthed: (access: string, refresh: string, user: User, extra?: string) => Promise<void>;
}) {
  const [email, setEmail] = useState(gate === "login" ? "demo@inkworks.app" : "");
  const [password, setPassword] = useState(gate === "login" ? "InkDemo123!" : "");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [token, setToken] = useState(hashParam("token"));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(notice);

  useEffect(() => {
    setToken(hashParam("token"));
    setError(null);
  }, [gate]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (gate === "login") {
        const res = await api.login({ email, password });
        await onAuthed(res.access_token, res.refresh_token, res.user);
      } else if (gate === "register") {
        const res = await api.register({ email, password, first_name: firstName, last_name: lastName });
        const extra = res.verification_token
          ? `Verify with token (demo): ${res.verification_token}`
          : "Registered. Verify your email before dispatching tasks.";
        await onAuthed(res.access_token, res.refresh_token, res.user, extra);
      } else if (gate === "forgot") {
        const res = await api.forgotPassword(email);
        setInfo(
          res.reset_token
            ? `Reset token (demo): ${res.reset_token}`
            : "If that inbox exists, a reset token was issued.",
        );
      } else if (gate === "reset") {
        await api.resetPassword(token, password);
        setInfo("Password updated. Sign in with the new password.");
        onGo("login");
      } else if (gate === "verify") {
        await api.verifyEmail(token);
        setInfo("Email verified. You can dispatch tasks.");
        onGo("desk");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      onNotice(null);
    }
  }

  const title =
    gate === "login"
      ? "Sign in"
      : gate === "register"
        ? "Create operator"
        : gate === "forgot"
          ? "Forgot password"
          : gate === "reset"
            ? "Reset password"
            : "Verify email";

  return (
    <div style={styles.authShell}>
      <div style={styles.authCard}>
        <div style={styles.mark}>INKWORKS</div>
        <div style={styles.sub}>automation desk</div>
        <h1 style={styles.h1}>{title}</h1>
        {info ? <div style={styles.info}>{info}</div> : null}
        {error ? <div style={styles.error}>{error}</div> : null}
        <form onSubmit={submit}>
          {gate === "register" ? (
            <div style={styles.row}>
              <label style={styles.label}>
                First name
                <input value={firstName} onChange={(e) => setFirstName(e.target.value)} style={styles.input} />
              </label>
              <label style={styles.label}>
                Last name
                <input value={lastName} onChange={(e) => setLastName(e.target.value)} style={styles.input} />
              </label>
            </div>
          ) : null}
          {gate === "login" || gate === "register" || gate === "forgot" ? (
            <label style={styles.label}>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={styles.input}
                required
              />
            </label>
          ) : null}
          {gate === "login" || gate === "register" || gate === "reset" ? (
            <label style={styles.label}>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={styles.input}
                required
                minLength={8}
              />
            </label>
          ) : null}
          {gate === "reset" || gate === "verify" ? (
            <label style={styles.label}>
              Token
              <input value={token} onChange={(e) => setToken(e.target.value)} style={styles.input} required />
            </label>
          ) : null}
          <button type="submit" disabled={busy} style={{ ...styles.primary, marginTop: 16 }}>
            {busy ? "Working…" : title}
          </button>
        </form>
        <nav style={styles.authNav}>
          {gate !== "login" ? (
            <button type="button" style={styles.link} onClick={() => onGo("login")}>
              Sign in
            </button>
          ) : null}
          {gate !== "register" ? (
            <button type="button" style={styles.link} onClick={() => onGo("register")}>
              Register
            </button>
          ) : null}
          {gate !== "forgot" ? (
            <button type="button" style={styles.link} onClick={() => onGo("forgot")}>
              Forgot password
            </button>
          ) : null}
          {gate !== "reset" ? (
            <button type="button" style={styles.link} onClick={() => onGo("reset")}>
              Reset
            </button>
          ) : null}
          {gate !== "verify" ? (
            <button type="button" style={styles.link} onClick={() => onGo("verify")}>
              Verify email
            </button>
          ) : null}
        </nav>
        {gate === "login" ? (
          <p style={styles.muted}>Demo: demo@inkworks.app / InkDemo123!</p>
        ) : null}
      </div>
    </div>
  );
}

function Desk({
  user,
  notice,
  onLogout,
  onNotice,
}: {
  user: User | null;
  notice: string | null;
  onLogout: () => void;
  onNotice: (v: string | null) => void;
}) {
  const [tab, setTab] = useState<Tab>("tasks");
  const [prompt, setPrompt] = useState("Draft a night-shift brief for the amber warehouse.");
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tplName, setTplName] = useState("");
  const [tplBody, setTplBody] = useState("Summarize:\n{{prompt}}");
  const [editingId, setEditingId] = useState<string | null>(null);

  const selected = useMemo(
    () => tasks.find((t) => t.id === selectedId) ?? tasks[0] ?? null,
    [tasks, selectedId],
  );

  async function refresh() {
    const [taskRes, tplRes, wfRes, usageRes, sessionRes] = await Promise.all([
      api.tasks(),
      api.templates(),
      api.workflows(),
      api.usage(),
      api.sessions(),
    ]);
    setTasks(taskRes.items);
    setTemplates(tplRes.items);
    setWorkflows(wfRes.items);
    setUsage(usageRes);
    setSessions(sessionRes.items);
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
    const timer = setInterval(() => {
      refresh().catch(() => undefined);
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (workflowId === null && workflows[0]) setWorkflowId(workflows[0].id);
  }, [workflows, workflowId]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    onNotice(null);
    try {
      const created = await api.createTask({
        prompt,
        workflow_id: workflowId || undefined,
        template_id: templateId || undefined,
      });
      setSelectedId(created.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveTemplate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (editingId) {
        await api.updateTemplate(editingId, { name: tplName, body: tplBody });
      } else {
        await api.createTemplate({ name: tplName, body: tplBody });
      }
      setTplName("");
      setTplBody("Summarize:\n{{prompt}}");
      setEditingId(null);
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
        <div style={styles.who}>
          <div>{user?.email ?? "operator"}</div>
          <div className="mono" style={styles.muted}>
            {user?.email_verified_at ? "verified" : "unverified — verify to dispatch"}
          </div>
        </div>
        <nav style={styles.nav}>
          {(["tasks", "templates", "workflows", "sessions"] as Tab[]).map((id) => (
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
            {usage?.total_tokens ?? 0}
          </div>
          <div style={styles.muted}>tokens simulated</div>
          <div className="mono" style={{ marginTop: 8 }}>
            {usage?.task_count ?? 0} tasks
          </div>
        </div>
        <button type="button" style={styles.ghost} onClick={onLogout}>
          Sign out
        </button>
      </aside>

      <main style={styles.main}>
        {notice ? <div style={styles.info}>{notice}</div> : null}
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
                      value={workflowId ?? ""}
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
                  <div className="mono" style={styles.mutedDark}>
                    {selected.id} · {selected.tokens_used ?? 0} tok
                  </div>
                  <p style={styles.promptCopy}>{selected.prompt}</p>
                  <pre style={styles.result}>{selected.result || selected.error || "waiting for worker…"}</pre>
                </>
              ) : (
                <p style={styles.mutedDark}>No tasks yet. Dispatch one from the left.</p>
              )}
            </section>
          </div>
        ) : null}

        {tab === "templates" ? (
          <section style={styles.card}>
            <h1 style={styles.h1}>Prompt templates</h1>
            <form onSubmit={saveTemplate} style={{ marginBottom: 24 }}>
              <label style={styles.label}>
                Name
                <input value={tplName} onChange={(e) => setTplName(e.target.value)} style={styles.input} required />
              </label>
              <label style={styles.label}>
                Body
                <textarea
                  value={tplBody}
                  onChange={(e) => setTplBody(e.target.value)}
                  rows={5}
                  style={styles.textarea}
                  required
                />
              </label>
              <button type="submit" disabled={busy} style={{ ...styles.primary, marginTop: 12 }}>
                {editingId ? "Update template" : "Create template"}
              </button>
              {editingId ? (
                <button
                  type="button"
                  style={styles.ghostInline}
                  onClick={() => {
                    setEditingId(null);
                    setTplName("");
                    setTplBody("Summarize:\n{{prompt}}");
                  }}
                >
                  Cancel
                </button>
              ) : null}
            </form>
            <ul style={styles.cardGrid}>
              {templates.map((tpl) => (
                <li key={tpl.id} style={styles.tile}>
                  <div style={styles.tileName}>{tpl.name}</div>
                  <pre style={styles.tileBody}>{tpl.body}</pre>
                  <div style={styles.row}>
                    <button
                      type="button"
                      style={styles.link}
                      onClick={() => {
                        setEditingId(tpl.id);
                        setTplName(tpl.name);
                        setTplBody(tpl.body);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      style={styles.linkDanger}
                      onClick={async () => {
                        await api.deleteTemplate(tpl.id);
                        await refresh();
                      }}
                    >
                      Delete
                    </button>
                  </div>
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

        {tab === "sessions" ? (
          <section style={styles.card}>
            <h1 style={styles.h1}>Sessions</h1>
            <button
              type="button"
              style={styles.ghost}
              onClick={async () => {
                await api.logoutAll();
                onLogout();
              }}
            >
              Logout all devices
            </button>
            <ul style={styles.list}>
              {sessions.map((session) => (
                <li key={session.id} style={styles.item}>
                  <div>
                    <div className="mono" style={styles.status}>
                      {session.current ? "current" : session.revoked_at ? "revoked" : "active"}
                    </div>
                    <div style={styles.muted}>{session.user_agent || "unknown agent"}</div>
                    <div className="mono" style={styles.muted}>
                      {session.ip || "—"} · {session.created_at}
                    </div>
                  </div>
                  {!session.revoked_at && !session.current ? (
                    <button
                      type="button"
                      style={styles.linkDanger}
                      onClick={async () => {
                        await api.revokeSession(session.id);
                        await refresh();
                      }}
                    >
                      Revoke
                    </button>
                  ) : null}
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
  authShell: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    padding: 24,
  },
  authCard: {
    width: "min(480px, 100%)",
    background: "var(--panel)",
    border: "1px solid var(--line)",
    padding: 28,
  },
  authNav: { display: "flex", flexWrap: "wrap", gap: 12, marginTop: 18 },
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
  who: { marginTop: 16, fontSize: 13 },
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
  mutedDark: { color: "#5c4a32", fontSize: 13 },
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
  label: { display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--muted)", flex: 1, marginTop: 10 },
  textarea: {
    background: "var(--ink-2)",
    color: "var(--cream)",
    border: "1px solid var(--line)",
    padding: 12,
    resize: "vertical",
  },
  input: {
    background: "var(--ink-2)",
    color: "var(--cream)",
    border: "1px solid var(--line)",
    padding: "8px 10px",
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
  ghost: {
    marginTop: 24,
    background: "transparent",
    color: "var(--muted)",
    border: "1px solid var(--line)",
    padding: "8px 12px",
  },
  ghostInline: {
    marginLeft: 12,
    background: "transparent",
    color: "var(--muted)",
    border: "1px solid var(--line)",
    padding: "10px 12px",
  },
  link: {
    background: "transparent",
    color: "var(--amber-2)",
    border: 0,
    padding: 0,
    fontSize: 13,
  },
  linkDanger: {
    background: "transparent",
    color: "var(--danger)",
    border: 0,
    padding: 0,
    fontSize: 13,
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
    justifyContent: "space-between",
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
  info: {
    background: "#1e2a18",
    color: "#cfe3bf",
    padding: 10,
    marginBottom: 16,
    border: "1px solid var(--ok)",
    wordBreak: "break-all",
  },
  cardGrid: { listStyle: "none", padding: 0, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 },
  tile: { background: "var(--ink-2)", border: "1px solid var(--line)", padding: 16 },
  tileName: { color: "var(--amber-2)", marginBottom: 8, letterSpacing: "0.06em" },
  tileBody: { whiteSpace: "pre-wrap", color: "var(--cream)", fontSize: 13 },
  steps: { margin: "8px 0 0 18px", color: "var(--amber)" },
};
