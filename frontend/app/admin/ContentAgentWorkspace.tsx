"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";

type ContentItem = {
  id: number;
  content_type: string;
  topic: string;
  objective: string | null;
  audience: string;
  tone: string;
  language: string;
  product_id: number | null;
  title: string;
  subtitle: string | null;
  body: string;
  cta_label: string | null;
  hashtags: string[];
  status: "draft" | "published" | "archived";
  model: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

type ContentList = {
  items: ContentItem[];
  total: number;
};

type GenerateForm = {
  content_type: string;
  topic: string;
  objective: string;
  audience: string;
  tone: string;
  product_id: string;
};

const contentTypes = [
  ["homepage_hero", "Hero homepage"],
  ["promotion", "Campagne promotionnelle"],
  ["category", "Page categorie"],
  ["faq", "FAQ / conseils"],
  ["social_post", "Post reseaux sociaux"],
];

const emptyGenerate: GenerateForm = {
  content_type: "promotion",
  topic: "",
  objective: "",
  audience: "sportifs au Maroc",
  tone: "premium",
  product_id: "",
};

export function ContentAgentWorkspace() {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [selected, setSelected] = useState<ContentItem | null>(null);
  const [form, setForm] = useState<GenerateForm>(emptyGenerate);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const result = await api<ContentList>(
        "/api/admin/ai/content?page_size=100",
        {},
        true,
      );
      setItems(result.items);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const generate = async (event: FormEvent) => {
    event.preventDefault();
    setGenerating(true); setError(""); setMessage("");
    try {
      const item = await api<ContentItem>(
        "/api/admin/ai/content/generate",
        {
          method: "POST",
          body: JSON.stringify({
            content_type: form.content_type,
            topic: form.topic,
            objective: form.objective || null,
            audience: form.audience,
            tone: form.tone,
            language: "fr",
            product_id: form.product_id ? Number(form.product_id) : null,
          }),
        },
        true,
      );
      setSelected(item);
      setMessage("Brouillon genere. Relis et modifie avant publication.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  const saveDraft = async (): Promise<ContentItem | null> => {
    if (!selected) return null;
    const updated = await api<ContentItem>(
      `/api/admin/ai/content/${selected.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          title: selected.title,
          subtitle: selected.subtitle,
          body: selected.body,
          cta_label: selected.cta_label,
          hashtags: selected.hashtags,
        }),
      },
      true,
    );
    setSelected(updated);
    return updated;
  };

  const save = async () => {
    setSaving(true); setError(""); setMessage("");
    try {
      await saveDraft();
      setMessage("Brouillon enregistre.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    if (!selected) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const draft = await saveDraft();
      if (!draft) return;
      const published = await api<ContentItem>(
        `/api/admin/ai/content/${draft.id}/publish`,
        { method: "POST" },
        true,
      );
      setSelected(published);
      setMessage(
        published.content_type === "homepage_hero" ||
          published.content_type === "promotion"
          ? "Contenu publie sur la homepage."
          : "Contenu publie dans la bibliotheque.",
      );
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const archive = async () => {
    if (!selected) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const archived = await api<ContentItem>(
        `/api/admin/ai/content/${selected.id}/archive`,
        { method: "POST" },
        true,
      );
      setSelected(archived);
      setMessage("Contenu archive.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const updateSelected = (
    changes: Partial<ContentItem>,
  ) => setSelected((current) => current ? { ...current, ...changes } : current);

  return (
    <div className="content-agent-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Creation assistee</p>
          <h2>Content Agent</h2>
        </div>
        <span className="muted">{items.length} contenu(s)</span>
      </div>
      <div className="ai-safety-note">
        <strong>Validation admin + Safety AI</strong>
        <span>L&apos;AI cree uniquement un brouillon. Safety Agent le controle avant le bouton Publier.</span>
      </div>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="content-agent-layout">
        <div className="content-agent-left">
          <form className="panel content-generator" onSubmit={generate}>
            <div className="content-panel-title">
              <div><span>NOUVEAU BROUILLON</span><strong>Brief de generation</strong></div>
              <small>Ollama · local</small>
            </div>
            <div className="form-grid">
              <label>Type de contenu<select value={form.content_type} onChange={(event) => setForm({ ...form, content_type: event.target.value })}>{contentTypes.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
              <label>Ton<select value={form.tone} onChange={(event) => setForm({ ...form, tone: event.target.value })}><option value="premium">Premium</option><option value="energetic">Energique</option><option value="educational">Educatif</option><option value="direct">Direct</option></select></label>
              <label className="full-field">Sujet<input value={form.topic} onChange={(event) => setForm({ ...form, topic: event.target.value })} placeholder="Ex: campagne creatine pour la rentree" required minLength={3} /></label>
              <label className="full-field">Objectif<textarea value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} placeholder="Ex: presenter les benefices du catalogue sans promesse medicale" /></label>
              <label>Audience<input value={form.audience} onChange={(event) => setForm({ ...form, audience: event.target.value })} required /></label>
              <label>Produit lie (optionnel)<input type="number" min="1" value={form.product_id} onChange={(event) => setForm({ ...form, product_id: event.target.value })} placeholder="ID produit" /></label>
            </div>
            <button className="button button-ai" disabled={generating}>{generating ? "Content Agent travaille..." : "Generer le brouillon"}</button>
          </form>

          <section className="content-library">
            <div className="content-panel-title">
              <div><span>BIBLIOTHEQUE</span><strong>Historique des contenus</strong></div>
            </div>
            {!items.length ? <div className="empty-state compact"><h3>Aucun contenu</h3><p>Genere ton premier brouillon.</p></div> : <div className="content-card-list">{items.map((item) => <button type="button" className={`content-card ${selected?.id === item.id ? "selected" : ""}`} key={item.id} onClick={() => setSelected(item)}><span className={`content-status status-${item.status}`}>{item.status}</span><strong>{item.title}</strong><small>{contentTypes.find(([value]) => value === item.content_type)?.[1] || item.content_type} · {new Date(item.updated_at).toLocaleDateString("fr-MA")}</small></button>)}</div>}
          </section>
        </div>

        <section className="panel content-review">
          {!selected ? <div className="empty-state"><h3>Selectionne un contenu</h3><p>Le brouillon apparaitra ici pour review.</p></div> : <>
            <div className="content-panel-title">
              <div><span>REVIEW ADMIN</span><strong>Brouillon #{selected.id}</strong></div>
              <span className={`content-status status-${selected.status}`}>{selected.status}</span>
            </div>
            <div className="content-meta"><span>{selected.model}</span><span>{selected.tone}</span><span>{selected.language}</span></div>
            <label>Titre<input value={selected.title} maxLength={180} onChange={(event) => updateSelected({ title: event.target.value })} /></label>
            <label>Sous-titre<input value={selected.subtitle || ""} maxLength={300} onChange={(event) => updateSelected({ subtitle: event.target.value || null })} /></label>
            <label>Contenu<textarea className="content-body-input" value={selected.body} maxLength={4000} onChange={(event) => updateSelected({ body: event.target.value })} /></label>
            <label>Texte du bouton<input value={selected.cta_label || ""} maxLength={80} onChange={(event) => updateSelected({ cta_label: event.target.value || null })} /></label>
            <label>Hashtags<input value={selected.hashtags.join(" ")} onChange={(event) => updateSelected({ hashtags: splitHashtags(event.target.value) })} /></label>
            <div className="content-review-actions">
              <button type="button" className="button button-secondary" onClick={save} disabled={saving}>Enregistrer brouillon</button>
              <button type="button" className="button" onClick={publish} disabled={saving}>{saving ? "Traitement..." : "Publier"}</button>
              <button type="button" className="button button-danger" onClick={archive} disabled={saving}>Archiver</button>
            </div>
          </>}
        </section>
      </div>
    </div>
  );
}

function splitHashtags(value: string): string[] {
  return value
    .replaceAll(",", " ")
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `#${item.replace(/^#+/, "")}`)
    .slice(0, 12);
}
