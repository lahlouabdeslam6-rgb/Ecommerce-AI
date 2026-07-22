"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "../lib/api";

export default function ResetPasswordPage() {
  const params = useSearchParams();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const token = params.get("token") || "";

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      setMessage("Mot de passe modifie. Vous pouvez vous connecter.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return <section className="auth-page"><div className="auth-card"><p className="kicker">Securite</p><h1>Nouveau mot de passe</h1>{message && <div className="alert alert-success">{message}</div>}{error && <div className="alert alert-error">{error}</div>}{!message && <form className="stack-form" onSubmit={submit}><label>Nouveau mot de passe<input type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label><button className="button" disabled={!token}>Modifier</button></form>}<p className="auth-switch"><Link href="/login">Retour a la connexion</Link></p></div><div className="auth-aside"><span>NUTRIFIT</span><h2>Une session sure pour chaque client.</h2></div></section>;
}
