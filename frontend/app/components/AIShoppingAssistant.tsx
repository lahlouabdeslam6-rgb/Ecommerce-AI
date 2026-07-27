"use client";

import { FormEvent, useState } from "react";
import { api } from "../lib/api";
import type { OrchestratorResponse } from "../orchestrator-types";
import { useAuth } from "./AuthProvider";
import { OrchestratorResult } from "./OrchestratorResult";

type ConversationItem = {
  id: number;
  message: string;
  response?: OrchestratorResponse;
  error?: string;
};

const quickPrompts = [
  "Bghit creatine ta7t 300 MAD w kayna f stock",
  "9ter7 lia produit l recuperation",
  "Bghit proteine 3la 7sab budget dyali",
];

export function AIShoppingAssistant() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [conversation, setConversation] = useState<ConversationItem[]>([]);

  if (user?.role !== "customer") return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const value = message.trim();
    if (!value || sending) return;
    const id = Date.now();
    setConversation((items) => [...items, { id, message: value }]);
    setMessage("");
    setSending(true);
    try {
      const response = await api<OrchestratorResponse>(
        "/api/orchestrator/execute",
        { method: "POST", body: JSON.stringify({ message: value }) },
        true,
      );
      setConversation((items) => items.map((item) => item.id === id ? { ...item, response } : item));
    } catch (error) {
      setConversation((items) => items.map((item) => item.id === id ? { ...item, error: (error as Error).message } : item));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className={`ai-assistant ${open ? "open" : ""}`}>
      {open && (
        <section className="ai-assistant-panel" aria-label="Assistant NUTRIFIT">
          <header>
            <div>
              <span className="brand-mark assistant-mark">N</span>
              <div><strong>Assistant NUTRIFIT</strong><small>Product + Recommendation + Safety</small></div>
            </div>
            <button type="button" className="ai-close" onClick={() => setOpen(false)} aria-label="Fermer">×</button>
          </header>
          <div className="ai-assistant-thread">
            {conversation.length === 0 && (
              <div className="ai-welcome">
                <p>Sewelni 3la produit, objectif wela budget dyalk.</p>
                <div>{quickPrompts.map((prompt) => (
                  <button key={prompt} type="button" onClick={() => setMessage(prompt)}>{prompt}</button>
                ))}</div>
              </div>
            )}
            {conversation.map((item) => (
              <div className="ai-conversation-item" key={item.id}>
                <p className="ai-user-message">{item.message}</p>
                {item.response && <OrchestratorResult response={item.response} compact />}
                {item.error && <div className="alert alert-error">{item.error}</div>}
                {!item.response && !item.error && <div className="ai-thinking">Les agents kaykhdmo...</div>}
              </div>
            ))}
          </div>
          <form onSubmit={submit} className="ai-assistant-form">
            <label htmlFor="assistant-message">Talab dyalk</label>
            <div>
              <input
                id="assistant-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                maxLength={500}
                placeholder="Ex: bghit creatine ta7t 300 MAD"
              />
              <button className="button button-small" disabled={sending || !message.trim()}>
                {sending ? "..." : "Sift"}
              </button>
            </div>
          </form>
        </section>
      )}
      <button
        type="button"
        className="ai-assistant-trigger"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label="Ouvrir Assistant NUTRIFIT"
      >
        <span>N</span>
        <b>AI Assistant</b>
      </button>
    </div>
  );
}
