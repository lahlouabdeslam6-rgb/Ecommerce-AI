"use client";

import { useEffect, useMemo, useState } from "react";
import { api, money } from "../lib/api";

type VerificationStatus =
  | "to_confirm"
  | "priority_review"
  | "possible_duplicate"
  | "ready_to_prepare";

type VerificationItem = {
  order_id: number;
  customer_name: string;
  customer_email: string;
  phone: string;
  address: string;
  city: string;
  total: number;
  currency: string;
  payment_method: string;
  created_at: string;
  verification_status: VerificationStatus;
  priority_score: number;
  signals: string[];
  recommended_action: string;
};

type VerificationReport = {
  summary: {
    orders_to_review: number;
    to_confirm: number;
    priority_review: number;
    possible_duplicate: number;
    ready_to_prepare: number;
  };
  items: VerificationItem[];
  analysis: string;
  read_only: boolean;
  automatic_rejection: boolean;
};

const labels: Record<VerificationStatus, string> = {
  to_confirm: "À confirmer",
  priority_review: "Vérification prioritaire",
  possible_duplicate: "Doublon possible",
  ready_to_prepare: "Prête à préparer",
};

export function OrderVerificationWorkspace() {
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [filter, setFilter] = useState<VerificationStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setReport(
        await api<VerificationReport>(
          "/api/ai/order-verification/report",
          {},
          true,
        ),
      );
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const items = useMemo(
    () =>
      (report?.items || []).filter(
        (item) => !filter || item.verification_status === filter,
      ),
    [report, filter],
  );

  return (
    <section className="order-verification-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Contrôle avant préparation</p>
          <h2>Order Verification Agent</h2>
        </div>
        <button
          type="button"
          className="button button-secondary button-small"
          onClick={load}
          disabled={loading}
        >
          {loading ? "Analyse..." : "Actualiser"}
        </button>
      </div>
      <p className="section-intro">
        L&apos;agent classe les commandes COD pour aider l&apos;équipe à
        organiser les appels. Il ne confirme, ne refuse et n&apos;annule jamais
        une commande automatiquement.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {!report && loading ? (
        <div className="page-loading">Vérification des commandes...</div>
      ) : (
        report && (
          <>
            <div className="delivery-summary panel">
              <span className="brand-mark">N</span>
              <div>
                <p className="kicker">Résumé de vérification</p>
                <h3>{report.analysis}</h3>
                <small>Décision finale réservée à l&apos;équipe humaine.</small>
              </div>
            </div>
            <div className="delivery-metrics">
              {(
                [
                  ["to_confirm", report.summary.to_confirm],
                  ["priority_review", report.summary.priority_review],
                  ["possible_duplicate", report.summary.possible_duplicate],
                  ["ready_to_prepare", report.summary.ready_to_prepare],
                ] as const
              ).map(([key, value]) => (
                <button
                  key={key}
                  type="button"
                  className={`panel verification-${key} ${
                    filter === key ? "active" : ""
                  }`}
                  onClick={() => setFilter(filter === key ? "" : key)}
                >
                  <small>{labels[key]}</small>
                  <strong>{value}</strong>
                  <span>commande(s)</span>
                </button>
              ))}
            </div>
            <section className="panel delivery-priority-panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Appels à organiser</p>
                  <h3>Commandes en attente</h3>
                </div>
                <span>{items.length} commande(s)</span>
              </div>
              {!items.length ? (
                <div className="empty-state">
                  Aucune commande dans ce filtre.
                </div>
              ) : (
                <div className="delivery-list">
                  {items.map((item) => (
                    <article key={item.order_id}>
                      <span
                        className={`delivery-risk verification-${item.verification_status}`}
                      >
                        {labels[item.verification_status]}
                      </span>
                      <div>
                        <strong>
                          Commande #{item.order_id} · {item.customer_name}
                        </strong>
                        <small>
                          {item.customer_email} · {item.city} ·{" "}
                          <a href={`tel:${item.phone}`}>{item.phone}</a>
                        </small>
                        <small>{item.address}</small>
                        <p>{item.recommended_action}</p>
                        <small>{item.signals.join(" · ")}</small>
                      </div>
                      <div>
                        <strong>{money(item.total, item.currency)}</strong>
                        <small>Priorité {item.priority_score}/100</small>
                        <small>{item.payment_method}</small>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )
      )}
    </section>
  );
}
