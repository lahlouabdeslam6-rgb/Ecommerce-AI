"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "../components/AuthProvider";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const user = await login(email, password);
      router.push(
        user.role === "admin"
          ? "/admin"
          : user.role === "support"
            ? "/support"
            : searchParams.get("returnTo") || "/",
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return <section className="auth-page"><div className="auth-card"><p className="kicker">Heureux de vous revoir</p><h1>Connexion</h1><p className="muted">Retrouvez votre panier et suivez vos commandes.</p>{searchParams.get("expired") && <div className="alert alert-error">Votre session a expire. Connectez-vous a nouveau.</div>}{error && <div className="alert alert-error">{error}</div>}<form onSubmit={submit} className="stack-form"><label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label><label>Mot de passe<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label><div className="form-helper"><Link href="/forgot-password">Mot de passe oublie ?</Link></div><button className="button" disabled={submitting}>{submitting ? "Connexion..." : "Se connecter"}</button></form><p className="auth-switch">Pas encore de compte ? <Link href="/register">Creer un compte</Link></p></div><div className="auth-aside"><span>Commande simple</span><h2>Choisissez. Confirmez. Payez a la livraison.</h2></div></section>;
}
