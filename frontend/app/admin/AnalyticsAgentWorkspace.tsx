"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, money } from "../lib/api";

type AnalyticsMetrics = {
  orders: number;
  paid_orders: number;
  delivered_orders: number;
  cancelled_orders: number;
  units_sold: number;
  revenue_mad: number;
  average_order_value_mad: number;
};

type AnalyticsReport = {
  period_days: number;
  generated_at: string;
  current: AnalyticsMetrics;
  previous: AnalyticsMetrics;
  comparison: {
    orders_change_pct: number;
    revenue_change_pct: number;
    units_change_pct: number;
  };
  daily_sales: Array<{
    date: string;
    orders: number;
    revenue_mad: number;
  }>;
  top_products: Array<{
    product_id: number;
    name: string;
    brand: string | null;
    quantity: number;
    revenue_mad: number;
  }>;
  unsold_products: Array<{
    product_id: number;
    name: string;
    brand: string | null;
    stock: number;
    price: number | null;
  }>;
  summary: string;
  insights: string[];
  alerts: string[];
  model: string;
  read_only: boolean;
};

function ChangeBadge({ value }: { value: number }) {
  const state = value > 0 ? "positive" : value < 0 ? "negative" : "neutral";
  return (
    <span className={`analytics-change ${state}`}>
      {value > 0 ? "+" : ""}
      {value.toLocaleString("fr-MA", { maximumFractionDigits: 1 })} %
    </span>
  );
}

function ComparisonRow({
  label,
  current,
  previous,
  format,
}: {
  label: string;
  current: number;
  previous: number;
  format: (value: number) => string;
}) {
  const maximum = Math.max(current, previous, 1);
  const currentWidth = current > 0 ? Math.max(4, (current / maximum) * 100) : 0;
  const previousWidth = previous > 0 ? Math.max(4, (previous / maximum) * 100) : 0;
  return (
    <div className="analytics-compare-row">
      <strong>{label}</strong>
      <div>
        <span>Actuelle</span>
        <div className="analytics-track">
          <i className="current" style={{ width: `${currentWidth}%` }} />
        </div>
        <b>{format(current)}</b>
      </div>
      <div>
        <span>Précédente</span>
        <div className="analytics-track">
          <i className="previous" style={{ width: `${previousWidth}%` }} />
        </div>
        <b>{format(previous)}</b>
      </div>
    </div>
  );
}

function StatusRow({
  label,
  value,
  total,
  state,
}: {
  label: string;
  value: number;
  total: number;
  state: "success" | "pending" | "danger";
}) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="analytics-status-row">
      <div>
        <span>{label}</span>
        <b>{value} · {percentage} %</b>
      </div>
      <div className="analytics-track">
        <i className={state} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

export function AnalyticsAgentWorkspace() {
  const [periodDays, setPeriodDays] = useState(30);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState("");

  const requestReport = async (useAI: boolean) => {
    if (useAI) setAiLoading(true);
    else setLoading(true);
    setError("");
    try {
      const data = await api<AnalyticsReport>(
        `/api/admin/ai/analytics/report?period_days=${periodDays}&use_ai=${useAI}`,
        {},
        true,
      );
      setReport(data);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
      setAiLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    api<AnalyticsReport>(
      "/api/admin/ai/analytics/report?period_days=30&use_ai=false",
      {},
      true,
    )
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

  const maxDailyRevenue = useMemo(
    () => Math.max(...(report?.daily_sales.map((item) => item.revenue_mad) || [0]), 1),
    [report],
  );
  const maxProductQuantity = useMemo(
    () => Math.max(...(report?.top_products.map((item) => item.quantity) || [0]), 1),
    [report],
  );

  return (
    <section className="analytics-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Analyse des ventes</p>
          <h2>Analytics Agent</h2>
        </div>
        <div className="analytics-actions">
          <label>
            <span>Période</span>
            <select
              value={periodDays}
              onChange={(event) => setPeriodDays(Number(event.target.value))}
            >
              <option value={7}>7 jours</option>
              <option value={30}>30 jours</option>
              <option value={90}>90 jours</option>
            </select>
          </label>
          <button
            type="button"
            className="button button-secondary button-small"
            onClick={() => requestReport(false)}
            disabled={loading || aiLoading}
          >
            {loading ? "Actualisation..." : "Actualiser"}
          </button>
          <button
            type="button"
            className="button button-ai button-small"
            onClick={() => requestReport(true)}
            disabled={loading || aiLoading}
          >
            {aiLoading ? "Analyse IA en cours..." : "Générer le résumé IA"}
          </button>
        </div>
      </div>

      <p className="section-intro">
        Consultez les tendances réelles des commandes. L&apos;agent analyse les données en lecture seule et ne modifie ni les produits ni les commandes.
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {loading && !report ? (
        <div className="page-loading">Chargement des données de vente...</div>
      ) : report ? (
        <>
          <div className="analytics-summary panel">
            <div>
              <span className="brand-mark">N</span>
              <div>
                <p className="kicker">Résumé Analytics Agent</p>
                <h3>{report.summary}</h3>
              </div>
            </div>
            <small>
              Source : {report.model} · Mis à jour le{" "}
              {new Date(report.generated_at).toLocaleString("fr-MA")}
            </small>
          </div>

          <div className="analytics-metrics">
            <article className="panel">
              <small>Revenu confirmé</small>
              <strong>{money(report.current.revenue_mad)}</strong>
              <ChangeBadge value={report.comparison.revenue_change_pct} />
            </article>
            <article className="panel">
              <small>Commandes</small>
              <strong>{report.current.orders}</strong>
              <ChangeBadge value={report.comparison.orders_change_pct} />
            </article>
            <article className="panel">
              <small>Unités vendues</small>
              <strong>{report.current.units_sold}</strong>
              <ChangeBadge value={report.comparison.units_change_pct} />
            </article>
            <article className="panel">
              <small>Panier moyen</small>
              <strong>{money(report.current.average_order_value_mad)}</strong>
              <span className="analytics-context">
                {report.current.paid_orders} paiement(s) confirmé(s)
              </span>
            </article>
          </div>

          <div className="analytics-visual-grid">
            <section className="panel analytics-comparison-panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Comparaison simple</p>
                  <h3>Période actuelle / précédente</h3>
                </div>
              </div>
              <div className="analytics-legend">
                <span><i className="current" />Période actuelle</span>
                <span><i className="previous" />Période précédente</span>
              </div>
              <ComparisonRow
                label="Revenu"
                current={report.current.revenue_mad}
                previous={report.previous.revenue_mad}
                format={(value) => money(value)}
              />
              <ComparisonRow
                label="Commandes"
                current={report.current.orders}
                previous={report.previous.orders}
                format={(value) => value.toLocaleString("fr-MA")}
              />
              <ComparisonRow
                label="Unités vendues"
                current={report.current.units_sold}
                previous={report.previous.units_sold}
                format={(value) => value.toLocaleString("fr-MA")}
              />
            </section>

            <section className="panel analytics-status-panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">État des commandes</p>
                  <h3>Répartition des commandes</h3>
                </div>
              </div>
              <div className="analytics-status-chart">
                <StatusRow
                  label="Livrées"
                  value={report.current.delivered_orders}
                  total={report.current.orders}
                  state="success"
                />
                <StatusRow
                  label="En cours"
                  value={Math.max(
                    report.current.orders
                      - report.current.delivered_orders
                      - report.current.cancelled_orders,
                    0,
                  )}
                  total={report.current.orders}
                  state="pending"
                />
                <StatusRow
                  label="Annulées"
                  value={report.current.cancelled_orders}
                  total={report.current.orders}
                  state="danger"
                />
              </div>
              <div className="analytics-status-total">
                <strong>{report.current.orders}</strong>
                <span>commandes au total</span>
              </div>
            </section>
          </div>

          <section className="panel analytics-chart-panel">
            <div className="analytics-section-head">
              <div>
                <p className="kicker">Évolution quotidienne</p>
                <h3>Revenu confirmé</h3>
              </div>
              <span>{report.period_days} jours</span>
            </div>
            <div className="analytics-chart" role="img" aria-label="Évolution quotidienne du revenu confirmé">
              {report.daily_sales.map((point) => (
                <div
                  className="analytics-bar-column"
                  key={point.date}
                  title={`${new Date(`${point.date}T12:00:00`).toLocaleDateString("fr-MA")} : ${money(point.revenue_mad)} · ${point.orders} commande(s)`}
                >
                  <span
                    className="analytics-bar"
                    style={{
                      height: `${Math.max(4, (point.revenue_mad / maxDailyRevenue) * 100)}%`,
                    }}
                  />
                  <small>
                    {new Date(`${point.date}T12:00:00`).toLocaleDateString("fr-MA", {
                      day: "2-digit",
                      month: "2-digit",
                    })}
                  </small>
                </div>
              ))}
            </div>
          </section>

          <div className="analytics-tables">
            <section className="panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Performance</p>
                  <h3>Produits les plus vendus</h3>
                </div>
              </div>
              {report.top_products.length ? (
                <div className="analytics-top-products-chart">
                  {report.top_products.map((product, index) => (
                    <Link href={`/products/${product.product_id}`} key={product.product_id}>
                      <div>
                        <span><b>{index + 1}</b><strong>{product.name}</strong></span>
                        <span>{product.quantity} unité(s) · {money(product.revenue_mad)}</span>
                      </div>
                      <div className="analytics-track">
                        <i
                          className="current"
                          style={{ width: `${Math.max(5, (product.quantity / maxProductQuantity) * 100)}%` }}
                        />
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="muted">Aucune vente enregistrée sur cette période.</p>
              )}
            </section>

            <section className="panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Opportunités</p>
                  <h3>Produits sans vente</h3>
                </div>
              </div>
              {report.unsold_products.length ? (
                <div className="analytics-product-list">
                  {report.unsold_products.map((product) => (
                    <Link href={`/admin?product=${product.product_id}`} key={product.product_id}>
                      <b>#{product.product_id}</b>
                      <span>
                        <strong>{product.name}</strong>
                        <small>{product.brand || "Sans marque"}</small>
                      </span>
                      <span>
                        <strong>{product.stock} en stock</strong>
                        <small>{product.price === null ? "Prix indisponible" : money(product.price)}</small>
                      </span>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="muted">Tous les produits affichés ont enregistré une vente.</p>
              )}
            </section>
          </div>

          <div className="analytics-insight-grid">
            <section className="panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Observations</p>
                  <h3>Points clés</h3>
                </div>
              </div>
              <ul className="analytics-list">
                {report.insights.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
            <section className="panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Surveillance</p>
                  <h3>Alertes</h3>
                </div>
              </div>
              {report.alerts.length ? (
                <ul className="analytics-list analytics-alerts">
                  {report.alerts.map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : (
                <p className="muted">Aucune alerte importante sur cette période.</p>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
