"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Protected } from "../../../components/Protected";
import { ProductImageManager } from "../../../components/ProductImageManager";
import { api } from "../../../lib/api";
import type { Product } from "../../../types";

type ProductForm = {
  name: string;
  brand: string;
  category: string;
  description: string;
  price: number;
  stock: number;
  currency: string;
  is_active: boolean;
};

export default function SupportProductEditorPage() {
  const params = useParams();
  const router = useRouter();
  const productId = Number(params.id);
  const [form, setForm] = useState<ProductForm | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const product = await api<Product>(`/api/products/${productId}`);
      setProduct(product);
      setForm({
        name: product.name || "",
        brand: product.brand || "",
        category: product.category || "",
        description: product.description || "",
        price: product.price || 0,
        stock: product.stock,
        currency: product.currency,
        is_active: product.is_active,
      });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    if (Number.isInteger(productId) && productId > 0) void load();
  }, [productId]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api<Product>(
        `/api/products/${productId}`,
        { method: "PATCH", body: JSON.stringify(form) },
        true,
      );
      setProduct(updated);
      setMessage("Produit mis a jour.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const uploadMedia = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    const data = new FormData();
    files.forEach((file) => data.append("files", file));
    setError("");
    try {
      const updated = await api<Product>(
        `/api/products/${productId}/media`,
        { method: "POST", body: data },
        true,
      );
      setProduct(updated);
      setMessage(`${files.length} média(s) ajouté(s).`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      event.target.value = "";
    }
  };

  return (
    <Protected roles={["support", "admin"]}>
      <section className="shell page-section">
        <div className="page-title">
          <div>
            <p className="kicker">Catalogue support</p>
            <h1>Modifier le produit #{productId}</h1>
          </div>
          <button className="text-link" onClick={() => router.push("/")}>Retour aux produits</button>
        </div>
        {message && <div className="alert alert-success">{message}</div>}
        {error && <div className="alert alert-error">{error}</div>}
        {!form ? (
          <div className="page-loading">Chargement...</div>
        ) : (
          <form className="panel product-editor" onSubmit={save}>
            <div className="form-grid">
              <label>Nom<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
              <label>Marque<input value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} required /></label>
              <label>Categorie<input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label>
              <label>Prix MAD<input type="number" min="0" step="0.01" value={form.price} onChange={(event) => setForm({ ...form, price: Number(event.target.value) })} required /></label>
              <label>Stock<input type="number" min="0" value={form.stock} onChange={(event) => setForm({ ...form, stock: Number(event.target.value) })} required /></label>
              <label className="check-filter"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} /><span>Produit actif</span></label>
              <label className="full-field">Description<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
              <label className="full-field">Ajouter des photos ou vidéos<input type="file" accept="image/png,image/jpeg,image/webp,video/mp4,video/webm,video/quicktime,video/x-m4v" multiple onChange={uploadMedia} /><small>Jusqu&apos;à 8 fichiers par envoi. Photo: 5 MB. Vidéo: 50 MB.</small></label>
              {product && <div className="full-field"><strong>Médias actuels</strong><ProductImageManager product={product} onChange={setProduct} onError={setError} /></div>}
            </div>
            <div className="editor-actions">
              <button className="button" disabled={saving}>{saving ? "Enregistrement..." : "Enregistrer"}</button>
            </div>
          </form>
        )}
      </section>
    </Protected>
  );
}
