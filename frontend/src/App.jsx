import React, { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8001/api/expenses";
const CATEGORIES = ["Food", "Petrol", "Snacks", "Recharge", "Groceries", "Clothes", "Transport", "Bills", "Health", "Entertainment", "Other"];
const emptyForm = { amount: "", category: "Food", date: "", note: "" };

function App() {
  const [expenses, setExpenses] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function loadExpenses() {
    setLoading(true); setError("");
    try { const response = await fetch(API_URL); if (!response.ok) throw new Error("Could not load expenses."); setExpenses(await response.json()); }
    catch (requestError) { setError(requestError.message); } finally { setLoading(false); }
  }
  useEffect(() => { loadExpenses(); }, []);
  function handleChange(event) { setForm({ ...form, [event.target.name]: event.target.value }); }
  async function handleSubmit(event) {
    event.preventDefault(); const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) { setError("Amount must be a number greater than zero."); return; }
    setSaving(true); setError("");
    try {
      const response = await fetch(editingId ? `${API_URL}/${editingId}` : API_URL, { method: editingId ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, amount }) });
      if (!response.ok) { const details = await response.json().catch(() => ({})); throw new Error(details.detail || "Could not save expense."); }
      setForm(emptyForm); setEditingId(null); await loadExpenses();
    } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }
  function startEditing(expense) { setEditingId(expense.id); setForm({ amount: String(expense.amount), category: expense.category, date: expense.date, note: expense.note || "" }); setError(""); window.scrollTo({ top: 0, behavior: "smooth" }); }
  async function deleteExpense(id) {
    if (!window.confirm("Delete this expense?")) return;
    try { const response = await fetch(`${API_URL}/${id}`, { method: "DELETE" }); if (!response.ok) throw new Error("Could not delete expense."); await loadExpenses(); }
    catch (requestError) { setError(requestError.message); }
  }
  function cancelEditing() { setEditingId(null); setForm(emptyForm); setError(""); }

  return <main className="page-shell">
    <header><p className="eyebrow">PHASE 2 � EXPENSE CRUD</p><h1>Smart Expense Tracker</h1><p className="subtitle">Keep your everyday spending organized.</p></header>
    <section className="card form-card"><h2>{editingId ? "Edit expense" : "Add an expense"}</h2><form onSubmit={handleSubmit}>
      <label>Amount<input name="amount" type="number" min="0.01" step="0.01" value={form.amount} onChange={handleChange} placeholder="0.00" required /></label>
      <label>Category<select name="category" value={form.category} onChange={handleChange}>{CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select></label>
      <label>Date<input name="date" type="date" value={form.date} onChange={handleChange} required /></label>
      <label className="wide">Note (optional)<input name="note" value={form.note} onChange={handleChange} placeholder="What was this for?" /></label>
      <div className="form-actions"><button type="submit" disabled={saving}>{saving ? "Saving�" : editingId ? "Update expense" : "Add expense"}</button>{editingId && <button type="button" className="secondary" onClick={cancelEditing}>Cancel</button>}</div>
    </form></section>
    {error && <p className="message error">{error}</p>}
    <section className="card"><div className="section-heading"><h2>Your expenses</h2><span>{expenses.length} total</span></div>
      {loading ? <p className="message">Loading expenses�</p> : expenses.length === 0 ? <p className="message">No expenses yet. Add your first one above.</p> : <div className="table-wrap"><table><thead><tr><th>Date</th><th>Category</th><th>Note</th><th>Amount</th><th>Actions</th></tr></thead><tbody>{expenses.map((expense) => <tr key={expense.id}><td>{expense.date}</td><td><span className="tag">{expense.category}</span></td><td>{expense.note || "�"}</td><td className="amount">{Number(expense.amount).toFixed(2)}</td><td className="actions"><button className="link-button" onClick={() => startEditing(expense)}>Edit</button><button className="link-button danger" onClick={() => deleteExpense(expense.id)}>Delete</button></td></tr>)}</tbody></table></div>}
    </section>
  </main>;
}
export default App;
