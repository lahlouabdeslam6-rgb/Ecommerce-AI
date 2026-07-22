"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "../components/AuthProvider";

export default function RegisterPage() {
  const router = useRouter(); const { register, login } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" }); const [error, setError] = useState(""); const [submitting, setSubmitting] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setSubmitting(true); setError(""); try { await register(form); await login(form.email, form.password); router.push("/"); } catch (err) { setError((err as Error).message); } finally { setSubmitting(false); } };
  return <section className="auth-page"><div className="auth-card"><p className="kicker">Bienvenue</p><h1>Créer un compte</h1><p className="muted">Quelques secondes pour commencer vos achats.</p>{error && <div className="alert alert-error">{error}</div>}<form onSubmit={submit} className="stack-form"><label>Nom complet<input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} /></label><label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></label><label>Mot de passe<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} /></label><button className="button" disabled={submitting}>{submitting ? "Création…" : "Créer mon compte"}</button></form><p className="auth-switch">Déjà inscrit ? <Link href="/login">Se connecter</Link></p></div><div className="auth-aside"><span>Votre espace</span><h2>Un panier personnel et un suivi clair de chaque commande.</h2></div></section>;
}
