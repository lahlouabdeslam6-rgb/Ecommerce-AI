"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";

type SafetyStatus = "safe" | "warning" | "blocked";

type SafetyReview = {
  id: number;
  source_type: string;
  source_id: string | null;
  action: string;
  status: SafetyStatus;
  risk_level: "low" | "medium" | "high";
  reasons: string[];
  recommendations: string[];
  matched_rules: string[];
  excerpt: string;
  model: string;
  actor_id: number | null;
  created_at: string;
};

type SafetyReviewList = {
  items: SafetyReview[];
  total: number;
};

const statusLabels: Record<SafetyStatus, string> = {
  safe: "Conforme",
  warning: "A verifier",
  blocked: "Bloque",
};

const sourceLabels: Record<string, string> = {
  manual: "Test manuel",
  product_suggestion: "Product Agent",
  content: "Content Agent",
  marketing_campaign: "Marketing Agent",
  support_reply: "Support Agent",
};

export function SafetyAgentWorkspace() {
  const [text, setText] = useState("");
  const [items, setItems] = useState<SafetyReview[]>([]);
  const [selected, setSelected] = useState<SafetyReview | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async (reviewStatus = statusFilter) => {
    try {
      const query = new URLSearchParams({ page_size: "100" });
      if (reviewStatus) query.set("review_status", reviewStatus);
      const result = await api<SafetyReviewList>(
        `/api/admin/ai/safety/reviews?${query.toString()}`,
        {},
        true,
      );
      setItems(result.items);
      setSelected((current) => {
        if (!current) return current;
        return result.items.find((item) => item.id === current.id) || current;
      });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    void load("");
  }, []);

  const review = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const report = await api<SafetyReview>(
        "/api/admin/ai/safety/review",
        {
          method: "POST",
          body: JSON.stringify({
            text,
            source_type: "manual",
            action: "manual.review",
          }),
        },
        true,
      );
      setSelected(report);
      await load(statusFilter);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const changeFilter = (value: string) => {
    setStatusFilter(value);
    void load(value);
  };

  return (
    <div className="content-agent-workspace safety-agent-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Controle avant validation</p>
          <h2>Safety Agent</h2>
        </div>
        <span className="muted">{items.length} rapport(s)</span>
      </div>

      <div className="ai-safety-note">
        <strong>Protection nutrition et sante</strong>
        <span>
          Chaque publication AI est controlee avant application. Une promesse
          medicale dangereuse est bloquee; un doute reste visible pour review.
        </span>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="safety-agent-layout">
        <div className="safety-agent-left">
          <form className="panel safety-review-form" onSubmit={review}>
            <div className="content-panel-title">
              <div>
                <span>TEST MANUEL</span>
                <strong>Verifier un texte</strong>
              </div>
              <small>Regles + Ollama local</small>
            </div>
            <label>
              Texte a controler
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Colle ici une description, une promotion ou une reponse client..."
                required
                minLength={3}
                maxLength={12000}
              />
            </label>
            <button className="button button-ai" disabled={loading}>
              {loading ? "Verification en cours..." : "Analyser avec Safety AI"}
            </button>
          </form>

          <section className="content-library safety-history">
            <div className="content-panel-title">
              <div>
                <span>TRACABILITE</span>
                <strong>Historique des controles</strong>
              </div>
              <select
                aria-label="Filtrer les rapports"
                value={statusFilter}
                onChange={(event) => changeFilter(event.target.value)}
              >
                <option value="">Tous</option>
                <option value="safe">Conformes</option>
                <option value="warning">A verifier</option>
                <option value="blocked">Bloques</option>
              </select>
            </div>
            {!items.length ? (
              <div className="empty-state compact">
                <h3>Aucun rapport</h3>
                <p>Les controles automatiques vont apparaitre ici.</p>
              </div>
            ) : (
              <div className="content-card-list">
                {items.map((item) => (
                  <button
                    type="button"
                    className={`content-card ${
                      selected?.id === item.id ? "selected" : ""
                    }`}
                    key={item.id}
                    onClick={() => setSelected(item)}
                  >
                    <span className={`content-status status-${item.status}`}>
                      {statusLabels[item.status]}
                    </span>
                    <strong>
                      {sourceLabels[item.source_type] || item.source_type}
                      {item.source_id ? ` #${item.source_id}` : ""}
                    </strong>
                    <small>
                      {item.action} ·{" "}
                      {new Date(item.created_at).toLocaleString("fr-MA")}
                    </small>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="panel content-review safety-result">
          {!selected ? (
            <div className="empty-state">
              <h3>Aucun controle selectionne</h3>
              <p>Analyse un texte ou ouvre un rapport de l&apos;historique.</p>
            </div>
          ) : (
            <>
              <div className="content-panel-title">
                <div>
                  <span>RAPPORT SAFETY</span>
                  <strong>Controle #{selected.id}</strong>
                </div>
                <span className={`content-status status-${selected.status}`}>
                  {statusLabels[selected.status]}
                </span>
              </div>
              <div className="content-meta">
                <span>Risque {selected.risk_level}</span>
                <span>{selected.model}</span>
                <span>
                  {sourceLabels[selected.source_type] || selected.source_type}
                </span>
              </div>
              <div className="safety-report-section">
                <strong>Extrait controle</strong>
                <p>{selected.excerpt}</p>
              </div>
              <div className="safety-report-section">
                <strong>Pourquoi</strong>
                <ul>
                  {selected.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
              <div className="safety-report-section">
                <strong>Action recommandee</strong>
                <ul>
                  {selected.recommendations.map((recommendation) => (
                    <li key={recommendation}>{recommendation}</li>
                  ))}
                </ul>
              </div>
              {!!selected.matched_rules.length && (
                <div className="safety-rules">
                  {selected.matched_rules.map((rule) => (
                    <code key={rule}>{rule}</code>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
