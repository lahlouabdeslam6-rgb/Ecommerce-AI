"use client";

import { useEffect, useMemo, useState } from "react";
import { api, money } from "../lib/api";

type DeliveryRisk = "normal" | "warning" | "critical" | "failed";
type DeliveryItem = {
  order_id: number;
  customer_name: string;
  customer_email: string;
  phone: string;
  city: string;
  order_status: string;
  age_hours: number;
  estimated_delivery_date: string | null;
  risk: DeliveryRisk;
  reason: string;
  total: number;
  currency: string;
};
type DeliveryReport = {
  generated_at: string;
  summary: {
    active_orders: number;
    normal: number;
    warning: number;
    critical: number;
    failed: number;
    alerts_sent: number;
  };
  items: DeliveryItem[];
  analysis: string;
  read_only: boolean;
};

const riskLabels: Record<DeliveryRisk, string> = {
  normal: "Dans les délais",
  warning: "À surveiller",
  critical: "En retard",
  failed: "Échec de livraison",
};

export function DeliveryAgentWorkspace({
  allowNotifications = true,
}: {
  allowNotifications?: boolean;
}) {
  const [report, setReport] = useState<DeliveryReport | null>(null);
  const [risk, setRisk] = useState<DeliveryRisk | "">("");
  const [loading, setLoading] = useState(true);
  const [notifying, setNotifying] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async (notify = false) => {
    if (notify) setNotifying(true);
    else setLoading(true);
    setError("");
    setMessage("");
    try {
      const data = await api<DeliveryReport>(
        notify ? "/api/admin/ai/delivery/scan" : "/api/admin/ai/delivery/report",
        notify ? { method: "POST" } : {},
        true,
      );
      setReport(data);
      if (notify) {
        setMessage(
          data.summary.alerts_sent
            ? `${data.summary.alerts_sent} alerte(s) transmise(s) aux clients et à l'équipe.`
            : "Analyse terminée. Aucune nouvelle alerte à envoyer.",
        );
      }
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
      setNotifying(false);
    }
  };

  useEffect(() => {
    let active = true;
    api<DeliveryReport>("/api/admin/ai/delivery/report", {}, true)
      .then((data) => {
        if (active) setReport(data);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const visibleItems = useMemo(
    () => (report?.items || []).filter((item) => !risk || item.risk === risk),
    [report, risk],
  );
  const total = Math.max(report?.summary.active_orders || 0, 1);

  return (
    <section className="delivery-agent-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Suivi des expéditions</p>
          <h2>Delivery Agent</h2>
        </div>
        <div className="analytics-actions">
          <button
            type="button"
            className="button button-secondary button-small"
            onClick={() => load(false)}
            disabled={loading || notifying}
          >
            {loading ? "Actualisation..." : "Actualiser"}
          </button>
          {allowNotifications && (
            <button
              type="button"
              className="button button-ai button-small"
              onClick={() => load(true)}
              disabled={loading || notifying}
            >
              {notifying ? "Analyse en cours..." : "Analyser et notifier"}
            </button>
          )}
        </div>
      </div>
      <p className="section-intro">
        L&apos;agent détecte les commandes à surveiller. Les notifications ne sont envoyées qu&apos;après votre confirmation et ne sont pas répétées pendant 24 heures.
      </p>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {!report && loading ? (
        <div className="page-loading">Analyse des livraisons...</div>
      ) : report && (
        <>
          <div className="delivery-summary panel">
            <span className="brand-mark">N</span>
            <div>
              <p className="kicker">Résumé opérationnel</p>
              <h3>{report.analysis}</h3>
              <small>Estimation interne, sans connexion transporteur.</small>
            </div>
          </div>
          <div className="delivery-metrics">
            {([
              ["normal", "Dans les délais", report.summary.normal],
              ["warning", "À surveiller", report.summary.warning],
              ["critical", "En retard", report.summary.critical],
              ["failed", "Échecs", report.summary.failed],
            ] as const).map(([key, label, value]) => (
              <button
                key={key}
                type="button"
                className={`panel risk-${key} ${risk === key ? "active" : ""}`}
                onClick={() => setRisk(risk === key ? "" : key)}
              >
                <small>{label}</small>
                <strong>{value}</strong>
                <span>{Math.round((value / total) * 100)} % des commandes</span>
              </button>
            ))}
          </div>
          <section className="panel delivery-priority-panel">
            <div className="analytics-section-head">
              <div>
                <p className="kicker">Priorités</p>
                <h3>Commandes actives</h3>
              </div>
              <span>{visibleItems.length} commande(s)</span>
            </div>
            {!visibleItems.length ? (
              <div className="empty-state">Aucune commande dans ce filtre.</div>
            ) : (
              <div className="delivery-list">
                {visibleItems.map((item) => (
                  <article key={item.order_id}>
                    <span className={`delivery-risk risk-${item.risk}`}>
                      {riskLabels[item.risk]}
                    </span>
                    <div>
                      <strong>Commande #{item.order_id} · {item.customer_name}</strong>
                      <small>
                        {item.customer_email} · {item.city} ·{" "}
                        <a href={`tel:${item.phone}`}>{item.phone}</a>
                      </small>
                      <p>{item.reason}</p>
                    </div>
                    <div>
                      <strong>{money(item.total, item.currency)}</strong>
                      <small>{item.age_hours} h · {item.order_status}</small>
                      <small>
                        {item.estimated_delivery_date
                          ? `Estimation : ${new Date(item.estimated_delivery_date).toLocaleDateString("fr-MA")}`
                          : "Estimation indisponible"}
                      </small>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
