"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { SupportTicket, TicketList } from "../types";

const ticketStatuses = ["open", "in_progress", "resolved", "closed"];
const priorities = ["low", "normal", "high", "urgent"];

export function AdminTicketWorkspace({
  initialTicketId,
}: {
  initialTicketId: number | null;
}) {
  const [tickets, setTickets] = useState<TicketList | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(initialTicketId);
  const [reply, setReply] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  const selected = useMemo(
    () => tickets?.items.find((ticket) => ticket.id === selectedId) || null,
    [tickets, selectedId],
  );

  const load = async () => {
    try {
      let result = await api<TicketList>(
        "/api/support/tickets?page_size=100",
        {},
        true,
      );
      if (
        initialTicketId &&
        !result.items.some((ticket) => ticket.id === initialTicketId)
      ) {
        const requestedTicket = await api<SupportTicket>(
          `/api/support/tickets/${initialTicketId}`,
          {},
          true,
        );
        result = { ...result, items: [requestedTicket, ...result.items] };
      }
      setTickets(result);
      setSelectedId((current) => {
        if (
          current &&
          result.items.some((ticket) => ticket.id === current)
        ) {
          return current;
        }
        return result.items[0]?.id || null;
      });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, [initialTicketId]);

  useEffect(() => {
    if (initialTicketId) setSelectedId(initialTicketId);
  }, [initialTicketId]);

  const replaceTicket = (ticket: SupportTicket) => {
    setTickets((current) => current ? {
      ...current,
      items: current.items.map((item) =>
        item.id === ticket.id ? ticket : item
      ),
    } : current);
  };

  const updateTicket = async (
    field: "status" | "priority",
    value: string,
  ) => {
    if (!selected) return;
    setError("");
    setMessage("");
    try {
      const ticket = await api<SupportTicket>(
        `/api/support/tickets/${selected.id}/${field}`,
        {
          method: "PATCH",
          body: JSON.stringify({ [field]: value }),
        },
        true,
      );
      replaceTicket(ticket);
      setMessage("Demande mise a jour.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const sendReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setSending(true);
    setError("");
    setMessage("");
    try {
      const ticket = await api<SupportTicket>(
        `/api/support/tickets/${selected.id}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ message: reply.trim() }),
        },
        true,
      );
      replaceTicket(ticket);
      setReply("");
      setMessage("Reponse admin envoyee au client.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <div className="page-title">
        <div>
          <p className="kicker">Service client</p>
          <h2>Messages clients</h2>
        </div>
        <span className="muted">{tickets?.total || 0} demande(s)</span>
      </div>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}
      <div className="support-ticket-layout">
        <div className="ticket-list panel">
          {!tickets?.items.length ? (
            <p className="muted">Aucune demande client.</p>
          ) : tickets.items.map((ticket) => (
            <button
              key={ticket.id}
              className={`ticket-list-item ${
                selected?.id === ticket.id ? "active" : ""
              }`}
              onClick={() => setSelectedId(ticket.id)}
              type="button"
            >
              <span>
                <strong>#{ticket.id} {ticket.subject}</strong>
                <small>{ticket.customer_name} - {ticket.customer_email}</small>
              </span>
              <i className={`ticket-priority priority-${ticket.priority}`}>
                {ticket.priority}
              </i>
            </button>
          ))}
        </div>
        {selected ? (
          <div className="panel ticket-conversation">
            <div className="ticket-conversation-head">
              <div>
                <p className="kicker">Client #{selected.user_id}</p>
                <h2>{selected.subject}</h2>
                <p className="muted">
                  {selected.customer_name} - {selected.customer_email}
                  {selected.order_id
                    ? ` - Commande #${selected.order_id}`
                    : ""}
                </p>
              </div>
              <div className="ticket-controls">
                <label>
                  Priorite
                  <select
                    value={selected.priority}
                    onChange={(event) =>
                      updateTicket("priority", event.target.value)
                    }
                  >
                    {priorities.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Statut
                  <select
                    value={selected.status}
                    onChange={(event) =>
                      updateTicket("status", event.target.value)
                    }
                  >
                    {ticketStatuses.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            <div className="message-thread">
              {selected.messages.map((item) => (
                <article
                  key={item.id}
                  className={`support-message ${
                    item.sender_role === "customer" ? "customer" : "staff"
                  }`}
                >
                  <div>
                    <strong>{item.sender_name}</strong>
                    <small>
                      {new Date(item.created_at).toLocaleString("fr-MA")}
                    </small>
                  </div>
                  <p>{item.message}</p>
                </article>
              ))}
            </div>
            <form className="reply-form" onSubmit={sendReply}>
              <textarea
                value={reply}
                onChange={(event) => setReply(event.target.value)}
                placeholder="Repondre au client en tant qu'admin..."
                required
              />
              <button
                className="button button-small"
                disabled={sending}
              >
                {sending ? "Envoi..." : "Envoyer"}
              </button>
            </form>
          </div>
        ) : (
          <div className="empty-state">
            <h3>Choisissez une demande</h3>
          </div>
        )}
      </div>
    </>
  );
}
