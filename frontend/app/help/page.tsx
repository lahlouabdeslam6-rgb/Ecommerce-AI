"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Protected } from "../components/Protected";
import { api } from "../lib/api";
import type { PaginatedOrders, SupportTicket, TicketList } from "../types";

const statusLabels: Record<string, string> = {
  open: "Ouverte",
  in_progress: "En traitement",
  resolved: "Resolue",
  closed: "Fermee",
};

export default function HelpPage() {
  const searchParams = useSearchParams();
  const requestedTicketId = Number(searchParams.get("ticket"));
  const [tickets, setTickets] = useState<TicketList | null>(null);
  const [orders, setOrders] = useState<PaginatedOrders | null>(null);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [form, setForm] = useState({ subject: "", category: "general", order_id: "", message: "" });
  const [reply, setReply] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [loadedTickets, orderData] = await Promise.all([
        api<TicketList>("/api/tickets", {}, true),
        api<PaginatedOrders>("/api/orders?page_size=50", {}, true),
      ]);
      let ticketData = loadedTickets;
      if (
        Number.isInteger(requestedTicketId) &&
        requestedTicketId > 0 &&
        !loadedTickets.items.some((item) => item.id === requestedTicketId)
      ) {
        const requestedTicket = await api<SupportTicket>(
          `/api/tickets/${requestedTicketId}`,
          {},
          true,
        );
        ticketData = {
          ...loadedTickets,
          items: [requestedTicket, ...loadedTickets.items],
        };
      }
      setTickets(ticketData);
      setOrders(orderData);
      const ticketToSelect = requestedTicketId || selected?.id;
      if (ticketToSelect) {
        setSelected(
          ticketData.items.find((item) => item.id === ticketToSelect) || null,
        );
      }
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => { void load(); }, [requestedTicketId]);

  const createTicket = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const ticket = await api<SupportTicket>("/api/tickets", {
        method: "POST",
        body: JSON.stringify({
          subject: form.subject,
          category: form.category,
          message: form.message,
          order_id: form.order_id ? Number(form.order_id) : null,
        }),
      }, true);
      setForm({ subject: "", category: "general", order_id: "", message: "" });
      setSelected(ticket);
      setMessage("Votre demande a ete envoyee au support.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const sendReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    try {
      const ticket = await api<SupportTicket>(`/api/tickets/${selected.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ message: reply }),
      }, true);
      setReply("");
      setSelected(ticket);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Protected roles={["customer"]}>
      <section className="shell page-section">
        <div className="page-title">
          <div><p className="kicker">Service client</p><h1>Centre d&apos;aide</h1></div>
        </div>
        {message && <div className="alert alert-success">{message}</div>}
        {error && <div className="alert alert-error">{error}</div>}
        <div className="help-layout">
          <form className="panel stack-form" onSubmit={createTicket}>
            <h2>Nouvelle demande</h2>
            <label>Sujet<input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required minLength={3} /></label>
            <label>Categorie<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}><option value="general">Question generale</option><option value="order">Commande</option><option value="delivery">Livraison</option><option value="payment">Paiement</option><option value="product">Produit</option><option value="return">Retour</option></select></label>
            <label>Commande concernee<select value={form.order_id} onChange={(e) => setForm({ ...form, order_id: e.target.value })}><option value="">Aucune</option>{orders?.items.map((order) => <option key={order.id} value={order.id}>Commande #{order.id}</option>)}</select></label>
            <label>Message<textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} required minLength={3} /></label>
            <button className="button">Envoyer au support</button>
          </form>
          <div className="ticket-workspace">
            <div className="ticket-list panel">
              <h2>Mes demandes</h2>
              {!tickets?.items.length ? <p className="muted">Aucune demande pour le moment.</p> : tickets.items.map((ticket) => <button key={ticket.id} className={`ticket-list-item ${selected?.id === ticket.id ? "active" : ""}`} onClick={() => setSelected(ticket)}><span><strong>#{ticket.id} {ticket.subject}</strong><small>{new Date(ticket.updated_at).toLocaleDateString("fr-MA")}</small></span><i className={`ticket-status ticket-${ticket.status}`}>{statusLabels[ticket.status]}</i></button>)}
            </div>
            {selected && <TicketConversation ticket={selected} reply={reply} setReply={setReply} submit={sendReply} />}
          </div>
        </div>
      </section>
    </Protected>
  );
}

function TicketConversation({ ticket, reply, setReply, submit }: { ticket: SupportTicket; reply: string; setReply: (value: string) => void; submit: (event: FormEvent) => void }) {
  return <div className="panel ticket-conversation"><div className="ticket-conversation-head"><div><p className="kicker">Demande #{ticket.id}</p><h2>{ticket.subject}</h2></div><span className={`ticket-status ticket-${ticket.status}`}>{statusLabels[ticket.status]}</span></div><div className="message-thread">{ticket.messages.map((item) => <article key={item.id} className={`support-message ${item.sender_role !== "customer" ? "staff" : "customer"}`}><div><strong>{item.sender_name}</strong><small>{new Date(item.created_at).toLocaleString("fr-MA")}</small></div><p>{item.message}</p></article>)}</div><form className="reply-form" onSubmit={submit}><textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Ecrire une reponse..." required /><button className="button button-small">Envoyer</button></form></div>;
}
