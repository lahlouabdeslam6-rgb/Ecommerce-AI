"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Protected } from "../components/Protected";
import { StatCard as Stat } from "../components/StatCard";
import { api, money } from "../lib/api";
import type { PaginatedOrders, ProductList, SupportTicket, TicketList } from "../types";
import { DeliveryAgentWorkspace } from "../admin/DeliveryAgentWorkspace";
import { OrderVerificationWorkspace } from "../components/OrderVerificationWorkspace";

type SupportDashboard = { orders: number; pending_orders: number; delivered_orders: number; open_tickets: number; in_progress_tickets: number };
const orderStatuses = ["pending", "confirmed", "preparing", "shipped", "delivered", "delivery_failed", "cancelled"];
const ticketStatuses = ["open", "in_progress", "resolved", "closed"];
const priorities = ["low", "normal", "high", "urgent"];

export default function SupportPage() {
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const requestedTicketId = Number(searchParams.get("ticket"));
  const [tab, setTab] = useState<"dashboard" | "operations" | "products">("dashboard");
  const [dashboard, setDashboard] = useState<SupportDashboard | null>(null);
  const [tickets, setTickets] = useState<TicketList | null>(null);
  const [orders, setOrders] = useState<PaginatedOrders | null>(null);
  const [products, setProducts] = useState<ProductList | null>(null);
  const [productPage, setProductPage] = useState(1);
  const [productSearch, setProductSearch] = useState("");
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [reply, setReply] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (requestedTab === "orders" || requestedTab === "tickets" || requestedTab === "operations") {
      setTab("operations");
    } else if (requestedTab === "products") {
      setTab("products");
    }
  }, [requestedTab]);

  useEffect(() => {
    if (!Number.isInteger(requestedTicketId) || requestedTicketId < 1) return;
    const ticket = tickets?.items.find((item) => item.id === requestedTicketId);
    if (ticket) setSelected(ticket);
  }, [requestedTicketId, tickets]);

  const load = async () => {
    try {
      const [dashboardData, ticketData, orderData, productData] = await Promise.all([
        api<SupportDashboard>("/api/support/dashboard", {}, true),
        api<TicketList>("/api/support/tickets?page_size=50", {}, true),
        api<PaginatedOrders>("/api/support/orders?page_size=50", {}, true),
        api<ProductList>(
          `/api/products/manage?page=${productPage}&page_size=50${
            productSearch.trim()
              ? `&search=${encodeURIComponent(productSearch.trim())}`
              : ""
          }`,
          {},
          true,
        ),
      ]);
      setDashboard(dashboardData);
      setTickets(ticketData);
      setOrders(orderData);
      setProducts(productData);
      if (selected) setSelected(ticketData.items.find((item) => item.id === selected.id) || null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => { void load(); }, [productPage]);

  const searchProducts = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setProductPage(1);
    try {
      setProducts(
        await api<ProductList>(
          `/api/products/manage?page=1&page_size=50${
            productSearch.trim()
              ? `&search=${encodeURIComponent(productSearch.trim())}`
              : ""
          }`,
          {},
          true,
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const clearProductSearch = async () => {
    setProductSearch("");
    setProductPage(1);
    setError("");
    try {
      setProducts(
        await api<ProductList>(
          "/api/products/manage?page=1&page_size=50",
          {},
          true,
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const updateOrder = async (id: number, orderStatus: string) => {
    try {
      await api(`/api/support/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ order_status: orderStatus }) }, true);
      setMessage("Statut de la commande mis a jour.");
      await load();
    } catch (err) { setError((err as Error).message); }
  };

  const updateTicket = async (id: number, field: "status" | "priority", value: string) => {
    try {
      const ticket = await api<SupportTicket>(`/api/support/tickets/${id}/${field}`, { method: "PATCH", body: JSON.stringify({ [field]: value }) }, true);
      setSelected(ticket);
      await load();
    } catch (err) { setError((err as Error).message); }
  };

  const sendReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    try {
      const ticket = await api<SupportTicket>(`/api/support/tickets/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ message: reply }) }, true);
      setReply("");
      setSelected(ticket);
      setMessage("Reponse envoyee au client.");
      await load();
    } catch (err) { setError((err as Error).message); }
  };

  return <Protected roles={["support", "admin"]}><section className="admin-shell support-shell"><aside className="admin-sidebar"><p className="kicker">NUTRIFIT Care</p><h1>Support</h1><button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>Vue d&apos;ensemble</button><button className={tab === "operations" ? "active" : ""} onClick={() => setTab("operations")}>Support &amp; livraison</button><button className={tab === "products" ? "active" : ""} onClick={() => setTab("products")}>Produits</button></aside><div className="admin-content">{message && <div className="alert alert-success">{message}</div>}{error && <div className="alert alert-error">{error}</div>}
    {tab === "dashboard" && <><div className="page-title"><div><p className="kicker">Activite support</p><h2>Vue d&apos;ensemble</h2></div></div>{dashboard ? <div className="stats-grid support-stats"><Stat label="Demandes ouvertes" value={dashboard.open_tickets} accent /><Stat label="En traitement" value={dashboard.in_progress_tickets} /><Stat label="Commandes" value={dashboard.orders} /><Stat label="Commandes en attente" value={dashboard.pending_orders} accent /><Stat label="Commandes livrees" value={dashboard.delivered_orders} /></div> : <div className="page-loading">Chargement...</div>}</>}
    {tab === "operations" && <><OrderVerificationWorkspace /><DeliveryAgentWorkspace allowNotifications={false} /><div className="page-title"><div><p className="kicker">Service client</p><h2>Demandes clients</h2></div></div><div className="support-ticket-layout"><div className="ticket-list panel">{!tickets?.items.length ? <p className="muted">Aucune demande.</p> : tickets.items.map((ticket) => <button key={ticket.id} className={`ticket-list-item ${selected?.id === ticket.id ? "active" : ""}`} onClick={() => setSelected(ticket)}><span><strong>#{ticket.id} {ticket.subject}</strong><small>{ticket.customer_name} - {ticket.customer_email}</small></span><i className={`ticket-priority priority-${ticket.priority}`}>{ticket.priority}</i></button>)}</div>{selected ? <div className="panel ticket-conversation"><div className="ticket-conversation-head"><div><p className="kicker">Client #{selected.user_id}</p><h2>{selected.subject}</h2><p className="muted">{selected.customer_name} - {selected.customer_email}{selected.order_id ? ` - Commande #${selected.order_id}` : ""}</p></div><div className="ticket-controls"><label>Priorite<select value={selected.priority} onChange={(e) => updateTicket(selected.id, "priority", e.target.value)}>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Statut<select value={selected.status} onChange={(e) => updateTicket(selected.id, "status", e.target.value)}>{ticketStatuses.map((item) => <option key={item}>{item}</option>)}</select></label></div></div><div className="message-thread">{selected.messages.map((item) => <article key={item.id} className={`support-message ${item.sender_role === "customer" ? "customer" : "staff"}`}><div><strong>{item.sender_name}</strong><small>{new Date(item.created_at).toLocaleString("fr-MA")}</small></div><p>{item.message}</p></article>)}</div><form className="reply-form" onSubmit={sendReply}><textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Repondre au client..." required /><button className="button button-small">Envoyer</button></form></div> : <div className="empty-state"><h3>Choisissez une demande</h3></div>}</div><div className="page-title"><div><p className="kicker">Suivi client</p><h2>Commandes</h2></div></div>{!orders?.items.length ? <div className="empty-state"><h3>Aucune commande</h3></div> : <div className="data-table orders-table"><div className="table-row table-head"><span>No</span><span>Client</span><span>Total</span><span>Paiement</span><span>Statut</span></div>{orders.items.map((order) => <div className="table-row" key={order.id}><span>#{order.id}</span><span><strong>{order.full_name}</strong><small>{order.city} - {order.phone}<br />{order.address}</small></span><span>{money(order.total)}</span><span>{order.payment_status}</span><span><select value={order.order_status} onChange={(e) => updateOrder(order.id, e.target.value)}>{orderStatuses.map((item) => <option key={item}>{item}</option>)}</select></span></div>)}</div>}</>}
    {tab === "products" && <><div className="page-title"><div><p className="kicker">Catalogue</p><h2>Modifier les produits</h2></div><span className="muted">{products?.total || 0} produits</span></div><form className="panel admin-search-bar" onSubmit={searchProducts}><label>Rechercher un produit<input value={productSearch} onChange={(event) => setProductSearch(event.target.value)} placeholder="Nom ou marque du produit" /></label><button className="button button-small">Rechercher</button>{productSearch && <button type="button" className="text-link" onClick={() => void clearProductSearch()}>Effacer</button>}</form>{!products?.items.length ? <div className="empty-state"><h3>Aucun produit trouvé</h3></div> : <><div className="data-table"><div className="table-row table-head"><span>Produit</span><span>Prix</span><span>Stock</span><span>Statut</span><span /></div>{products.items.map((product) => <div className="table-row" key={product.product_id}><span><strong>{product.name}</strong><small>{product.brand}</small></span><span>{money(product.price || 0, product.currency)}</span><span>{product.stock}</span><span><i className={product.is_active ? "dot active" : "dot"} />{product.is_active ? "Actif" : "Masque"}</span><span><Link className="text-link" href={`/support/products/${product.product_id}`}>Modifier</Link></span></div>)}</div>{products.total_pages > 1 && <div className="pagination"><button disabled={productPage === 1} onClick={() => setProductPage((page) => page - 1)}>Precedent</button><span>Page {productPage} sur {products.total_pages}</span><button disabled={productPage === products.total_pages} onClick={() => setProductPage((page) => page + 1)}>Suivant</button></div>}</>}</>}
  </div></section></Protected>;
}
