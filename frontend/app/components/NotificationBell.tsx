"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "./AuthProvider";
import { api } from "../lib/api";

type Notification = {
  id: number;
  notification_type: string;
  title: string;
  message: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
};

export function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);

  const load = () =>
    api<{ items: Notification[]; unread: number }>("/api/notifications", {}, true)
      .then((data) => {
        setItems(data.items);
        setUnread(data.unread);
      })
      .catch(() => undefined);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const markRead = async (item: Notification) => {
    if (!item.is_read) {
      await api<void>(`/api/notifications/${item.id}/read`, { method: "PATCH" }, true);
      setItems((current) =>
        current.map((value) =>
          value.id === item.id ? { ...value, is_read: true } : value,
        ),
      );
      setUnread((value) => Math.max(0, value - 1));
    }
    setOpen(false);
  };

  const notificationLink = (item: Notification) => {
    const parameters = new URLSearchParams(item.link?.split("?")[1] || "");
    const orderId = parameters.get("order");
    const ticketId = parameters.get("ticket");

    if (orderId) {
      if (user?.role === "admin") {
        return `/admin?tab=orders&order=${orderId}`;
      }
      if (user?.role === "support") {
        return `/support?tab=orders&order=${orderId}`;
      }
      return `/orders?order=${orderId}`;
    }

    if (ticketId) {
      if (user?.role === "admin") {
        return `/admin?tab=support-delivery&ticket=${ticketId}`;
      }
      if (user?.role === "support") {
        return `/support?tab=operations&ticket=${ticketId}`;
      }
      return `/help?ticket=${ticketId}`;
    }

    if (item.link) return item.link;
    if (user?.role === "admin") return "/admin";
    if (user?.role === "support") return "/support";
    return "/account";
  };

  return (
    <div className="notification-center">
      <button
        className="notification-button"
        type="button"
        aria-label="Notifications"
        onClick={() => setOpen((value) => !value)}
      >
        <svg
          className="notification-bell-icon"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M10 21h4"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
        {unread > 0 && <strong>{unread > 9 ? "9+" : unread}</strong>}
      </button>
      {open && (
        <div className="notification-menu">
          <div><b>Notifications</b><small>{unread} non lue(s)</small></div>
          {items.length === 0 ? (
            <p>Aucune notification.</p>
          ) : (
            items.slice(0, 8).map((item) => {
              const link = notificationLink(item);
              return (
                <Link
                  href={link}
                  key={item.id}
                  className={item.is_read ? "" : "unread"}
                  onClick={() => void markRead(item)}
                >
                  <b>{item.title}</b><span>{item.message}</span>
                </Link>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
