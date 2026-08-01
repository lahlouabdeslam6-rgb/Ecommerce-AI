"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";

type MarketingCampaign = {
  id: number;
  campaign_type: string;
  topic: string;
  objective: string;
  audience: string;
  tone: string;
  channels: string[];
  product_id: number | null;
  promotion_kind: "single_product" | "pack" | null;
  selection_mode: "automatic" | "manual" | null;
  product_ids: number[];
  selection_scores: PromotionProductScore[];
  discount_percentage: number | null;
  starts_at: string | null;
  ends_at: string | null;
  offer_details: string | null;
  campaign_title: string;
  headline: string;
  core_message: string;
  email_subject: string | null;
  email_body: string | null;
  whatsapp_message: string | null;
  social_caption: string | null;
  cta_label: string;
  hashtags: string[];
  recommended_schedule: string | null;
  status: "draft" | "approved" | "archived";
  model: string;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
};

type CampaignList = {
  items: MarketingCampaign[];
  total: number;
};

type GenerateForm = {
  campaign_type: string;
  topic: string;
  objective: string;
  audience: string;
  tone: string;
  channels: string[];
  promotion_kind: "single_product" | "pack";
  selection_mode: "automatic" | "manual";
  selection_strategy:
    | "balanced"
    | "best_sellers"
    | "overstock"
    | "slow_movers"
    | "complementary_pack";
  product_ids: number[];
  discount_percentage: string;
  starts_at: string;
  ends_at: string;
  offer_details: string;
};

type PromotionProductScore = {
  product_id: number;
  name: string;
  brand: string | null;
  category: string | null;
  price: number;
  currency: string;
  stock: number;
  score: number;
  units_sold_90?: number;
  units_sold_30?: number;
  recent_campaigns?: number;
  reasons: string[];
};

type PromotionSuggestion = {
  promotion_kind: "single_product" | "pack";
  selection_strategy: GenerateForm["selection_strategy"];
  products: PromotionProductScore[];
  regular_total: number;
  suggested_discount_percentage: number;
  suggested_price: number;
  currency: string;
  data_notes: string[];
};

type ProductOption = {
  product_id: number;
  name: string | null;
  brand: string | null;
  price: number | null;
  currency: string;
  stock: number;
};

type ProductOptionList = {
  items: ProductOption[];
};

const campaignTypes = [
  ["product_launch", "Lancement produit"],
  ["promotion", "Campagne promotionnelle"],
  ["awareness", "Notoriete de marque"],
  ["retention", "Fidelisation clients"],
];

const channelOptions = [
  ["instagram", "Instagram"],
  ["facebook", "Facebook"],
  ["email", "Email"],
  ["whatsapp", "WhatsApp"],
];

const emptyGenerate: GenerateForm = {
  campaign_type: "promotion",
  topic: "",
  objective: "",
  audience: "sportifs au Maroc",
  tone: "premium",
  channels: ["instagram"],
  promotion_kind: "single_product",
  selection_mode: "automatic",
  selection_strategy: "balanced",
  product_ids: [],
  discount_percentage: "",
  starts_at: "",
  ends_at: "",
  offer_details: "",
};

export function MarketingAgentWorkspace() {
  const [items, setItems] = useState<MarketingCampaign[]>([]);
  const [selected, setSelected] = useState<MarketingCampaign | null>(null);
  const [form, setForm] = useState<GenerateForm>(emptyGenerate);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState<PromotionSuggestion | null>(null);
  const [productSearch, setProductSearch] = useState("");
  const [productOptions, setProductOptions] = useState<ProductOption[]>([]);
  const [reviewProductSearch, setReviewProductSearch] = useState("");
  const [reviewProductOptions, setReviewProductOptions] = useState<ProductOption[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const result = await api<CampaignList>(
        "/api/admin/ai/marketing/campaigns?page_size=100",
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
    void load();
  }, []);

  useEffect(() => {
    if (form.campaign_type !== "promotion") return;
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        page: "1",
        page_size: "12",
        in_stock: "true",
        sort_by: "stock_desc",
      });
      if (productSearch.trim()) params.set("search", productSearch.trim());
      api<ProductOptionList>(`/api/products?${params.toString()}`)
        .then((result) => setProductOptions(result.items))
        .catch(() => setProductOptions([]));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [form.campaign_type, productSearch]);

  useEffect(() => {
    if (
      !selected
      || selected.campaign_type !== "promotion"
      || selected.selection_mode !== "manual"
    ) {
      setReviewProductOptions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        page: "1",
        page_size: "12",
        in_stock: "true",
        sort_by: "stock_desc",
      });
      if (reviewProductSearch.trim()) {
        params.set("search", reviewProductSearch.trim());
      }
      api<ProductOptionList>(`/api/products?${params.toString()}`)
        .then((result) => setReviewProductOptions(result.items))
        .catch(() => setReviewProductOptions([]));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [
    selected?.id,
    selected?.campaign_type,
    selected?.selection_mode,
    reviewProductSearch,
  ]);

  const togglePromotionProduct = (productId: number) => {
    setForm((current) => {
      if (current.promotion_kind === "single_product") {
        return { ...current, product_ids: [productId] };
      }
      const selected = current.product_ids.includes(productId)
        ? current.product_ids.filter((item) => item !== productId)
        : [...current.product_ids, productId];
      return { ...current, product_ids: selected };
    });
    setSuggestion(null);
  };

  const toggleReviewedProduct = (productId: number) => {
    setSelected((current) => {
      if (!current) return current;
      if (current.promotion_kind === "single_product") {
        return { ...current, product_ids: [productId] };
      }
      const productIds = current.product_ids.includes(productId)
        ? current.product_ids.filter((item) => item !== productId)
        : [...current.product_ids, productId];
      return { ...current, product_ids: productIds };
    });
  };

  const suggestPromotion = async () => {
    setSuggesting(true);
    setError("");
    try {
      const result = await api<PromotionSuggestion>(
        "/api/admin/ai/marketing/promotions/suggest",
        {
          method: "POST",
          body: JSON.stringify({
            promotion_kind: form.promotion_kind,
            selection_strategy: form.selection_strategy,
            product_ids:
              form.selection_mode === "manual" ? form.product_ids : [],
          }),
        },
        true,
      );
      setSuggestion(result);
      setForm((current) => ({
        ...current,
        product_ids: result.products.map((item) => item.product_id),
        discount_percentage:
          current.discount_percentage ||
          String(result.suggested_discount_percentage),
      }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSuggesting(false);
    }
  };

  const toggleFormChannel = (channel: string) => {
    setForm((current) => ({
      ...current,
      channels: current.channels.includes(channel)
        ? current.channels.filter((item) => item !== channel)
        : [...current.channels, channel],
    }));
  };

  const toggleSelectedChannel = (channel: string) => {
    setSelected((current) => {
      if (!current) return current;
      const channels = current.channels.includes(channel)
        ? current.channels.filter((item) => item !== channel)
        : [...current.channels, channel];
      return channels.length ? { ...current, channels } : current;
    });
  };

  const generate = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.channels.length) {
      setError("Choisis au moins un canal.");
      return;
    }
    setGenerating(true);
    setError("");
    setMessage("");
    try {
      const campaign = await api<MarketingCampaign>(
        "/api/admin/ai/marketing/campaigns/generate",
        {
          method: "POST",
          body: JSON.stringify({
            ...form,
            product_id: form.product_ids[0] || null,
            product_ids:
              form.selection_mode === "manual" ? form.product_ids : [],
            discount_percentage: form.discount_percentage
              ? Number(form.discount_percentage)
              : null,
            starts_at: form.starts_at
              ? new Date(form.starts_at).toISOString()
              : null,
            ends_at: form.ends_at
              ? new Date(form.ends_at).toISOString()
              : null,
            offer_details: form.offer_details || null,
          }),
        },
        true,
      );
      setSelected(campaign);
      setMessage(
        "Campagne generee en brouillon. Relis chaque canal avant validation.",
      );
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  const saveDraft = async (): Promise<MarketingCampaign | null> => {
    if (!selected) return null;
    const updated = await api<MarketingCampaign>(
      `/api/admin/ai/marketing/campaigns/${selected.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          audience: selected.audience,
          channels: selected.channels,
          campaign_title: selected.campaign_title,
          headline: selected.headline,
          core_message: selected.core_message,
          email_subject: selected.email_subject,
          email_body: selected.email_body,
          whatsapp_message: selected.whatsapp_message,
          social_caption: selected.social_caption,
          cta_label: selected.cta_label,
          hashtags: selected.hashtags,
          recommended_schedule: selected.recommended_schedule,
          promotion_kind: selected.promotion_kind,
          selection_mode: selected.selection_mode,
          product_ids: selected.product_ids,
          discount_percentage: selected.discount_percentage,
          starts_at: selected.starts_at,
          ends_at: selected.ends_at,
        }),
      },
      true,
    );
    setSelected(updated);
    return updated;
  };

  const save = async () => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await saveDraft();
      setMessage("Brouillon marketing enregistre.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const approve = async () => {
    if (!selected) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const draft = await saveDraft();
      if (!draft) return;
      const approved = await api<MarketingCampaign>(
        `/api/admin/ai/marketing/campaigns/${draft.id}/approve`,
        { method: "POST" },
        true,
      );
      setSelected(approved);
      setMessage(
        "Campagne validee et prete. Aucun message n'a ete envoye automatiquement.",
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
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const archived = await api<MarketingCampaign>(
        `/api/admin/ai/marketing/campaigns/${selected.id}/archive`,
        { method: "POST" },
        true,
      );
      setSelected(archived);
      setMessage("Campagne archivee.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const updateSelected = (changes: Partial<MarketingCampaign>) =>
    setSelected((current) => current ? { ...current, ...changes } : current);

  return (
    <div className="content-agent-workspace marketing-agent-workspace">
      <div className="page-title">
        <div>
          <p className="kicker">Campagnes assistees</p>
          <h2>Marketing Agent</h2>
        </div>
        <span className="muted">{items.length} campagne(s)</span>
      </div>
      <div className="ai-safety-note">
        <strong>Validation admin + Safety AI</strong>
        <span>
          L&apos;AI prepare les textes. Safety Agent les controle avant
          validation. Pour les promotions, le score utilise ventes, stock,
          tendance, taux de conversion, marge disponible et achats ensemble.
          Aucun message n&apos;est envoye automatiquement.
        </span>
      </div>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="content-agent-layout">
        <div className="content-agent-left">
          <form className="panel content-generator" onSubmit={generate}>
            <div className="content-panel-title">
              <div>
                <span>NOUVELLE CAMPAGNE</span>
                <strong>Brief marketing</strong>
              </div>
              <small>Ollama · local</small>
            </div>
            <div className="form-grid">
              <label>
                Type de campagne
                <select
                  value={form.campaign_type}
                  onChange={(event) =>
                    setForm({ ...form, campaign_type: event.target.value })
                  }
                >
                  {campaignTypes.map(([value, label]) => (
                    <option value={value} key={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>
                Ton
                <select
                  value={form.tone}
                  onChange={(event) =>
                    setForm({ ...form, tone: event.target.value })
                  }
                >
                  <option value="premium">Premium</option>
                  <option value="energetic">Energique</option>
                  <option value="educational">Educatif</option>
                  <option value="direct">Direct</option>
                </select>
              </label>
              <label className="full-field">
                Sujet {form.campaign_type === "promotion" ? "(optionnel)" : ""}
                <input
                  value={form.topic}
                  onChange={(event) =>
                    setForm({ ...form, topic: event.target.value })
                  }
                  placeholder={
                    form.campaign_type === "promotion"
                      ? "Laisser vide: Marketing Agent choisit le sujet"
                      : "Ex: campagne creatine pour la rentree"
                  }
                  required={form.campaign_type !== "promotion"}
                  minLength={form.campaign_type === "promotion" ? 0 : 3}
                />
              </label>
              <label className="full-field">
                Objectif {form.campaign_type === "promotion" ? "(optionnel)" : ""}
                <textarea
                  value={form.objective}
                  onChange={(event) =>
                    setForm({ ...form, objective: event.target.value })
                  }
                  placeholder={
                    form.campaign_type === "promotion"
                      ? "Laisser vide: Marketing Agent construit l'objectif"
                      : "Ex: faire decouvrir la selection et attirer vers le catalogue"
                  }
                  required={form.campaign_type !== "promotion"}
                  minLength={form.campaign_type === "promotion" ? 0 : 3}
                />
                {form.campaign_type === "promotion" && (
                  <small className="muted">
                    Mode autonome: laisse ces deux champs vides et Marketing
                    Agent prepare le brief complet depuis les produits choisis.
                  </small>
                )}
              </label>
              <label>
                Audience
                <input
                  value={form.audience}
                  onChange={(event) =>
                    setForm({ ...form, audience: event.target.value })
                  }
                  required
                />
              </label>
              {form.campaign_type === "promotion" && (
                <>
                  <label>
                    Format de la promotion
                    <select
                      value={form.promotion_kind}
                      onChange={(event) => {
                        const promotionKind = event.target.value as
                          | "single_product"
                          | "pack";
                        setForm({
                          ...form,
                          promotion_kind: promotionKind,
                          selection_strategy:
                            promotionKind === "single_product"
                            && form.selection_strategy === "complementary_pack"
                              ? "balanced"
                              : form.selection_strategy,
                          product_ids:
                            promotionKind === "single_product"
                              ? form.product_ids.slice(0, 1)
                              : form.product_ids,
                        });
                        setSuggestion(null);
                      }}
                    >
                      <option value="single_product">Produit unique</option>
                      <option value="pack">Pack de produits</option>
                    </select>
                  </label>
                  <label>
                    Selection des produits
                    <select
                      value={form.selection_mode}
                      onChange={(event) => {
                        setForm({
                          ...form,
                          selection_mode: event.target.value as
                            | "automatic"
                            | "manual",
                        });
                        setSuggestion(null);
                      }}
                    >
                      <option value="automatic">
                        Automatique par Marketing Agent
                      </option>
                      <option value="manual">Manuelle par admin</option>
                    </select>
                  </label>
                  {form.selection_mode === "automatic" && (
                    <label className="full-field">
                      Strategie de selection
                      <select
                        value={form.selection_strategy}
                        onChange={(event) => {
                          setForm({
                            ...form,
                            selection_strategy: event.target.value as
                              GenerateForm["selection_strategy"],
                          });
                          setSuggestion(null);
                        }}
                      >
                        <option value="balanced">
                          Equilibree: ventes + stock a relancer
                        </option>
                        <option value="best_sellers">Meilleures ventes</option>
                        <option value="overstock">
                          Stock eleve avec ventes faibles
                        </option>
                        <option value="slow_movers">Produits a relancer</option>
                        {form.promotion_kind === "pack" && (
                          <option value="complementary_pack">
                            Pack complementaire
                          </option>
                        )}
                      </select>
                      <small className="muted">
                        La strategie equilibree varie les choix et evite les
                        produits deja utilises dans les campagnes recentes.
                      </small>
                    </label>
                  )}
                  {form.selection_mode === "manual" && (
                    <div className="full-field promotion-product-picker">
                      <label>
                        Rechercher les produits
                        <input
                          value={productSearch}
                          onChange={(event) =>
                            setProductSearch(event.target.value)
                          }
                          placeholder="Nom ou marque..."
                        />
                      </label>
                      <div className="promotion-product-options">
                        {productOptions.map((product) => (
                          <button
                            type="button"
                            key={product.product_id}
                            className={
                              form.product_ids.includes(product.product_id)
                                ? "selected"
                                : ""
                            }
                            onClick={() =>
                              togglePromotionProduct(product.product_id)
                            }
                          >
                            <span>
                              <strong>
                                {product.name || `Produit #${product.product_id}`}
                              </strong>
                              <small>
                                {product.brand || "NUTRIFIT"} · {product.stock} en stock
                              </small>
                            </span>
                            <b>
                              {product.price?.toFixed(2)} {product.currency}
                            </b>
                          </button>
                        ))}
                      </div>
                      <small className="muted">
                        {form.product_ids.length} produit(s) selectionne(s)
                        {form.promotion_kind === "pack"
                          ? " · minimum 2, sans limite maximale"
                          : ""}
                      </small>
                    </div>
                  )}
                  <label>
                    Reduction proposee
                    <input
                      type="number"
                      min="0"
                      max="50"
                      step="0.5"
                      value={form.discount_percentage}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          discount_percentage: event.target.value,
                        })
                      }
                      placeholder="Ex: 10"
                    />
                  </label>
                  <label>
                    Debut de la promotion
                    <input
                      type="datetime-local"
                      value={form.starts_at}
                      onChange={(event) =>
                        setForm({ ...form, starts_at: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Fin de la promotion
                    <input
                      type="datetime-local"
                      value={form.ends_at}
                      onChange={(event) =>
                        setForm({ ...form, ends_at: event.target.value })
                      }
                    />
                  </label>
                  <div className="full-field promotion-suggestion-actions">
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={suggestPromotion}
                      disabled={suggesting}
                    >
                      {suggesting
                        ? "Analyse en cours..."
                        : form.selection_mode === "automatic"
                          ? "Proposer les produits avec le score"
                          : "Verifier ma selection"}
                    </button>
                  </div>
                  {suggestion && (
                    <div className="full-field promotion-score-preview">
                      <div className="content-panel-title">
                        <div>
                          <span>SCORE MARKETING</span>
                          <strong>
                            {suggestion.promotion_kind === "pack"
                              ? "Pack recommande"
                              : "Produit recommande"}
                          </strong>
                        </div>
                        <b>
                          {suggestion.suggested_price.toFixed(2)}{" "}
                          {suggestion.currency}
                        </b>
                      </div>
                      {suggestion.products.map((product) => (
                        <article key={product.product_id}>
                          <div>
                            <strong>{product.name}</strong>
                            <small>
                              #{product.product_id} · {product.stock} en stock
                            </small>
                          </div>
                          <span>{product.score}/100</span>
                          <small>{product.reasons.join(" · ")}</small>
                        </article>
                      ))}
                      <p>
                        Prix normal:{" "}
                        <strong>
                          {suggestion.regular_total.toFixed(2)}{" "}
                          {suggestion.currency}
                        </strong>
                        {" · "}
                        Reduction suggeree:{" "}
                        <strong>
                          {suggestion.suggested_discount_percentage}%
                        </strong>
                      </p>
                      <ul>
                        {suggestion.data_notes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
              <label className="full-field">
                Offre exacte (optionnel)
                <input
                  value={form.offer_details}
                  onChange={(event) =>
                    setForm({ ...form, offer_details: event.target.value })
                  }
                  placeholder="Laisser vide si aucune reduction n'est validee"
                />
              </label>
              <fieldset className="full-field channel-selector">
                <legend>Canaux</legend>
                <div className="marketing-channel-grid">
                  {channelOptions.map(([value, label]) => (
                    <label key={value}>
                      <input
                        type="checkbox"
                        checked={form.channels.includes(value)}
                        onChange={() => toggleFormChannel(value)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
            <button className="button button-ai" disabled={generating}>
              {generating
                ? "Marketing Agent travaille..."
                : form.campaign_type === "promotion"
                  ? "Generer toute la promotion avec AI"
                  : "Generer la campagne"}
            </button>
          </form>

          <section className="content-library">
            <div className="content-panel-title">
              <div>
                <span>BIBLIOTHEQUE</span>
                <strong>Historique des campagnes</strong>
              </div>
            </div>
            {!items.length ? (
              <div className="empty-state compact">
                <h3>Aucune campagne</h3>
                <p>Genere ta premiere campagne marketing.</p>
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
                      {campaignStatusLabel(item)}
                    </span>
                    <strong>{item.campaign_title}</strong>
                    <small>
                      {campaignTypes.find(
                        ([value]) => value === item.campaign_type
                      )?.[1] || item.campaign_type}
                      {" · "}
                      {item.channels.join(", ")}
                    </small>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="panel content-review marketing-review">
          {!selected ? (
            <div className="empty-state">
              <h3>Selectionne une campagne</h3>
              <p>La proposition apparaitra ici pour review.</p>
            </div>
          ) : (
            <>
              <div className="content-panel-title">
                <div>
                  <span>REVIEW ADMIN</span>
                  <strong>Campagne #{selected.id}</strong>
                </div>
                <span className={`content-status status-${selected.status}`}>
                  {campaignStatusLabel(selected)}
                </span>
              </div>
              <div className="content-meta">
                <span>{selected.model}</span>
                <span>{selected.tone}</span>
                <span>{selected.campaign_type}</span>
              </div>
              {selected.campaign_type === "promotion" && (
                <div className="marketing-copy-block promotion-review-block">
                  <strong>Configuration de la promotion</strong>
                  <div className="form-grid">
                    <label>
                      Format
                      <select
                        value={selected.promotion_kind || "single_product"}
                        onChange={(event) =>
                          updateSelected({
                            promotion_kind: event.target.value as
                              | "single_product"
                              | "pack",
                            product_ids:
                              event.target.value === "single_product"
                                ? selected.product_ids.slice(0, 1)
                                : selected.product_ids,
                          })
                        }
                      >
                        <option value="single_product">Produit unique</option>
                        <option value="pack">Pack</option>
                      </select>
                    </label>
                    <label>
                      Selection
                      <select
                        value={selected.selection_mode || "automatic"}
                        onChange={(event) =>
                          updateSelected({
                            selection_mode: event.target.value as
                              | "automatic"
                              | "manual",
                          })
                        }
                      >
                        <option value="automatic">Marketing Agent</option>
                        <option value="manual">Admin</option>
                      </select>
                    </label>
                    {selected.selection_mode === "manual" ? (
                      <div className="full-field promotion-product-picker review-product-picker">
                        <label>
                          Rechercher les produits
                          <input
                            value={reviewProductSearch}
                            onChange={(event) =>
                              setReviewProductSearch(event.target.value)
                            }
                            placeholder="Nom ou marque..."
                          />
                        </label>
                        <div className="promotion-selected-products">
                          {selected.product_ids.map((productId) => {
                            const product =
                              selected.selection_scores.find(
                                (item) => item.product_id === productId,
                              )
                              || reviewProductOptions.find(
                                (item) => item.product_id === productId,
                              );
                            return (
                              <button
                                type="button"
                                key={productId}
                                onClick={() => toggleReviewedProduct(productId)}
                                aria-label={`Retirer ${product?.name || `produit ${productId}`}`}
                              >
                                <span>{product?.name || `Produit #${productId}`}</span>
                                <b>Retirer</b>
                              </button>
                            );
                          })}
                        </div>
                        <div className="promotion-product-options">
                          {reviewProductOptions.map((product) => (
                            <button
                              type="button"
                              key={product.product_id}
                              className={
                                selected.product_ids.includes(product.product_id)
                                  ? "selected"
                                  : ""
                              }
                              onClick={() =>
                                toggleReviewedProduct(product.product_id)
                              }
                            >
                              <span>
                                <strong>
                                  {product.name || `Produit #${product.product_id}`}
                                </strong>
                                <small>
                                  {product.brand || "NUTRIFIT"} · {product.stock} en stock
                                </small>
                              </span>
                              <b>
                                {product.price?.toFixed(2)} {product.currency}
                              </b>
                            </button>
                          ))}
                        </div>
                        <small className="muted">
                          {selected.product_ids.length} produit(s) selectionne(s)
                          {selected.promotion_kind === "pack"
                            ? " · minimum 2"
                            : " · un seul produit"}
                        </small>
                      </div>
                    ) : (
                      <div className="full-field automatic-product-summary">
                        <small>Produits choisis par Marketing Agent</small>
                        {selected.selection_scores.map((product) => (
                          <strong key={product.product_id}>{product.name}</strong>
                        ))}
                      </div>
                    )}
                    <label>
                      Reduction (%)
                      <input
                        type="number"
                        min="0"
                        max="50"
                        step="0.5"
                        value={selected.discount_percentage ?? ""}
                        onChange={(event) =>
                          updateSelected({
                            discount_percentage: event.target.value
                              ? Number(event.target.value)
                              : null,
                          })
                        }
                      />
                    </label>
                    <label>
                      Debut
                      <input
                        type="datetime-local"
                        value={toLocalDateTime(selected.starts_at)}
                        onChange={(event) =>
                          updateSelected({
                            starts_at: event.target.value
                              ? new Date(event.target.value).toISOString()
                              : null,
                          })
                        }
                      />
                    </label>
                    <label>
                      Fin
                      <input
                        type="datetime-local"
                        value={toLocalDateTime(selected.ends_at)}
                        onChange={(event) =>
                          updateSelected({
                            ends_at: event.target.value
                              ? new Date(event.target.value).toISOString()
                              : null,
                          })
                        }
                      />
                    </label>
                  </div>
                  <div className="promotion-score-list">
                    {selected.selection_scores.map((product) => (
                      <article key={product.product_id}>
                        <strong>{product.name}</strong>
                        <span>{product.score}/100</span>
                        <small>{product.reasons.join(" · ")}</small>
                      </article>
                    ))}
                  </div>
                  <small className="muted">
                    Validation admin obligatoire. La marge doit etre verifiee
                    tant que le cout d&apos;achat produit n&apos;est pas
                    renseigne.
                  </small>
                </div>
              )}
              <fieldset className="channel-selector review-channels">
                <legend>Canaux valides</legend>
                <div className="marketing-channel-grid">
                  {channelOptions.map(([value, label]) => (
                    <label key={value}>
                      <input
                        type="checkbox"
                        checked={selected.channels.includes(value)}
                        onChange={() => toggleSelectedChannel(value)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <label>
                Audience
                <input
                  value={selected.audience}
                  onChange={(event) =>
                    updateSelected({ audience: event.target.value })
                  }
                />
              </label>
              <label>
                Nom de campagne
                <textarea
                  className="marketing-short-textarea"
                  rows={2}
                  value={selected.campaign_title}
                  onChange={(event) =>
                    updateSelected({ campaign_title: event.target.value })
                  }
                />
              </label>
              <label>
                Accroche
                <textarea
                  className="marketing-short-textarea"
                  rows={2}
                  value={selected.headline}
                  onChange={(event) =>
                    updateSelected({ headline: event.target.value })
                  }
                />
              </label>
              <label>
                Message central
                <textarea
                  value={selected.core_message}
                  onChange={(event) =>
                    updateSelected({ core_message: event.target.value })
                  }
                />
              </label>
              {selected.channels.includes("email") && (
                <div className="marketing-copy-block">
                  <strong>Email</strong>
                  <label>
                    Objet
                    <textarea
                      className="marketing-short-textarea"
                      rows={2}
                      value={selected.email_subject || ""}
                      onChange={(event) =>
                        updateSelected({
                          email_subject: event.target.value || null,
                        })
                      }
                    />
                  </label>
                  <label>
                    Corps
                    <textarea
                      value={selected.email_body || ""}
                      onChange={(event) =>
                        updateSelected({
                          email_body: event.target.value || null,
                        })
                      }
                    />
                  </label>
                </div>
              )}
              {selected.channels.includes("whatsapp") && (
                <div className="marketing-copy-block">
                  <strong>WhatsApp</strong>
                  <label>
                    Message
                    <textarea
                      value={selected.whatsapp_message || ""}
                      onChange={(event) =>
                        updateSelected({
                          whatsapp_message: event.target.value || null,
                        })
                      }
                    />
                  </label>
                </div>
              )}
              {selected.channels.some((channel) =>
                channel === "instagram" || channel === "facebook"
              ) && (
                <div className="marketing-copy-block">
                  <strong>Reseaux sociaux</strong>
                  <label>
                    Legende
                    <textarea
                      value={selected.social_caption || ""}
                      onChange={(event) =>
                        updateSelected({
                          social_caption: event.target.value || null,
                        })
                      }
                    />
                  </label>
                </div>
              )}
              <label>
                Texte du CTA
                <input
                  value={selected.cta_label}
                  onChange={(event) =>
                    updateSelected({ cta_label: event.target.value })
                  }
                />
              </label>
              <label>
                Hashtags
                <input
                  value={selected.hashtags.join(" ")}
                  onChange={(event) =>
                    updateSelected({
                      hashtags: splitHashtags(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                Planning recommande
                <textarea
                  className="marketing-short-textarea"
                  rows={2}
                  value={selected.recommended_schedule || ""}
                  onChange={(event) =>
                    updateSelected({
                      recommended_schedule: event.target.value || null,
                    })
                  }
                />
              </label>
              <div className="content-review-actions">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={save}
                  disabled={saving}
                >
                  Enregistrer brouillon
                </button>
                <button
                  type="button"
                  className="button"
                  onClick={approve}
                  disabled={saving}
                >
                  {saving ? "Traitement..." : "Valider la campagne"}
                </button>
                <button
                  type="button"
                  className="button button-danger"
                  onClick={archive}
                  disabled={saving}
                >
                  Archiver
                </button>
              </div>
            </>
          )}
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

function toLocalDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function campaignStatusLabel(campaign: MarketingCampaign): string {
  if (campaign.status === "approved") {
    const now = Date.now();
    if (campaign.starts_at && new Date(campaign.starts_at).getTime() > now) {
      return "Planifiee";
    }
    if (campaign.ends_at && new Date(campaign.ends_at).getTime() < now) {
      return "Terminee";
    }
    return "Actif";
  }
  if (campaign.status === "draft") return "Brouillon";
  return "Archive";
}
