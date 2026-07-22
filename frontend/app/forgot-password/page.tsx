"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { api } from "../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [devToken, setDevToken] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const result = await api<{ message: string; dev_token: string | null }>(
        "/api/auth/forgot-password",
        { method: "POST", body: JSON.stringify({ email }) },
      );
      setMessage("Si le compte existe, la demande a ete creee.");
      setDevToken(result.dev_token || "");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return <section className="auth-page"><div className="auth-card"><p className="kicker">Securite</p><h1>Mot de passe oublie</h1><p className="muted">Entrez votre email pour creer un lien de reinitialisation.</p>{message && <div className="alert alert-success">{message}</div>}{error && <div className="alert alert-error">{error}</div>}<form className="stack-form" onSubmit={submit}><label>Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label><button className="button">Continuer</button></form>{devToken && <div className="dev-token"><b>Mode local</b><Link href={`/reset-password?token=${encodeURIComponent(devToken)}`}>Ouvrir la reinitialisation</Link></div>}<p className="auth-switch"><Link href="/login">Retour a la connexion</Link></p></div><div className="auth-aside"><span>Compte protege</span><h2>Recuperez votre acces en toute securite.</h2></div></section>;
}
