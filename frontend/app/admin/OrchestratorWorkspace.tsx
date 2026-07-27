"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";
import type {
  OrchestratorHistory,
  OrchestratorHistoryItem,
  OrchestratorResponse,
} from "../orchestrator-types";
import { OrchestratorResult } from "../components/OrchestratorResult";

const examples = [
  "Bghit creatine ta7t 300 MAD w kayna f stock",
  "Kteb description premium 3la whey protein",
  "Prepare campagne promotion creatine pour Instagram et email",
];

export function OrchestratorWorkspace() {
  const [message, setMessage] = useState("");
  const [taskType, setTaskType] = useState("");
  const [response, setResponse] = useState<OrchestratorResponse | null>(null);
  const [history, setHistory] = useState<OrchestratorHistory | null>(null);
  const [selected, setSelected] = useState<OrchestratorHistoryItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadHistory = async () => {
    try {
      setHistory(await api<OrchestratorHistory>("/api/orchestrator/history?page_size=40", {}, true));
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  useEffect(() => {
    let cancelled = false;
    api<OrchestratorHistory>(
      "/api/orchestrator/history?page_size=40",
      {},
      true,
    )
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!message.trim()) return;
    setLoading(true);
    setError("");
    setResponse(null);
    try {
      const result = await api<OrchestratorResponse>(
        "/api/orchestrator/execute",
        {
          method: "POST",
          body: JSON.stringify({
            message: message.trim(),
            ...(taskType ? { task_type: taskType } : {}),
          }),
        },
        true,
      );
      setResponse(result);
      await loadHistory();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="orchestrator-workspace">
      <div className="page-title">
        <div><p className="kicker">Cerveau central</p><h2>AI Orchestrator</h2></div>
        <span className="ai-readonly-badge">Preview + Safety</span>
      </div>
      <p className="section-intro">
        Teste un talab, chof achmen agents khdmo, w ra9eb Safety. Hna ma kayn la publication la modification automatique.
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="orchestrator-admin-grid">
        <div className="panel orchestrator-console">
          <form onSubmit={submit}>
            <label>
              <span>Talab</span>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                maxLength={500}
                placeholder="Ex: kteb contenu premium 3la creatine"
                required
              />
            </label>
            <label>
              <span>Routing</span>
              <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
                <option value="">Automatique</option>
                <option value="product">Product Agent</option>
                <option value="recommendation">Recommendation Agent</option>
                <option value="content">Content Agent</option>
                <option value="marketing">Marketing Agent</option>
              </select>
            </label>
            <div className="orchestrator-examples">
              {examples.map((example) => (
                <button type="button" key={example} onClick={() => setMessage(example)}>{example}</button>
              ))}
            </div>
            <button className="button" disabled={loading || !message.trim()}>
              {loading ? "Orchestrator kaykhdem..." : "Lancer l'analyse"}
            </button>
          </form>
        </div>

        <div className="orchestrator-live">
          {response ? (
            <OrchestratorResult response={response} />
          ) : (
            <div className="panel ai-empty-state">
              <span>N</span>
              <h3>Resultat dyal agents</h3>
              <p>Dir talab bach tchof routing, outputs w Safety decision.</p>
            </div>
          )}
        </div>
      </div>

      <div className="page-title orchestrator-history-title">
        <div><p className="kicker">Tracabilite</p><h2>Historique Orchestrator</h2></div>
        <span>{history?.total || 0} requete(s)</span>
      </div>
      <div className="orchestrator-history-layout">
        <div className="data-table orchestrator-history-table">
          <div className="table-row table-head"><span>Date</span><span>Acteur</span><span>Talab</span><span>Agents</span><span /></div>
          {history?.items.map((item) => (
            <button className="table-row" key={item.id} onClick={() => setSelected(item)}>
              <span>{new Date(item.created_at).toLocaleString("fr-MA")}</span>
              <span><strong>{item.actor_email || `Compte #${item.actor_id}`}</strong><small>{item.actor_role}</small></span>
              <span className="history-request">{item.message}</span>
              <span className="ai-chip-list">{item.selected_agents.map((agent) => <b key={agent}>{agent}</b>)}</span>
              <span className="text-link">Voir</span>
            </button>
          ))}
          {history && history.items.length === 0 && <div className="empty-state">Aucun historique pour le moment.</div>}
        </div>
        {selected && (
          <aside className="panel orchestrator-history-detail">
            <button className="ai-close" onClick={() => setSelected(null)} aria-label="Fermer">×</button>
            <small>{selected.actor_email || `Compte #${selected.actor_id}`} · {new Date(selected.created_at).toLocaleString("fr-MA")}</small>
            <h3>{selected.message}</h3>
            <OrchestratorResult response={selected} />
          </aside>
        )}
      </div>
    </section>
  );
}
