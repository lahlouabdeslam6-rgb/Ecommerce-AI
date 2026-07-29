"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthProvider";
import { api, money } from "../lib/api";
import { getGuestOrderReceipts } from "../lib/guest-orders";
import type { Order, PaginatedOrders } from "../types";

const statusLabels: Record<string, string> = {
  pending: "En attente de confirmation",
  confirmed: "Confirmée",
  preparing: "En préparation",
  shipped: "Expédiée",
  delivered: "Livrée",
  cancelled: "Annulée",
  delivery_failed: "Livraison échouée",
};

export default function OrdersPage() {
  const search = useSearchParams();
  const { user, loading } = useAuth();
  const [orders, setOrders] = useState<PaginatedOrders | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    if (loading) return;
    setError("");
    setRefreshing(true);
    try {
      if (user) {
        setOrders(await api<PaginatedOrders>("/api/orders", {}, true));
        return;
      }

      const receipts = getGuestOrderReceipts();
      const tracked = await Promise.allSettled(
        receipts.map((receipt) =>
          api<Order>("/api/orders/guest-track", {
            method: "POST",
            body: JSON.stringify(receipt),
          }),
        ),
      );
      const items: Order[] = [];
      tracked.forEach((result) => {
        if (result.status === "fulfilled") {
          items.push(result.value);
        }
      });
      if (receipts.length && !items.length) {
        throw new Error(
          "Impossible d'actualiser vos commandes. Veuillez réessayer.",
        );
      }
      items.sort(
        (left, right) =>
          new Date(right.created_at).getTime() -
          new Date(left.created_at).getTime(),
      );
      setOrders({
        items,
        total: items.length,
        page: 1,
        page_size: items.length,
        total_pages: items.length ? 1 : 0,
      });
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [loading, user]);

  const cancel = async (id: number) => {
    if (!user || !window.confirm("Annuler cette commande ?")) return;
    try {
      await api<Order>(
        `/api/orders/${id}/cancel`,
        { method: "POST" },
        true,
      );
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  return (
    <section className="shell page-section">
      <div className="page-title">
        <div>
          <p className="kicker">Historique et suivi</p>
          <h1>Mes commandes</h1>
        </div>
        {!user && orders?.items.length ? (
          <button
            className="button button-small button-outline"
            onClick={() => void load()}
            disabled={refreshing}
          >
            {refreshing ? "Actualisation..." : "Actualiser les statuts"}
          </button>
        ) : null}
      </div>

      {search.get("created") && (
        <div className="alert alert-success">
          Commande #{search.get("created")} enregistrée. Votre panier a été
          vidé et notre équipe admin ou support va vous appeler pour confirmer
          la livraison.
        </div>
      )}
      {!user && (
        <div className="guest-orders-note">
          <strong>Suivi sans compte</strong>
          <span>
            Vos commandes restent disponibles sur ce navigateur. Créer un
            compte reste facultatif.
          </span>
        </div>
      )}
      {error && <div className="alert alert-error">{error}</div>}

      {!orders ? (
        <div className="page-loading">Chargement...</div>
      ) : !orders.items.length ? (
        <div className="empty-state">
          <h2>Aucune commande</h2>
          <p>Vos prochaines commandes apparaîtront ici après confirmation.</p>
          <Link href="/" className="button">
            Voir les produits
          </Link>
        </div>
      ) : (
        <div className="orders-list">
          {orders.items.map((order) => (
            <article className="order-card" key={order.id}>
              <div className="order-card-head">
                <div>
                  <p className="eyebrow">Commande #{order.id}</p>
                  <strong>
                    {new Date(order.created_at).toLocaleDateString("fr-MA")}
                  </strong>
                </div>
                <span
                  className={`status status-${order.order_status}`}
                >
                  {statusLabels[order.order_status] || order.order_status}
                </span>
              </div>
              <div className="order-delivery-summary">
                <span>
                  <small>Livraison</small>
                  <strong>{order.city}</strong>
                </span>
                <span>
                  <small>Téléphone</small>
                  <strong>{order.phone}</strong>
                </span>
                <span>
                  <small>Adresse</small>
                  <strong>{order.address}</strong>
                </span>
              </div>
              <div className="order-lines">
                {order.items.map((item) => (
                  <div key={item.product_id}>
                    <span>
                      {item.quantity} × {item.product_name}
                    </span>
                    <strong>{money(item.subtotal)}</strong>
                  </div>
                ))}
              </div>
              <div className="order-card-foot">
                <div>
                  <small>Paiement</small>
                  <strong>
                    {order.payment_status === "paid"
                      ? "Payé"
                      : order.payment_status === "cancelled"
                        ? "Annulé"
                        : "À la livraison"}
                  </strong>
                </div>
                <div>
                  <small>Total</small>
                  <strong>{money(order.total, order.currency)}</strong>
                </div>
                {user &&
                  ["pending", "confirmed"].includes(order.order_status) && (
                    <button
                      className="button button-outline button-small"
                      onClick={() => void cancel(order.id)}
                    >
                      Annuler
                    </button>
                  )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
