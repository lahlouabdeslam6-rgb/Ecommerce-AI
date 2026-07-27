"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";

type AuditItem = {
  product_id: number;
  name: string;
  brand: string | null;
  score: number;
  issues: string[];
  slug: string | null;
};
type AuditReport = {
  generated_at: string;
  summary: {
    products: number;
    excellent: number;
    needs_work: number;
    critical: number;
    average_score: number;
  };
  items: AuditItem[];
};
type SEOProposal = {
  product_id: number;
  slug: string;
  seo_title: string;
  seo_description: string;
  seo_keywords: string[];
  image_alt: string;
  seo_faq: { question: string; answer: string }[];
  model: string;
};

export function SEOAgentWorkspace() {
  const [audit, setAudit] = useState<AuditReport | null>(null);
  const [filter, setFilter] = useState<"all" | "critical" | "work" | "excellent">("all");
  const [selected, setSelected] = useState<AuditItem | null>(null);
  const [proposal, setProposal] = useState<SEOProposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadAudit = async () => {
    setLoading(true);
    setError("");
    try {
      setAudit(await api<AuditReport>("/api/admin/ai/seo/audit", {}, true));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    api<AuditReport>("/api/admin/ai/seo/audit", {}, true)
      .then((data) => {
        if (active) setAudit(data);
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

  const visible = useMemo(
    () => (audit?.items || []).filter((item) => (
      filter === "all"
      || (filter === "critical" && item.score < 50)
      || (filter === "work" && item.score >= 50 && item.score < 80)
      || (filter === "excellent" && item.score >= 80)
    )),
    [audit, filter],
  );

  const preview = async (item: AuditItem) => {
    setSelected(item);
    setProposal(null);
    setWorking(true);
    setError("");
    try {
      setProposal(
        await api<SEOProposal>(
          `/api/admin/ai/seo/products/${item.product_id}/preview`,
          { method: "POST" },
          true,
        ),
      );
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setWorking(false);
    }
  };

  const apply = async () => {
    if (!proposal) return;
    setWorking(true);
    setError("");
    try {
      const result = await api<{ score_before: number; score_after: number }>(
        `/api/admin/ai/seo/products/${proposal.product_id}/apply`,
        { method: "POST", body: JSON.stringify(proposal) },
        true,
      );
      setMessage(
        `SEO appliqué au produit #${proposal.product_id}: ${result.score_before} → ${result.score_after}/100.`,
      );
      setProposal(null);
      setSelected(null);
      await loadAudit();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="seo-agent-workspace">
      <div className="page-title">
        <div><p className="kicker">Référencement catalogue</p><h2>SEO Agent</h2></div>
        <button className="button button-secondary button-small" onClick={loadAudit} disabled={loading}>
          {loading ? "Audit en cours..." : "Relancer l'audit"}
        </button>
      </div>
      <p className="section-intro">
        L&apos;agent contrôle chaque fiche, prépare les métadonnées, le slug, le texte alternatif et la FAQ. Aucune proposition n&apos;est appliquée sans validation.
      </p>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {audit && (
        <>
          <div className="seo-metrics">
            <article className="panel"><small>Score moyen</small><strong>{audit.summary.average_score}/100</strong></article>
            <article className="panel seo-good"><small>Excellent</small><strong>{audit.summary.excellent}</strong></article>
            <article className="panel seo-work"><small>À améliorer</small><strong>{audit.summary.needs_work}</strong></article>
            <article className="panel seo-critical"><small>Critique</small><strong>{audit.summary.critical}</strong></article>
          </div>
          <div className="seo-layout">
            <section className="panel seo-audit-panel">
              <div className="analytics-section-head">
                <div><p className="kicker">Catalogue</p><h3>Audit des fiches</h3></div>
                <select value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
                  <option value="all">Tous les scores</option>
                  <option value="critical">Critique</option>
                  <option value="work">À améliorer</option>
                  <option value="excellent">Excellent</option>
                </select>
              </div>
              <div className="seo-product-list">
                {visible.slice(0, 100).map((item) => (
                  <button key={item.product_id} type="button" onClick={() => preview(item)}>
                    <span className={`seo-score ${item.score >= 80 ? "good" : item.score >= 50 ? "work" : "critical"}`}>{item.score}</span>
                    <span><strong>{item.name}</strong><small>{item.brand || "Sans marque"} · {item.issues[0] || "Fiche optimisée"}</small></span>
                    <b>{working && selected?.product_id === item.product_id ? "..." : "Optimiser"}</b>
                  </button>
                ))}
              </div>
            </section>
            <aside className="panel seo-proposal-panel">
              {!proposal ? (
                <div className="empty-state">
                  <span className="brand-mark">N</span>
                  <h3>Proposition SEO</h3>
                  <p>Sélectionnez un produit pour préparer son optimisation.</p>
                </div>
              ) : (
                <>
                  <div><p className="kicker">Produit #{proposal.product_id}</p><h3>Proposition à valider</h3></div>
                  <label>Slug<input value={proposal.slug} onChange={(event) => setProposal({ ...proposal, slug: event.target.value })} /></label>
                  <label>Titre SEO<input maxLength={70} value={proposal.seo_title} onChange={(event) => setProposal({ ...proposal, seo_title: event.target.value })} /></label>
                  <label>Méta description<textarea maxLength={180} value={proposal.seo_description} onChange={(event) => setProposal({ ...proposal, seo_description: event.target.value })} /></label>
                  <label>Mots-clés<input value={proposal.seo_keywords.join(", ")} onChange={(event) => setProposal({ ...proposal, seo_keywords: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} /></label>
                  <label>Texte alternatif image<input maxLength={180} value={proposal.image_alt} onChange={(event) => setProposal({ ...proposal, image_alt: event.target.value })} /></label>
                  <div className="seo-faq-preview">
                    <small>FAQ proposée</small>
                    {proposal.seo_faq.map((item) => <div key={item.question}><strong>{item.question}</strong><p>{item.answer}</p></div>)}
                  </div>
                  <div className="ai-review-actions">
                    <button className="button" onClick={apply} disabled={working}>{working ? "Application..." : "Valider et appliquer"}</button>
                    <button className="text-link" onClick={() => setProposal(null)} disabled={working}>Ignorer</button>
                  </div>
                </>
              )}
            </aside>
          </div>
        </>
      )}
    </section>
  );
}

