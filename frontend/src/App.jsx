import { useEffect, useState } from "react";
import { supabase, supabaseConfigError } from "./lib/supabaseClient";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001/api";
const CATEGORIES = ["Food", "Petrol", "Snacks", "Recharge", "Groceries", "Clothes", "Transport", "Bills", "Health", "Entertainment", "Other"];
const emptyForm = { amount: "", category: "Food", date: "", note: "" };

async function apiFetch(path, token, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) {
    await supabase?.auth.signOut();
    throw new Error("Your session expired. Please sign in again.");
  }
  if (!response.ok) {
    const details = await response.json().catch(() => ({}));
    throw new Error(details.detail || "The backend request failed.");
  }
  return response;
}

function AuthScreen() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submitAuth(event) {
    event.preventDefault(); setError(""); setMessage("");
    if (!email.trim() || password.length < 6) { setError("Enter a valid email and a password with at least 6 characters."); return; }
    if (!supabase) { setError(supabaseConfigError); return; }
    setBusy(true);
    try {
      if (mode === "login") {
        const { error: signInError } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (signInError) throw signInError;
        window.location.hash = "#/dashboard";
      } else {
        const { data, error: signUpError } = await supabase.auth.signUp({ email: email.trim(), password });
        if (signUpError) throw signUpError;
        if (data.session) { window.location.hash = "#/dashboard"; }
        else { setMessage("Registration succeeded. Check your email to confirm your account, then sign in."); setMode("login"); }
      }
    } catch (authError) { setError(authError.message || "Authentication failed."); }
    finally { setBusy(false); }
  }

  return <main className="auth-shell"><section className="card auth-card">
    <p className="eyebrow">SMART EXPENSE TRACKER</p><h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
    <p className="subtitle">{mode === "login" ? "Sign in to manage your private expenses." : "Register with Supabase Auth to get started."}</p>
    {supabaseConfigError && <p className="message error">{supabaseConfigError}</p>}
    <form onSubmit={submitAuth}>
      <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
      <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} minLength="6" required /></label>
      {error && <p className="message error">{error}</p>}{message && <p className="message success">{message}</p>}
      <button type="submit" disabled={busy || Boolean(supabaseConfigError)}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Register"}</button>
    </form>
    <button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setMessage(""); }}>
      {mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}
    </button>
  </section></main>;
}

function Dashboard({ session }) {
  const [expenses, setExpenses] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function loadExpenses() {
    setLoading(true); setError("");
    try { const response = await apiFetch("/expenses", session.access_token); setExpenses(await response.json()); }
    catch (requestError) { setError(requestError.message); } finally { setLoading(false); }
  }
  useEffect(() => { loadExpenses(); }, [session.access_token]);
  function handleChange(event) { setForm({ ...form, [event.target.name]: event.target.value }); }
  async function handleSubmit(event) {
    event.preventDefault(); const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) { setError("Amount must be a number greater than zero."); return; }
    setSaving(true); setError("");
    try {
      const response = await apiFetch(editingId ? `/expenses/${editingId}` : "/expenses", session.access_token, { method: editingId ? "PUT" : "POST", body: JSON.stringify({ ...form, amount }) });
      if (!response.ok) throw new Error("Could not save expense.");
      setForm(emptyForm); setEditingId(null); await loadExpenses();
    } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }
  function startEditing(expense) { setEditingId(expense.id); setForm({ amount: String(expense.amount), category: expense.category, date: expense.date, note: expense.note || "" }); setError(""); window.scrollTo({ top: 0, behavior: "smooth" }); }
  async function deleteExpense(id) {
    if (!window.confirm("Delete this expense?")) return;
    try { await apiFetch(`/expenses/${id}`, session.access_token, { method: "DELETE" }); await loadExpenses(); }
    catch (requestError) { setError(requestError.message); }
  }
  async function logout() { await supabase.auth.signOut(); window.location.hash = "#/login"; }

  return <main className="page-shell">
    <header className="dashboard-header"><div><p className="eyebrow">PRIVATE EXPENSES</p><h1>Smart Expense Tracker</h1><p className="subtitle">Signed in as {session.user.email}</p></div><button className="secondary" onClick={logout}>Log out</button></header>
    <section className="card form-card"><h2>{editingId ? "Edit expense" : "Add an expense"}</h2><form onSubmit={handleSubmit}>
      <label>Amount<input name="amount" type="number" min="0.01" step="0.01" value={form.amount} onChange={handleChange} placeholder="0.00" required /></label>
      <label>Category<select name="category" value={form.category} onChange={handleChange}>{CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select></label>
      <label>Date<input name="date" type="date" value={form.date} onChange={handleChange} required /></label>
      <label className="wide">Note (optional)<input name="note" value={form.note} onChange={handleChange} placeholder="What was this for?" /></label>
      <div className="form-actions"><button type="submit" disabled={saving}>{saving ? "Saving…" : editingId ? "Update expense" : "Add expense"}</button>{editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm(emptyForm); setError(""); }}>Cancel</button>}</div>
    </form></section>
    {error && <p className="message error">{error}</p>}
    <section className="card"><div className="section-heading"><h2>Your expenses</h2><span>{expenses.length} total</span></div>
      {loading ? <p className="message">Loading expenses…</p> : expenses.length === 0 ? <p className="message">No expenses yet. Add your first one above.</p> : <div className="table-wrap"><table><thead><tr><th>Date</th><th>Category</th><th>Note</th><th>Amount</th><th>Actions</th></tr></thead><tbody>{expenses.map((expense) => <tr key={expense.id}><td>{expense.date}</td><td><span className="tag">{expense.category}</span></td><td>{expense.note || "—"}</td><td className="amount">{Number(expense.amount).toFixed(2)}</td><td className="actions"><button className="link-button" onClick={() => startEditing(expense)}>Edit</button><button className="link-button danger" onClick={() => deleteExpense(expense.id)}>Delete</button></td></tr>)}</tbody></table></div>}
    </section>
  </main>;
}

function App() {
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  useEffect(() => {
    if (!supabase) { setAuthLoading(false); return undefined; }
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => { if (mounted) { setSession(data.session); window.location.hash = data.session ? "#/dashboard" : "#/login"; setAuthLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, currentSession) => { if (mounted) { setSession(currentSession); window.location.hash = currentSession ? "#/dashboard" : "#/login"; } });
    return () => { mounted = false; listener.subscription.unsubscribe(); };
  }, []);
  if (authLoading) return <main className="auth-shell"><p className="message">Checking your session…</p></main>;
  return session ? <Dashboard session={session} /> : <AuthScreen />;
}

export default App;

