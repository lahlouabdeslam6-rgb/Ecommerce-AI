"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, money } from "../lib/api";
import { getGuestCart } from "../lib/guest-cart";
import type { Cart, User } from "../types";

const emptyCart: Cart = {
  items: [],
  item_count: 0,
  subtotal: 0,
  currency: "MAD",
};

export function CommerceCartSummary({ user }: { user: User | null }) {
  const [cart, setCart] = useState<Cart>(emptyCart);

  useEffect(() => {
    const load = () => {
      if (!user) {
        setCart(getGuestCart());
        return;
      }
      if (user.role !== "customer") {
        setCart(emptyCart);
        return;
      }
      void api<Cart>("/api/cart", {}, true).then(setCart).catch(() => undefined);
    };

    load();
    window.addEventListener("guest-cart-changed", load);
    window.addEventListener("cart-changed", load);
    return () => {
      window.removeEventListener("guest-cart-changed", load);
      window.removeEventListener("cart-changed", load);
    };
  }, [user]);

  return (
    <Link href="/cart" className="commerce-cart" aria-label="Ouvrir le panier">
      <span className="commerce-cart-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M3 4h2l2.1 10.1a2 2 0 0 0 2 1.6h7.8a2 2 0 0 0 2-1.6L20.2 8H6.1" />
          <circle cx="10" cy="20" r="1.2" />
          <circle cx="17" cy="20" r="1.2" />
        </svg>
        <strong>{cart.item_count > 99 ? "99+" : cart.item_count}</strong>
      </span>
      <span>
        <small>Votre panier</small>
        <b>{money(cart.subtotal, cart.currency)}</b>
      </span>
    </Link>
  );
}
