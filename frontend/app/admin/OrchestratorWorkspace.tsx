"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type {
  OrchestratorHistory,
  OrchestratorHistoryItem,
  OrchestratorResponse,
} from "../orchestrator-types";
import { OrchestratorResult } from "../components/OrchestratorResult";

const examples = [
  {
    message: "Je cherche de la créatine à moins de 300 MAD en stock",
    taskType: "",
  },
  {
    message: "Rédige une description premium pour une whey protein",
    taskType: "content",
  },
  {
    message: "Prépare une campagne de promotion pour la créatine sur Instagram et par email",
    taskType: "marketing",
  },
  {
    message: "Analyse les ventes des 30 derniers jours",
    taskType: "analytics",
  },
  {
    message: "Prévois les risques de rupture de stock",
    taskType: "stock_forecast",
  },
  {
    message: "Comment fonctionne le paiement à la livraison ?",
    taskType: "support",
  },
  {
    message: "Analyse les risques et retards de livraison",
    taskType: "delivery",
  },
  {
    message: "Lance un audit SEO du catalogue",
    taskType: "seo",
  },
];

export function OrchestratorWorkspace() {
  const [message, setMessage] = useState("");
  const [taskType, setTaskType] = useState("");
  const [productId, setProductId] = useState("");
  const [response, setResponse] = useState<OrchestratorResponse | null>(null);
  const [history, setHistory] = useState<OrchestratorHistory | null>(null);
  const [selected, setSelected] = useState<OrchestratorHistoryItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const resultRef = useRef<HTMLDivElement>(null);

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
    if (taskType === "product" && (!productId || Number(productId) < 1)) {
      setError("Le Product Agent nécessite un identifiant de produit valide.");
      return;
    }
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
            ...(taskType === "product"
              ? { context: { product_id: Number(productId) } }
              : {}),
          }),
        },
        true,
      );
      setResponse(result);
      await loadHistory();
      window.requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
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
        <span className="ai-readonly-badge">Prévisualisation + Safety</span>
      </div>
      <p className="section-intro">
        Testez une demande, identifiez les agents mobilisés et consultez le contrôle Safety. Aucune publication ni modification automatique ne sera effectuée.
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="orchestrator-admin-grid">
        <div className="panel orchestrator-console">
          <form onSubmit={submit}>
            <label>
              <span>Demande</span>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                maxLength={500}
                placeholder="Ex. : rédiger un contenu premium sur la créatine"
                required
              />
            </label>
            <label>
              <span>Sélection des agents</span>
              <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
                <option value="">Automatique (recommandé)</option>
                <option value="product">Product Agent</option>
                <option value="recommendation">Recommendation Agent</option>
                <option value="support">Support Agent</option>
                <option value="content">Content Agent</option>
                <option value="marketing">Marketing Agent</option>
                <option value="analytics">Analytics Agent</option>
                <option value="stock_forecast">Stock Forecast Agent</option>
                <option value="delivery">Delivery Agent</option>
                <option value="seo">SEO Agent</option>
              </select>
              <small>
                Laissez le mode automatique pour que l&apos;Orchestrator sélectionne l&apos;agent adapté.
              </small>
            </label>
            {taskType === "product" && (
              <label>
                <span>ID produit</span>
                <input
                  type="number"
                  min="1"
                  value={productId}
                  onChange={(event) => setProductId(event.target.value)}
                  placeholder="Ex: 23445"
                  required
                />
              </label>
            )}
            <div className="orchestrator-examples">
              {examples.map((example) => (
                <button
                  type="button"
                  key={example.message}
                  onClick={() => {
                    setMessage(example.message);
                    setTaskType(example.taskType);
                    setError("");
                  }}
                >
                  {example.message}
                </button>
              ))}
            </div>
            <button className="button" disabled={loading || !message.trim()}>
              {loading ? "Analyse en cours..." : "Lancer l'analyse"}
            </button>
          </form>
        </div>

        <div className="orchestrator-live" ref={resultRef} aria-live="polite">
          {response ? (
            <>
              <div className="alert alert-success">
                Résultat prêt : {response.selected_agents.join(" + ")}
              </div>
              <OrchestratorResult response={response} />
            </>
          ) : (
            <div className="panel ai-empty-state">
              <span>N</span>
              <h3>Résultat des agents</h3>
              <p>Saisissez une demande pour consulter le routage, les résultats et la décision Safety.</p>
            </div>
          )}
        </div>
      </div>

      <div className="page-title orchestrator-history-title">
        <div><p className="kicker">Traçabilité</p><h2>Historique Orchestrator</h2></div>
        <span>{history?.total || 0} requête(s)</span>
      </div>
      <div className="orchestrator-history-layout">
        <div className="data-table orchestrator-history-table">
          <div className="table-row table-head"><span>Date</span><span>Acteur</span><span>Demande</span><span>Agents</span><span /></div>
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
