"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";

type StockRisk =
  | "out_of_stock"
  | "critical"
  | "warning"
  | "healthy"
  | "dormant";

type ForecastItem = {
  product_id: number;
  name: string;
  brand: string | null;
  stock: number;
  price: number | null;
  units_sold: number;
  previous_units_sold: number;
  sales_trend_pct: number;
  average_daily_sales: number;
  days_remaining: number | null;
  predicted_stockout_date: string | null;
  recommended_reorder_quantity: number;
  risk: StockRisk;
};

type StockForecastReport = {
  lookback_days: number;
  target_cover_days: number;
  generated_at: string;
  summary: {
    products: number;
    out_of_stock: number;
    critical: number;
    warning: number;
    healthy: number;
    dormant: number;
    recommended_reorder_units: number;
  };
  items: ForecastItem[];
  analysis: string;
  insights: string[];
  alerts: string[];
  model: string;
  read_only: boolean;
};

const riskLabels: Record<StockRisk, string> = {
  out_of_stock: "En rupture",
  critical: "Critique",
  warning: "À surveiller",
  healthy: "Stable",
  dormant: "Sans vente",
};

function RiskBar({
  label,
  value,
  total,
  risk,
}: {
  label: string;
  value: number;
  total: number;
  risk: StockRisk;
}) {
  const percentage = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="stock-risk-row">
      <div>
        <span><i className={`stock-risk-dot risk-${risk}`} />{label}</span>
        <b>{value} · {percentage} %</b>
      </div>
      <div className="stock-risk-track">
        <i className={`risk-${risk}`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

export function StockForecastWorkspace() {
  const [lookbackDays, setLookbackDays] = useState(30);
  const [riskFilter, setRiskFilter] = useState<StockRisk | "">("");
  const [report, setReport] = useState<StockForecastReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState("");

  const requestReport = async (useAI: boolean) => {
    if (useAI) setAiLoading(true);
    else setLoading(true);
    setError("");
    try {
      setReport(
        await api<StockForecastReport>(
          `/api/admin/ai/stock-forecast/report?lookback_days=${lookbackDays}&use_ai=${useAI}`,
          {},
          true,
        ),
      );
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
      setAiLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    api<StockForecastReport>(
      "/api/admin/ai/stock-forecast/report?lookback_days=30&use_ai=false",
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

  const priorityItems = useMemo(
    () => (report?.items || [])
      .filter((item) => riskFilter ? item.risk === riskFilter : item.risk !== "healthy")
      .slice(0, 40),
    [report, riskFilter],
  );
  const coverageItems = useMemo(
    () => (report?.items || [])
      .filter((item) => item.days_remaining !== null && item.average_daily_sales > 0)
      .slice(0, 10),
    [report],
  );
  const maxCoverage = Math.max(
    ...coverageItems.map((item) => Math.min(item.days_remaining || 0, 60)),
    1,
  );

  return (
    <section className="stock-forecast-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Prévision et réapprovisionnement</p>
          <h2>Stock Forecast Agent</h2>
        </div>
        <div className="analytics-actions">
          <label>
            <span>Historique</span>
            <select
              value={lookbackDays}
              onChange={(event) => setLookbackDays(Number(event.target.value))}
            >
              <option value={30}>30 jours</option>
              <option value={60}>60 jours</option>
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
            {aiLoading ? "Analyse IA en cours..." : "Générer l'analyse IA"}
          </button>
        </div>
      </div>

      <p className="section-intro">
        Cette prévision utilise les ventes réelles et le stock actuel. Elle ne modifie aucun produit et ne passe aucune commande fournisseur.
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {loading && !report ? (
        <div className="page-loading">Analyse du stock en cours...</div>
      ) : report ? (
        <>
          <div className="stock-forecast-summary panel">
            <div>
              <span className="brand-mark">N</span>
              <div>
                <p className="kicker">Résumé Stock Forecast</p>
                <h3>{report.analysis}</h3>
              </div>
            </div>
            <small>
              Source : {report.model} · Mis à jour le{" "}
              {new Date(report.generated_at).toLocaleString("fr-MA")}
            </small>
          </div>

          <div className="stock-forecast-metrics">
            <article className="panel risk-out_of_stock">
              <small>En rupture</small>
              <strong>{report.summary.out_of_stock}</strong>
              <span>produit(s)</span>
            </article>
            <article className="panel risk-critical">
              <small>Risque sous 7 jours</small>
              <strong>{report.summary.critical}</strong>
              <span>produit(s)</span>
            </article>
            <article className="panel risk-warning">
              <small>À surveiller</small>
              <strong>{report.summary.warning}</strong>
              <span>moins de 21 jours</span>
            </article>
            <article className="panel">
              <small>Réapprovisionnement suggéré</small>
              <strong>{report.summary.recommended_reorder_units}</strong>
              <span>unité(s) au total</span>
            </article>
          </div>

          <div className="stock-forecast-graphs">
            <section className="panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Vue globale</p>
                  <h3>Répartition du risque</h3>
                </div>
              </div>
              <div className="stock-risk-chart">
                <RiskBar label="En rupture" value={report.summary.out_of_stock} total={report.summary.products} risk="out_of_stock" />
                <RiskBar label="Critique" value={report.summary.critical} total={report.summary.products} risk="critical" />
                <RiskBar label="À surveiller" value={report.summary.warning} total={report.summary.products} risk="warning" />
                <RiskBar label="Stable" value={report.summary.healthy} total={report.summary.products} risk="healthy" />
                <RiskBar label="Sans vente" value={report.summary.dormant} total={report.summary.products} risk="dormant" />
              </div>
            </section>

            <section className="panel">
              <div className="analytics-section-head">
                <div>
                  <p className="kicker">Couverture estimée</p>
                  <h3>Jours de stock restants</h3>
                </div>
              </div>
              {coverageItems.length ? (
                <div className="stock-coverage-chart">
                  {coverageItems.map((item) => (
                    <Link href={`/admin?product=${item.product_id}`} key={item.product_id}>
                      <div>
                        <span>{item.name}</span>
                        <b>{item.days_remaining?.toLocaleString("fr-MA", { maximumFractionDigits: 1 })} j</b>
                      </div>
                      <div className="stock-risk-track">
                        <i
                          className={`risk-${item.risk}`}
                          style={{
                            width: `${Math.max(
                              5,
                              (Math.min(item.days_remaining || 0, 60) / maxCoverage) * 100,
                            )}%`,
                          }}
                        />
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="muted">Pas encore assez de ventes pour calculer la couverture.</p>
              )}
            </section>
          </div>

          <section className="panel stock-priority-panel">
            <div className="analytics-section-head">
              <div>
                <p className="kicker">Actions recommandées</p>
                <h3>Priorités de stock</h3>
              </div>
              <label className="stock-filter">
                <span>Afficher</span>
                <select
                  value={riskFilter}
                  onChange={(event) => setRiskFilter(event.target.value as StockRisk | "")}
                >
                  <option value="">Toutes les priorités</option>
                  <option value="out_of_stock">En rupture</option>
                  <option value="critical">Critique</option>
                  <option value="warning">À surveiller</option>
                  <option value="healthy">Stable</option>
                  <option value="dormant">Sans vente</option>
                </select>
              </label>
            </div>
            {priorityItems.length ? (
              <div className="stock-priority-list">
                {priorityItems.map((item) => (
                  <Link href={`/admin?product=${item.product_id}`} key={item.product_id}>
                    <span className={`stock-risk-badge risk-${item.risk}`}>
                      {riskLabels[item.risk]}
                    </span>
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.brand || "Sans marque"} · Stock actuel : {item.stock}</small>
                    </span>
                    <span>
                      <strong>
                        {item.days_remaining === null
                          ? "Couverture inconnue"
                          : `${item.days_remaining.toLocaleString("fr-MA", { maximumFractionDigits: 1 })} jours`}
                      </strong>
                      <small>
                        {item.predicted_stockout_date
                          ? `Rupture estimée : ${new Date(`${item.predicted_stockout_date}T12:00:00`).toLocaleDateString("fr-MA")}`
                          : `${item.units_sold} unité(s) vendue(s)`}
                      </small>
                    </span>
                    <span>
                      <strong>+{item.recommended_reorder_quantity}</strong>
                      <small>quantité suggérée</small>
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="muted">Aucun produit ne correspond à ce filtre.</p>
            )}
          </section>

          <div className="analytics-insight-grid">
            <section className="panel">
              <div className="analytics-section-head">
                <div><p className="kicker">Observations</p><h3>Points clés</h3></div>
              </div>
              <ul className="analytics-list">
                {report.insights.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
            <section className="panel">
              <div className="analytics-section-head">
                <div><p className="kicker">Surveillance</p><h3>Alertes</h3></div>
              </div>
              {report.alerts.length ? (
                <ul className="analytics-list analytics-alerts">
                  {report.alerts.map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : (
                <p className="muted">Aucune alerte urgente.</p>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
