"use client";

import { FormEvent, useEffect, useState } from "react";
import { Protected } from "../components/Protected";
import { useAuth } from "../components/AuthProvider";
import { api } from "../lib/api";
import type { User } from "../types";

export default function AccountPage() {
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState("");
  const [passwords, setPasswords] = useState({
    current_password: "",
    new_password: "",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => setName(user?.full_name || ""), [user]);

  const updateProfile = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api<User>(
        "/api/auth/me",
        { method: "PATCH", body: JSON.stringify({ full_name: name }) },
        true,
      );
      await refreshUser();
      setMessage("Profil mis a jour");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const changePassword = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api<void>(
        "/api/auth/change-password",
        { method: "POST", body: JSON.stringify(passwords) },
        true,
      );
      setPasswords({ current_password: "", new_password: "" });
      setMessage("Mot de passe modifie. Reconnectez-vous a la prochaine visite.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const verifyEmail = async () => {
    setError("");
    try {
      const result = await api<{ dev_token: string | null }>(
        "/api/auth/request-email-verification",
        { method: "POST" },
        true,
      );
      if (result.dev_token) {
        await api("/api/auth/verify-email", {
          method: "POST",
          body: JSON.stringify({ token: result.dev_token }),
        });
        await refreshUser();
        setMessage("Email verifie en mode local");
      } else {
        setMessage("Email deja verifie");
      }
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Protected>
      <section className="shell page-section">
        <div className="page-title"><div><p className="kicker">Votre espace</p><h1>Mon compte</h1></div></div>
        {message && <div className="alert alert-success">{message}</div>}
        {error && <div className="alert alert-error">{error}</div>}
        <div className="account-grid">
          <form className="panel stack-form" onSubmit={updateProfile}>
            <h2>Informations personnelles</h2>
            <label>Nom complet<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
            <label>Email<input value={user?.email || ""} disabled /></label>
            <div className="email-state">
              <span className={`account-state ${user?.is_email_verified ? "active" : ""}`}>
                {user?.is_email_verified ? "Email verifie" : "Email non verifie"}
              </span>
              {!user?.is_email_verified && <button type="button" className="link-button" onClick={verifyEmail}>Verifier maintenant</button>}
            </div>
            <label>Role<input value={user?.role || ""} disabled /></label>
            <button className="button">Enregistrer</button>
          </form>
          <form className="panel stack-form" onSubmit={changePassword}>
            <h2>Securite</h2>
            <label>Mot de passe actuel<input type="password" value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} required minLength={8} /></label>
            <label>Nouveau mot de passe<input type="password" value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} required minLength={8} /></label>
            <button className="button button-dark">Changer le mot de passe</button>
          </form>
        </div>
      </section>
    </Protected>
  );
}
