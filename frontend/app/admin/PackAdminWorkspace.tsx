"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, assetUrl, money } from "../lib/api";
import type { Pack, PackList, Product, ProductList } from "../types";

type PackForm = {
  name: string;
  description: string;
  highlights: string;
  discount_percentage: number;
  promotional_price: string;
  is_active: boolean;
  starts_at: string;
  ends_at: string;
  items: Array<{ product_id: number; quantity: number }>;
};

const emptyForm: PackForm = {
  name: "", description: "", highlights: "", discount_percentage: 10,
  promotional_price: "", is_active: true, items: [],
  starts_at: "", ends_at: "",
};

const toLocalDateTime = (value: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
};

export function PackAdminWorkspace() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [packSearch, setPackSearch] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [editing, setEditing] = useState<Pack | null>(null);
  const [form, setForm] = useState<PackForm>(emptyForm);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [manualPrice, setManualPrice] = useState(false);
  const [productCosts, setProductCosts] = useState<Record<number, number | null>>({});

  const regularTotal = useMemo(() => form.items.reduce((total, item) => {
    const product = products.find((value) => value.product_id === item.product_id);
    return total + Number(product?.price || 0) * item.quantity;
  }, 0), [form.items, products]);
  const calculatedPromotionalPrice = Math.max(
    0,
    regularTotal * (1 - Number(form.discount_percentage || 0) / 100),
  );
  const displayedPromotionalPrice = manualPrice && form.promotional_price !== ""
    ? Number(form.promotional_price)
    : calculatedPromotionalPrice;
  const savings = Math.max(0, regularTotal - displayedPromotionalPrice);
  const allCostsKnown = form.items.length > 0 && form.items.every(
    (item) => Object.prototype.hasOwnProperty.call(productCosts, item.product_id)
      && productCosts[item.product_id] !== null,
  );
  const costTotal = allCostsKnown ? form.items.reduce(
    (total, item) => total + Number(productCosts[item.product_id]) * item.quantity,
    0,
  ) : null;
  const estimatedMargin = costTotal === null ? null : displayedPromotionalPrice - costTotal;

  useEffect(() => {
    const productIds = Array.from(new Set(form.items.map((item) => item.product_id)));
    if (!productIds.length) return;
    let cancelled = false;
    void Promise.all(productIds.map(async (productId) => {
      try {
        const value = await api<{ cost_price: number | null }>(`/api/products/costs/${productId}`, {}, true);
        return [productId, value.cost_price] as const;
      } catch {
        return [productId, null] as const;
      }
    })).then((entries) => {
      if (!cancelled) setProductCosts((current) => ({ ...current, ...Object.fromEntries(entries) }));
    });
    return () => { cancelled = true; };
  }, [form.items]);

  const loadPacks = (search = packSearch) => api<PackList>(`/api/packs/admin/manage${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`, {}, true).then((value) => setPacks(value.items));
  const searchProducts = (search = productSearch) => api<ProductList>(`/api/products/manage?page_size=100${search.trim() ? `&search=${encodeURIComponent(search.trim())}` : ""}`, {}, true).then((value) => setProducts(value.items));

  useEffect(() => { void loadPacks("").catch((e: Error) => setError(e.message)); void searchProducts("").catch(() => undefined); }, []);

  const chooseCover = (file: File | null) => {
    setCoverFile(file);
    setCoverPreview((current) => {
      if (current?.startsWith("blob:")) URL.revokeObjectURL(current);
      return file ? URL.createObjectURL(file) : null;
    });
  };

  const selectPack = (pack: Pack) => {
    chooseCover(null);
    setEditing(pack);
    const automaticPrice = pack.regular_price * (1 - pack.discount_percentage / 100);
    setManualPrice(Math.abs(pack.promotional_price - automaticPrice) > 0.01);
    setForm({
      name: pack.name,
      description: pack.description,
      highlights: pack.highlights.join("\n"),
      discount_percentage: pack.discount_percentage,
      promotional_price: pack.promotional_price.toFixed(2),
      is_active: pack.is_active,
      starts_at: toLocalDateTime(pack.starts_at),
      ends_at: toLocalDateTime(pack.ends_at),
      items: pack.products.map((item) => ({ product_id: item.product.product_id, quantity: item.quantity })),
    });
    setProducts((current) => {
      const merged = new Map(current.map((product) => [product.product_id, product]));
      pack.products.forEach(({ product }) => merged.set(product.product_id, product));
      return Array.from(merged.values());
    });
    setError(""); setMessage("");
  };

  const toggleProduct = (productId: number) => setForm((value) => ({
    ...value,
    items: value.items.some((item) => item.product_id === productId)
      ? value.items.filter((item) => item.product_id !== productId)
      : [...value.items, { product_id: productId, quantity: 1 }],
  }));

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(""); setMessage("");
    if (form.items.length < 2) { setError("Selectionne au moins 2 produits."); return; }
    if (form.description.trim().length < 20) { setError("Ajoute un resume du pack de 20 caracteres minimum."); return; }
    if (!coverFile && !editing?.main_image_url) { setError("Ajoute la photo principale qui montre le pack complet."); return; }
    if (form.starts_at && form.ends_at && new Date(form.ends_at) <= new Date(form.starts_at)) { setError("La date de fin doit etre apres la date de debut."); return; }
    if (estimatedMargin !== null && estimatedMargin < 0) { setError("Le prix promo est inferieur au cout d'achat total. Corrige le prix ou la reduction."); return; }
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        description: form.description,
        highlights: form.highlights.split("\n").map((item) => item.trim()).filter(Boolean),
        items: form.items,
        discount_percentage: Number(form.discount_percentage),
        ...(manualPrice && form.promotional_price
          ? { promotional_price: Number(form.promotional_price) }
          : {}),
        is_active: form.is_active,
        starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
      };
      let saved = await api<Pack>(
        editing ? `/api/packs/admin/manage/${editing.id}` : "/api/packs/admin/manage",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) }, true,
      );
      setEditing(saved);
      if (coverFile) {
        const coverData = new FormData();
        coverData.append("file", coverFile);
        saved = await api<Pack>(`/api/packs/admin/manage/${saved.id}/cover`, { method: "POST", body: coverData }, true);
      }
      setEditing(saved); selectPack(saved); await loadPacks(""); setMessage("Pack enregistre.");
    } catch (e) { setError((e as Error).message); } finally { setSaving(false); }
  };

  const uploadImages = async (files: FileList | null) => {
    if (!editing || !files?.length) return;
    const data = new FormData(); Array.from(files).forEach((file) => data.append("files", file));
    try {
      const saved = await api<Pack>(`/api/packs/admin/manage/${editing.id}/images`, { method: "POST", body: data }, true);
      setEditing(saved); await loadPacks(""); setMessage("Photos ajoutees.");
    } catch (e) { setError((e as Error).message); }
  };

  const deletePack = async () => {
    if (!editing || !window.confirm(`Supprimer le pack ${editing.name} ?`)) return;
    try { await api<void>(`/api/packs/admin/manage/${editing.id}`, { method: "DELETE" }, true); setEditing(null); setManualPrice(false); setForm(emptyForm); chooseCover(null); await loadPacks(""); setMessage("Pack supprime."); }
    catch (e) { setError((e as Error).message); }
  };

  return <div className="pack-admin-workspace">
    <div className="page-title"><div><p className="kicker">Catalogue</p><h2>Packs</h2></div><button className="button button-small" onClick={() => { setEditing(null); setManualPrice(false); setForm(emptyForm); chooseCover(null); }}>Ajouter un pack</button></div>
    {error && <div className="alert alert-error">{error}</div>}{message && <div className="alert alert-success">{message}</div>}
    <div className="pack-admin-layout">
      <section className="panel pack-admin-list">
        <form onSubmit={(event) => { event.preventDefault(); void loadPacks(); }}><label>Rechercher un pack<input value={packSearch} onChange={(event) => setPackSearch(event.target.value)} placeholder="Nom du pack" /></label><button className="button button-small">Rechercher</button></form>
        <div>{packs.map((pack) => <button key={pack.id} onClick={() => selectPack(pack)} className={editing?.id === pack.id ? "active" : ""}><span>{pack.main_image_url ? <img src={assetUrl(pack.main_image_url) || ""} alt="" /> : "N"}</span><span><strong>{pack.name}</strong><small>{pack.products.length} produits · {money(pack.promotional_price)}</small></span><i className={pack.is_active ? "dot active" : "dot"} /></button>)}</div>
      </section>
      <form className="panel pack-admin-editor" onSubmit={submit}>
        <div className="form-grid">
          <label>Nom du pack<input required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Reduction (%)<input type="number" min="0" max="90" step="0.5" value={form.discount_percentage} onChange={(e) => setForm({ ...form, discount_percentage: Number(e.target.value) })} /></label>
          <label className="check-filter"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /><span>Pack actif</span></label>
          <label>Debut de l&apos;offre<input type="datetime-local" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} /></label>
          <label>Fin de l&apos;offre<input type="datetime-local" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} /></label>
          <section className="full-field pack-price-calculator">
            <div className="pack-price-summary">
              <span><small>Prix normal calcule</small><strong>{money(regularTotal)}</strong></span>
              <span><small>Economie client</small><strong>{money(savings)}</strong></span>
              <span><small>Cout d&apos;achat</small><strong>{costTotal === null ? "A completer" : money(costTotal)}</strong></span>
              <span><small>Marge estimee</small><strong className={estimatedMargin !== null && estimatedMargin < 0 ? "negative" : ""}>{estimatedMargin === null ? "Indisponible" : money(estimatedMargin)}</strong></span>
            </div>
            <label>
              Prix promo (modifiable)
              <input
                type="number"
                min="0"
                step="0.01"
                value={
                  manualPrice
                    ? form.promotional_price
                    : calculatedPromotionalPrice.toFixed(2)
                }
                onChange={(event) => {
                  setManualPrice(true);
                  setForm({ ...form, promotional_price: event.target.value });
                }}
              />
              <small>
                {manualPrice
                  ? "Prix modifie manuellement."
                  : `Calcul automatique avec ${form.discount_percentage}% de reduction.`}
              </small>
              {manualPrice && (
                <button
                  type="button"
                  className="pack-price-reset"
                  onClick={() => setManualPrice(false)}
                >
                  Recalculer automatiquement
                </button>
              )}
              {form.discount_percentage >= 25 && <small className="pack-price-warning">Reduction elevee : verifie la marge avant l&apos;enregistrement.</small>}
              {estimatedMargin !== null && estimatedMargin < 0 && <small className="pack-price-error">Prix refuse : il est inferieur au cout d&apos;achat total.</small>}
              {costTotal === null && form.items.length > 0 && <small>Renseigne le prix d&apos;achat de chaque produit pour obtenir une marge fiable.</small>}
            </label>
          </section>
          <label className="full-field">Resume du pack pour le client<textarea required minLength={20} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Explique ce que contient le pack, son objectif et l'avantage de l'offre." /><small>Ce texte apparait dans la premiere vue. Il doit parler du pack complet, pas d'un seul produit.</small></label>
          <label className="full-field">Points forts (une ligne par point)<textarea value={form.highlights} onChange={(e) => setForm({ ...form, highlights: e.target.value })} /></label>
        </div>
        <section className="pack-cover-admin">
          <div><strong>Photo principale du pack</strong><small>Obligatoire. Ajoute une seule photo qui montre le pack complet.</small></div>
          <label>
            <span className="pack-cover-preview">
              {coverPreview ? <img src={coverPreview} alt="Nouvelle photo du pack" /> : editing?.main_image_url ? <img src={assetUrl(editing.main_image_url) || ""} alt="Photo actuelle du pack" /> : <b>N</b>}
            </span>
            <span><strong>{coverFile ? coverFile.name : editing?.main_image_url ? "Remplacer la photo principale" : "Choisir la photo du pack"}</strong><small>JPG, PNG ou WebP · 5 MB maximum</small></span>
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => chooseCover(event.target.files?.[0] || null)} />
          </label>
        </section>
        <section className="pack-product-picker"><div><strong>Produits du pack</strong><small>{form.items.length} selectionne(s), minimum 2</small></div><div className="pack-product-search"><input value={productSearch} onChange={(event) => setProductSearch(event.target.value)} placeholder="Rechercher un produit ou une marque" /><button type="button" className="button button-small" onClick={() => void searchProducts()}>Rechercher</button></div><div className="pack-product-options">{products.map((product) => { const selected = form.items.find((item) => item.product_id === product.product_id); return <article className={selected ? "selected" : ""} key={product.product_id}><button type="button" onClick={() => toggleProduct(product.product_id)}><span>{product.images?.[0] ? <img src={assetUrl(product.images[0]) || ""} alt="" /> : "N"}</span><span><strong>{product.name}</strong><small>{product.brand} · {money(product.price || 0)}</small></span><b>{selected ? "Retirer" : "Ajouter"}</b></button>{selected && <label>Quantite<input type="number" min="1" max="20" value={selected.quantity} onChange={(e) => setForm((value) => ({ ...value, items: value.items.map((item) => item.product_id === product.product_id ? { ...item, quantity: Number(e.target.value) } : item) }))} /></label>}</article>; })}</div></section>
        {editing && <section className="pack-media-admin"><label>Photos supplementaires (optionnel)<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(e) => void uploadImages(e.target.files)} /></label><small>Ces photos completent la galerie. La couverture principale se change dans la section au-dessus.</small><div>{Array.from(new Set([editing.main_image_url, ...editing.gallery].filter(Boolean))).map((image) => <button type="button" key={image} className={editing.main_image_url === image ? "active" : ""} onClick={async () => { const saved = await api<Pack>(`/api/packs/admin/manage/${editing.id}/main-image?image_url=${encodeURIComponent(image as string)}`, { method: "PATCH" }, true); setEditing(saved); }}><img src={assetUrl(image as string) || ""} alt="" /><small>{editing.main_image_url === image ? "Photo principale" : "Choisir"}</small></button>)}</div></section>}
        <div className="editor-actions"><button className="button" disabled={saving}>{saving ? "Enregistrement..." : "Enregistrer le pack"}</button>{editing && <button type="button" className="button button-danger" onClick={deletePack}>Supprimer</button>}</div>
      </form>
    </div>
  </div>;
}
