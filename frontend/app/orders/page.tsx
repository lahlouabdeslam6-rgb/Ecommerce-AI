"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Protected } from "../components/Protected";
import { api, money } from "../lib/api";
import type { Order, PaginatedOrders } from "../types";

const statusLabels: Record<string, string> = { pending: "En attente", confirmed: "Confirmée", preparing: "En préparation", shipped: "Expédiée", delivered: "Livrée", cancelled: "Annulée", delivery_failed: "Livraison échouée" };

export default function OrdersPage() {
  const search = useSearchParams(); const [orders, setOrders] = useState<PaginatedOrders | null>(null); const [error, setError] = useState("");
  const load = () => api<PaginatedOrders>("/api/orders", {}, true).then(setOrders).catch((e: Error) => setError(e.message));
  useEffect(() => {
    void load();
  }, []);
  const cancel = async (id: number) => { if (!window.confirm("Annuler cette commande ?")) return; try { await api<Order>(`/api/orders/${id}/cancel`, { method: "POST" }, true); load(); } catch (e) { setError((e as Error).message); } };
  return <Protected><section className="shell page-section"><div className="page-title"><div><p className="kicker">Historique</p><h1>Mes commandes</h1></div></div>{search.get("created") && <div className="alert alert-success">Commande #{search.get("created")} confirmée. Nous vous contacterons pour la livraison.</div>}{error && <div className="alert alert-error">{error}</div>}{!orders ? <div className="page-loading">Chargement…</div> : !orders.items.length ? <div className="empty-state"><h2>Aucune commande</h2><p>Vos prochaines commandes apparaîtront ici.</p></div> : <div className="orders-list">{orders.items.map((order) => <article className="order-card" key={order.id}><div className="order-card-head"><div><p className="eyebrow">Commande #{order.id}</p><strong>{new Date(order.created_at).toLocaleDateString("fr-MA")}</strong></div><span className={`status status-${order.order_status}`}>{statusLabels[order.order_status] || order.order_status}</span></div><div className="order-lines">{order.items.map((item) => <div key={item.product_id}><span>{item.quantity} × {item.product_name}</span><strong>{money(item.subtotal)}</strong></div>)}</div><div className="order-card-foot"><div><small>Paiement</small><strong>{order.payment_status === "paid" ? "Payé" : order.payment_status === "cancelled" ? "Annulé" : "À la livraison"}</strong></div><div><small>Total</small><strong>{money(order.total, order.currency)}</strong></div>{["pending", "confirmed"].includes(order.order_status) && <button className="button button-outline button-small" onClick={() => cancel(order.id)}>Annuler</button>}</div></article>)}</div>}</section></Protected>;
}
