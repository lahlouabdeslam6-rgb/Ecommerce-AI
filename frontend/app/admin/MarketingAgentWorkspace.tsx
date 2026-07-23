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
  product_id: string;
  offer_details: string;
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
  product_id: "",
  offer_details: "",
};

export function MarketingAgentWorkspace() {
  const [items, setItems] = useState<MarketingCampaign[]>([]);
  const [selected, setSelected] = useState<MarketingCampaign | null>(null);
  const [form, setForm] = useState<GenerateForm>(emptyGenerate);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
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
            product_id: form.product_id ? Number(form.product_id) : null,
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
        <strong>Validation admin obligatoire</strong>
        <span>
          L&apos;AI prepare les textes. Elle ne change aucun prix et
          n&apos;envoie aucun email, WhatsApp ou post automatiquement.
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
                Sujet
                <input
                  value={form.topic}
                  onChange={(event) =>
                    setForm({ ...form, topic: event.target.value })
                  }
                  placeholder="Ex: campagne creatine pour la rentree"
                  required
                  minLength={3}
                />
              </label>
              <label className="full-field">
                Objectif
                <textarea
                  value={form.objective}
                  onChange={(event) =>
                    setForm({ ...form, objective: event.target.value })
                  }
                  placeholder="Ex: faire decouvrir la selection et attirer vers le catalogue"
                  required
                  minLength={3}
                />
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
              <label>
                Produit lie (optionnel)
                <input
                  type="number"
                  min="1"
                  value={form.product_id}
                  onChange={(event) =>
                    setForm({ ...form, product_id: event.target.value })
                  }
                  placeholder="ID produit"
                />
              </label>
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
                      {item.status}
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
                  {selected.status}
                </span>
              </div>
              <div className="content-meta">
                <span>{selected.model}</span>
                <span>{selected.tone}</span>
                <span>{selected.campaign_type}</span>
              </div>
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
                <input
                  value={selected.campaign_title}
                  onChange={(event) =>
                    updateSelected({ campaign_title: event.target.value })
                  }
                />
              </label>
              <label>
                Accroche
                <input
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
                    <input
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
                <input
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
