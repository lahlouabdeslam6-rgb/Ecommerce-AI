import Link from "next/link";
import { money } from "../lib/api";
import type {
  OrchestratorAgentResult,
  OrchestratorResponse,
} from "../orchestrator-types";

const agentLabels: Record<string, string> = {
  product: "Product Agent",
  recommendation: "Recommendation Agent",
  content: "Content Agent",
  marketing: "Marketing Agent",
  safety: "Safety Agent",
  analytics: "Analytics Agent",
};

const intentLabels: Record<string, string> = {
  product: "Produit",
  recommendation: "Recommandation",
  content: "Contenu",
  marketing: "Marketing",
  compound: "Produit et recommandation",
  analytics: "Analyse des ventes",
};

const statusLabels: Record<string, string> = {
  success: "Terminé",
  error: "Erreur",
  skipped: "Ignoré",
  blocked: "Bloqué",
  warning: "À vérifier",
};

const fieldLabels: Record<string, string> = {
  title: "Titre",
  subtitle: "Sous-titre",
  description: "Description",
  short_description: "Description courte",
  long_description: "Description longue",
  body: "Contenu",
  cta_label: "Bouton d'action",
  highlights: "Points forts",
  ingredients_summary: "Résumé des ingrédients",
  usage: "Conseils d'utilisation",
  seo_title: "Titre SEO",
  meta_description: "Méta description",
  keywords: "Mots-clés",
  category: "Catégorie",
  brand: "Marque",
  flavor: "Parfum",
  objective: "Objectif",
  channel: "Canal",
  audience: "Audience",
  subject: "Sujet",
  current: "Période actuelle",
  previous: "Période précédente",
  comparison: "Comparaison",
  daily_sales: "Ventes quotidiennes",
  top_products: "Produits les plus vendus",
  unsold_products: "Produits sans vente",
  summary: "Résumé",
  insights: "Observations",
  alerts: "Alertes",
  model: "Modèle",
  read_only: "Lecture seule",
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Oui" : "Non";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function RecommendationResult({ result }: { result: OrchestratorAgentResult }) {
  const items = Array.isArray(result.data.items) ? result.data.items : [];
  if (!items.length) {
    return <p className="ai-result-note">Aucune recommandation trouvée. Essayez une autre demande.</p>;
  }
  return (
    <div className="ai-recommendation-list">
      {items.slice(0, 6).map((entry, index) => {
        const item = entry as Record<string, unknown>;
        const product = (item.product || {}) as Record<string, unknown>;
        const productId = Number(product.product_id);
        const content = (
          <>
            <div>
              <strong>{String(product.name || "Produit NUTRIFIT")}</strong>
              <small>{String(product.brand || product.category || "")}</small>
            </div>
            <div className="ai-recommendation-meta">
              {typeof product.price === "number" && <b>{money(product.price)}</b>}
              {Number.isInteger(productId) && productId > 0 && <span className="text-link">Voir le produit</span>}
            </div>
          </>
        );
        return Number.isInteger(productId) && productId > 0 ? (
          <Link
            key={`${productId}-${index}`}
            href={`/products/${productId}`}
            className="ai-recommendation-item ai-recommendation-link"
            aria-label={`Voir le produit ${String(product.name || "NUTRIFIT")}`}
          >
            {content}
          </Link>
        ) : (
          <article key={`item-${index}`} className="ai-recommendation-item">
            {content}
          </article>
        );
      })}
    </div>
  );
}

function SafetyResult({ result }: { result: OrchestratorAgentResult }) {
  const safetyStatus = String(result.data.status || result.status || "warning");
  const reasons = Array.isArray(result.data.reasons) ? result.data.reasons : [];
  return (
    <div className={`ai-safety-result safety-${safetyStatus}`}>
      <div>
        <span className="ai-status-dot" />
        <strong>{safetyStatus === "safe" ? "Validé" : safetyStatus === "blocked" ? "Bloqué" : "À vérifier"}</strong>
      </div>
      {reasons.length > 0 && (
        <ul>{reasons.slice(0, 3).map((reason, index) => <li key={index}>{String(reason)}</li>)}</ul>
      )}
    </div>
  );
}

function GeneratedResult({ result }: { result: OrchestratorAgentResult }) {
  const hidden = new Set(["items", "disclaimer"]);
  const entries = Object.entries(result.data).filter(([key]) => !hidden.has(key));
  return (
    <div className="ai-generated-result">
      {entries.slice(0, 12).map(([key, value]) => (
        <div key={key}>
          <small>{fieldLabels[key] || key.replaceAll("_", " ")}</small>
          {Array.isArray(value) ? (
            <div className="ai-chip-list">
              {value.map((item, index) => <span key={index}>{displayValue(item)}</span>)}
            </div>
          ) : typeof value === "object" && value !== null ? (
            <pre>{displayValue(value)}</pre>
          ) : (
            <p>{displayValue(value)}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export function OrchestratorResult({
  response,
  compact = false,
}: {
  response: OrchestratorResponse;
  compact?: boolean;
}) {
  return (
    <div className={`orchestrator-result ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="orchestrator-route">
          <span>Intention détectée : {intentLabels[response.detected_intent] || response.detected_intent}</span>
          <div className="ai-chip-list">
            {response.selected_agents.map((agent) => (
              <b key={agent}>{agentLabels[agent] || agent}</b>
            ))}
          </div>
        </div>
      )}
      {response.requires_confirmation && (
        <div className="alert alert-warning">
          {response.proposed_action || "Ce résultat nécessite une validation humaine."}
        </div>
      )}
      <div className="orchestrator-agent-results">
        {response.results.map((result, index) => (
          <section className="orchestrator-agent-card" key={`${result.agent}-${index}`}>
            <header>
              <strong>{agentLabels[result.agent] || result.agent}</strong>
              <span className={`agent-state state-${result.status}`}>{statusLabels[result.status] || result.status}</span>
            </header>
            {result.agent === "recommendation" ? (
              <RecommendationResult result={result} />
            ) : result.agent === "safety" ? (
              <SafetyResult result={result} />
            ) : (
              <GeneratedResult result={result} />
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
