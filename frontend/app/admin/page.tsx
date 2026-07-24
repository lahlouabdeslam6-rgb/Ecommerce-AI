"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Protected } from "../components/Protected";
import { useAuth } from "../components/AuthProvider";
import { StatCard as Stat } from "../components/StatCard";
import { ProductImageManager } from "../components/ProductImageManager";
import { ContentAgentWorkspace } from "./ContentAgentWorkspace";
import { AdminTicketWorkspace } from "./AdminTicketWorkspace";
import { MarketingAgentWorkspace } from "./MarketingAgentWorkspace";
import { SafetyAgentWorkspace } from "./SafetyAgentWorkspace";
import { api, money } from "../lib/api";
import type { PaginatedOrders, Product, ProductList, User } from "../types";

type Dashboard = { users: number; products: number; active_products: number; low_stock_products: number; orders: number; pending_orders: number; delivered_orders: number; revenue_mad: number };
type UserList = { items: User[]; total: number; page: number; page_size: number; total_pages: number };
type ProductForm = { name: string; brand: string; category: string; description: string; price: number; stock: number; currency: string; is_active: boolean };
type SupportForm = { full_name: string; email: string; password: string; is_active: boolean };
type AuditLog = { id: number; actor_id: number | null; actor_email: string | null; actor_role: string; action: string; entity_type: string; entity_id: string | null; details: string | null; created_at: string };
type AuditLogList = { items: AuditLog[]; total: number };
type ProductAISuggestion = { product_id: number; model: string; cached: boolean; description: string; category: string; seo_title: string; seo_description: string; seo_keywords: string[]; tags: string[] };
type ProductAIApplyResponse = { product: Product; indexed: boolean };

const emptyProduct: ProductForm = { name: "", brand: "", category: "", description: "", price: 0, stock: 0, currency: "MAD", is_active: true };
const emptySupport: SupportForm = { full_name: "", email: "", password: "", is_active: true };
const orderStatuses = ["pending", "confirmed", "preparing", "shipped", "delivered", "delivery_failed", "cancelled"];

export default function AdminPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const productToEdit = searchParams.get("product");
  const requestedTab = searchParams.get("tab");
  const requestedTicketId = Number(searchParams.get("ticket"));
  const { user } = useAuth();
  const [tab, setTab] = useState("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [products, setProducts] = useState<ProductList | null>(null);
  const [orders, setOrders] = useState<PaginatedOrders | null>(null);
  const [users, setUsers] = useState<UserList | null>(null);
  const [supportUsers, setSupportUsers] = useState<UserList | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogList | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [productForm, setProductForm] = useState<ProductForm>(emptyProduct);
  const [editingSupportId, setEditingSupportId] = useState<number | null>(null);
  const [supportForm, setSupportForm] = useState<SupportForm>(emptySupport);
  const [savingSupport, setSavingSupport] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<ProductAISuggestion | null>(null);
  const [generatingAI, setGeneratingAI] = useState(false);
  const [applyingAI, setApplyingAI] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    if (user?.role !== "admin") return;
    try {
      const [d, p, o, u, s, a] = await Promise.all([
        api<Dashboard>("/api/admin/dashboard", {}, true),
        api<ProductList>("/api/products?page_size=20"),
        api<PaginatedOrders>("/api/admin/orders?page_size=30", {}, true),
        api<UserList>("/api/admin/users?page_size=50", {}, true),
        api<UserList>("/api/admin/support-users?page_size=100", {}, true),
        api<AuditLogList>("/api/admin/audit-logs?page_size=100", {}, true),
      ]);
      setDashboard(d); setProducts(p); setOrders(o); setUsers(u); setSupportUsers(s); setAuditLogs(a);
    } catch (err) { setError((err as Error).message); }
  };

  useEffect(() => { void load(); }, [user]);

  useEffect(() => {
    if (requestedTab === "messages") setTab("messages");
  }, [requestedTab]);

  useEffect(() => {
    const productId = Number(productToEdit);
    if (user?.role !== "admin" || !Number.isInteger(productId) || productId < 1) return;
    api<Product>(`/api/products/${productId}`)
      .then((product) => {
        setEditingId(product.product_id);
        setEditingProduct(product);
        setProductForm({ name: product.name || "", brand: product.brand || "", category: product.category || "", description: product.description || "", price: product.price || 0, stock: product.stock, currency: product.currency, is_active: product.is_active });
        setAiSuggestion(null);
        setTab("product-editor");
      })
      .catch((err: Error) => setError(err.message));
  }, [user, productToEdit]);

  const editProduct = (product: Product) => {
    setEditingId(product.product_id);
    setEditingProduct(product);
    setProductForm({ name: product.name || "", brand: product.brand || "", category: product.category || "", description: product.description || "", price: product.price || 0, stock: product.stock, currency: product.currency, is_active: product.is_active });
    setAiSuggestion(null);
    setTab("product-editor");
  };

  const saveProduct = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    try {
      if (editingId) setEditingProduct(await api<Product>(`/api/products/${editingId}`, { method: "PATCH", body: JSON.stringify(productForm) }, true));
      else await api<Product>("/api/products", { method: "POST", body: JSON.stringify({ ...productForm, images: [], ingredients: [] }) }, true);
      setMessage(editingId ? "Produit mis a jour." : "Produit cree.");
      setEditingId(null); setProductForm(emptyProduct); setTab("products"); router.replace("/admin"); await load();
    } catch (err) { setError((err as Error).message); }
  };

  const deleteProduct = async () => {
    if (!editingId || !window.confirm("Supprimer definitivement ce produit ?")) return;
    try { await api<void>(`/api/products/${editingId}`, { method: "DELETE" }, true); setMessage("Produit supprime."); setEditingId(null); setTab("products"); await load(); }
    catch (err) { setError((err as Error).message); }
  };

  const uploadImage = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file || !editingId) return;
    const form = new FormData(); form.append("image", file);
    try { const updated = await api<Product>(`/api/products/${editingId}/images`, { method: "POST", body: form }, true); setEditingProduct(updated); setMessage("Photo ajoutee."); await load(); }
    catch (err) { setError((err as Error).message); }
  };

  const generateProductSuggestion = async () => {
    if (!editingId) return;
    setError(""); setMessage(""); setGeneratingAI(true);
    try {
      const suggestion = await api<ProductAISuggestion>(
        `/api/admin/ai/products/${editingId}/suggest`,
        { method: "POST" },
        true,
      );
      setAiSuggestion(suggestion);
      setMessage(suggestion.cached ? "Proposition AI chargee depuis le cache." : "Proposition AI prete pour validation.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGeneratingAI(false);
    }
  };

  const applyProductSuggestion = async () => {
    if (!editingId || !aiSuggestion) return;
    setError(""); setMessage(""); setApplyingAI(true);
    try {
      const result = await api<ProductAIApplyResponse>(
        `/api/admin/ai/products/${editingId}/apply`,
        {
          method: "POST",
          body: JSON.stringify({
            description: aiSuggestion.description,
            category: aiSuggestion.category,
            seo_title: aiSuggestion.seo_title,
            seo_description: aiSuggestion.seo_description,
            seo_keywords: aiSuggestion.seo_keywords,
            tags: aiSuggestion.tags,
          }),
        },
        true,
      );
      setEditingProduct(result.product);
      setProductForm((current) => ({
        ...current,
        description: result.product.description || "",
        category: result.product.category || "",
      }));
      setAiSuggestion(null);
      setMessage(
        result.indexed
          ? "Proposition AI appliquee et produit indexe dans Qdrant."
          : "Proposition AI appliquee. Indexation Qdrant a reessayer.",
      );
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setApplyingAI(false);
    }
  };

  const updateOrder = async (id: number, orderStatus: string) => {
    try { await api(`/api/admin/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ order_status: orderStatus }) }, true); setMessage("Statut de commande mis a jour."); await load(); }
    catch (err) { setError((err as Error).message); }
  };

  const updateStatus = async (id: number, isActive: boolean) => {
    try { await api(`/api/admin/users/${id}/status`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }, true); await load(); }
    catch (err) { setError((err as Error).message); }
  };

  const newSupport = () => { setEditingSupportId(null); setSupportForm(emptySupport); setTab("support-editor"); };
  const editSupport = (item: User) => { setEditingSupportId(item.id); setSupportForm({ full_name: item.full_name || "", email: item.email, password: "", is_active: item.is_active }); setTab("support-editor"); };
  const saveSupport = async (event: FormEvent) => {
    event.preventDefault(); setError(""); setMessage(""); setSavingSupport(true);
    try {
      if (editingSupportId) {
        const payload: Record<string, string> = { full_name: supportForm.full_name, email: supportForm.email };
        if (supportForm.password) payload.password = supportForm.password;
        await api(`/api/admin/support-users/${editingSupportId}`, { method: "PATCH", body: JSON.stringify(payload) }, true);
        await updateStatus(editingSupportId, supportForm.is_active);
        setMessage("Compte support mis a jour.");
      } else {
        await api("/api/admin/support-users", { method: "POST", body: JSON.stringify(supportForm) }, true);
        setMessage("Nouveau compte support cree.");
      }
      setEditingSupportId(null); setSupportForm(emptySupport); setTab("support-users"); await load();
    } catch (err) { setError((err as Error).message); }
    finally { setSavingSupport(false); }
  };

  const deleteSupport = async () => {
    if (!editingSupportId || !window.confirm("Supprimer ce compte support ? Son historique sera conserve.")) return;
    setError("");
    try {
      await api<void>(
        `/api/admin/support-users/${editingSupportId}`,
        { method: "DELETE" },
        true,
      );
      setMessage("Compte support supprime. Son historique a ete conserve.");
      setEditingSupportId(null);
      setSupportForm(emptySupport);
      setTab("support-users");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return <Protected admin><section className="admin-shell"><aside className="admin-sidebar"><p className="kicker">Administration</p><h1>Pilotage</h1>{[["dashboard", "Vue d'ensemble"], ["products", "Produits"], ["content", "Contenu AI"], ["marketing", "Marketing AI"], ["safety", "Safety AI"], ["orders", "Commandes"], ["messages", "Messages clients"], ["support-users", "Equipe support"], ["users", "Utilisateurs"], ["audit", "Historique"]].map(([value, label]) => <button key={value} className={tab === value || (value === "support-users" && tab === "support-editor") ? "active" : ""} onClick={() => setTab(value)}>{label}</button>)}</aside><div className="admin-content">{message && <div className="alert alert-success">{message}</div>}{error && <div className="alert alert-error">{error}</div>}

    {tab === "dashboard" && <><Title kicker="Aujourd'hui" title="Vue d'ensemble" />{dashboard ? <div className="stats-grid"><Stat label="Produits" value={dashboard.products} /><Stat label="Produits actifs" value={dashboard.active_products} /><Stat label="Stock faible" value={dashboard.low_stock_products} accent /><Stat label="Utilisateurs" value={dashboard.users} /><Stat label="Equipe support" value={supportUsers?.total || 0} /><Stat label="Commandes" value={dashboard.orders} /><Stat label="En attente" value={dashboard.pending_orders} accent /><Stat label="Revenu COD" value={money(dashboard.revenue_mad)} /></div> : <div className="page-loading">Chargement...</div>}</>}

    {tab === "products" && <><Title kicker="Catalogue" title="Produits" action={<button className="button button-small" onClick={() => { setEditingId(null); setProductForm(emptyProduct); setTab("product-editor"); }}>Ajouter un produit</button>} /><div className="data-table"><div className="table-row table-head"><span>Produit</span><span>Prix</span><span>Stock</span><span>Statut</span><span /></div>{products?.items.map((product) => <div className="table-row" key={product.product_id}><span><strong>{product.name}</strong><small>{product.brand}</small></span><span>{money(product.price || 0)}</span><span>{product.stock}</span><span><i className={product.is_active ? "dot active" : "dot"} />{product.is_active ? "Actif" : "Masque"}</span><span><button className="text-link" onClick={() => editProduct(product)}>Modifier</button></span></div>)}</div></>}

    {tab === "product-editor" && <><Title kicker="Catalogue" title={editingId ? `Modifier #${editingId}` : "Nouveau produit"} action={<button className="text-link" onClick={() => setTab("products")}>Retour</button>} /><form className="panel product-editor" onSubmit={saveProduct}><div className="form-grid"><label>Nom<input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} required /></label><label>Marque<input value={productForm.brand} onChange={(e) => setProductForm({ ...productForm, brand: e.target.value })} required /></label><label>Categorie<input value={productForm.category} onChange={(e) => setProductForm({ ...productForm, category: e.target.value })} /></label><label>Prix MAD<input type="number" step="0.01" min="0" value={productForm.price} onChange={(e) => setProductForm({ ...productForm, price: Number(e.target.value) })} required /></label><label>Stock<input type="number" min="0" value={productForm.stock} onChange={(e) => setProductForm({ ...productForm, stock: Number(e.target.value) })} required /></label><label className="check-filter"><input type="checkbox" checked={productForm.is_active} onChange={(e) => setProductForm({ ...productForm, is_active: e.target.checked })} /><span>Produit actif</span></label><label className="full-field">Description<textarea value={productForm.description} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} /></label>{editingId && <div className="full-field ai-product-actions"><button type="button" className="button button-ai" onClick={generateProductSuggestion} disabled={generatingAI || applyingAI}>{generatingAI ? "Product Agent travaille..." : "Optimiser avec Product Agent"}</button><small>L'AI prepare une proposition. Aucune information ne change sans ta validation.</small></div>}{aiSuggestion && <section className="full-field ai-product-panel"><div className="ai-product-heading"><div><span>PRODUCT AGENT</span><strong>Proposition a valider</strong></div><small>{aiSuggestion.model}{aiSuggestion.cached ? " · cache" : ""}</small></div><div className="form-grid"><label>Categorie proposee<input value={aiSuggestion.category} onChange={(e) => setAiSuggestion((current) => current ? { ...current, category: e.target.value } : current)} /></label><label>Titre SEO<input value={aiSuggestion.seo_title} maxLength={70} onChange={(e) => setAiSuggestion((current) => current ? { ...current, seo_title: e.target.value } : current)} /></label><label className="full-field">Description produit<textarea value={aiSuggestion.description} maxLength={1500} onChange={(e) => setAiSuggestion((current) => current ? { ...current, description: e.target.value } : current)} /></label><label className="full-field">Description SEO<textarea value={aiSuggestion.seo_description} maxLength={180} onChange={(e) => setAiSuggestion((current) => current ? { ...current, seo_description: e.target.value } : current)} /></label><label>Mots-cles SEO<input value={aiSuggestion.seo_keywords.join(", ")} onChange={(e) => setAiSuggestion((current) => current ? { ...current, seo_keywords: splitTerms(e.target.value) } : current)} /></label><label>Tags<input value={aiSuggestion.tags.join(", ")} onChange={(e) => setAiSuggestion((current) => current ? { ...current, tags: splitTerms(e.target.value) } : current)} /></label></div><div className="ai-review-actions"><button type="button" className="button" onClick={applyProductSuggestion} disabled={applyingAI}>{applyingAI ? "Application..." : "Valider et appliquer"}</button><button type="button" className="text-link" onClick={() => setAiSuggestion(null)} disabled={applyingAI}>Ignorer</button></div></section>}{editingId && <label className="full-field">Ajouter une photo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={uploadImage} /></label>}{editingProduct && editingId && <div className="full-field"><strong>Photos actuelles</strong><ProductImageManager product={editingProduct} onChange={setEditingProduct} onError={setError} /></div>}</div><div className="editor-actions"><button className="button">Enregistrer</button>{editingId && <button type="button" className="button button-danger" onClick={deleteProduct}>Supprimer</button>}</div></form></>}

    {tab === "content" && <ContentAgentWorkspace />}

    {tab === "marketing" && <MarketingAgentWorkspace />}

    {tab === "safety" && <SafetyAgentWorkspace />}

    {tab === "orders" && <><Title kicker="Operations" title="Commandes" />{!orders?.items.length ? <div className="empty-state"><h3>Aucune commande</h3></div> : <div className="data-table orders-table"><div className="table-row table-head"><span>No</span><span>Client</span><span>Total</span><span>Paiement</span><span>Statut</span></div>{orders.items.map((order) => <div className="table-row" key={order.id}><span>#{order.id}</span><span><strong>{order.full_name}</strong><small>{order.city} - {order.phone}</small></span><span>{money(order.total)}</span><span>{order.payment_status}</span><span><select value={order.order_status} onChange={(e) => updateOrder(order.id, e.target.value)}>{orderStatuses.map((status) => <option key={status}>{status}</option>)}</select></span></div>)}</div>}</>}

    {tab === "messages" && <AdminTicketWorkspace initialTicketId={Number.isInteger(requestedTicketId) && requestedTicketId > 0 ? requestedTicketId : null} />}

    {tab === "support-users" && <><Title kicker="Acces support" title="Equipe support" action={<button className="button button-small" onClick={newSupport}>Ajouter un support</button>} />{!supportUsers?.items.length ? <div className="empty-state"><h3>Aucun compte support</h3><button className="button" onClick={newSupport}>Creer le premier compte</button></div> : <div className="support-account-grid">{supportUsers.items.map((item) => <article className="support-account-card" key={item.id}><div className="support-avatar">{(item.full_name || item.email).slice(0, 2).toUpperCase()}</div><div><strong>{item.full_name || "Support"}</strong><small>{item.email}</small><span className={`account-state ${item.is_active ? "active" : ""}`}>{item.is_active ? "Actif" : "Desactive"}</span></div><div className="support-account-actions"><button className="text-link" onClick={() => editSupport(item)}>Modifier</button><button className={`status-toggle ${item.is_active ? "on" : ""}`} onClick={() => updateStatus(item.id, !item.is_active)}>{item.is_active ? "Desactiver" : "Activer"}</button></div></article>)}</div>}</>}

    {tab === "support-editor" && <><Title kicker="Equipe support" title={editingSupportId ? "Modifier le compte" : "Nouveau compte support"} action={<button className="text-link" onClick={() => setTab("support-users")}>Retour</button>} /><form className="panel support-editor" onSubmit={saveSupport}><div className="form-grid"><label>Nom complet<input value={supportForm.full_name} onChange={(e) => setSupportForm({ ...supportForm, full_name: e.target.value })} required minLength={2} /></label><label>Email<input type="email" value={supportForm.email} onChange={(e) => setSupportForm({ ...supportForm, email: e.target.value })} required /></label><label className="full-field">{editingSupportId ? "Nouveau mot de passe (optionnel)" : "Mot de passe"}<input type="password" value={supportForm.password} onChange={(e) => setSupportForm({ ...supportForm, password: e.target.value })} required={!editingSupportId} minLength={8} /></label><label className="check-filter full-field"><input type="checkbox" checked={supportForm.is_active} onChange={(e) => setSupportForm({ ...supportForm, is_active: e.target.checked })} /><span>Compte actif</span></label></div><div className="support-permissions"><strong>Permissions du support</strong><p>Voir et suivre les commandes, repondre aux demandes clients, gerer leur statut et modifier les informations, le stock et les photos des produits. Aucun acces aux roles, comptes admin, creation ou suppression de produits.</p></div><div className="editor-actions"><button className="button" disabled={savingSupport}>{savingSupport ? "Creation en cours..." : editingSupportId ? "Enregistrer" : "Creer le compte"}</button>{editingSupportId && <button type="button" className="button button-danger" onClick={deleteSupport}>Supprimer le compte</button>}</div></form></>}

    {tab === "users" && <><Title kicker="Acces" title="Utilisateurs" /><div className="data-table users-table"><div className="table-row table-head"><span>Utilisateur</span><span>Role</span><span>Compte</span></div>{users?.items.map((item) => <div className="table-row" key={item.id}><span><strong>{item.full_name || "Sans nom"}</strong><small>{item.email}</small></span><span><span className={`role-badge role-${item.role}`}>{item.role}</span></span><span><button disabled={item.id === user?.id} className={`status-toggle ${item.is_active ? "on" : ""}`} onClick={() => updateStatus(item.id, !item.is_active)}>{item.is_active ? "Actif" : "Desactive"}</button></span></div>)}</div></>}

    {tab === "audit" && <><Title kicker="Securite et tracabilite" title="Historique des actions" action={<span className="muted">{auditLogs?.total || 0} action(s)</span>} />{!auditLogs?.items.length ? <div className="empty-state"><h3>Aucune action enregistree</h3></div> : <div className="data-table audit-table"><div className="table-row table-head"><span>Date</span><span>Admin / acteur</span><span>Action</span><span>Element</span><span>Details</span></div>{auditLogs.items.map((item) => <div className="table-row" key={item.id}><span><strong>{new Date(item.created_at).toLocaleDateString("fr-MA")}</strong><small>{new Date(item.created_at).toLocaleTimeString("fr-MA")}</small></span><span><strong>{item.actor_email || "Systeme"}</strong><small>{item.actor_role}</small></span><span><code>{item.action}</code></span><span><strong>{item.entity_type}</strong><small>{item.entity_id ? `#${item.entity_id}` : "-"}</small></span><span><AuditDetails value={item.details} /></span></div>)}</div>}</>}
  </div></section></Protected>;
}

function Title({ kicker, title, action }: { kicker: string; title: string; action?: React.ReactNode }) { return <div className="page-title"><div><p className="kicker">{kicker}</p><h2>{title}</h2></div>{action}</div>; }
function splitTerms(value: string): string[] { return value.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 12); }
function AuditDetails({ value }: { value: string | null }) {
  if (!value) return <small>Aucun detail</small>;
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return <small title={JSON.stringify(parsed, null, 2)}>{Object.entries(parsed).map(([key, item]) => `${key}: ${typeof item === "object" ? JSON.stringify(item) : String(item)}`).join(" | ")}</small>;
  } catch {
    return <small>{value}</small>;
  }
}
