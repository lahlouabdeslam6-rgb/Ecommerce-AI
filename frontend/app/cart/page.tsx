"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Protected } from "../components/Protected";
import { api, assetUrl, money } from "../lib/api";
import type { Cart } from "../types";

export default function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null); const [error, setError] = useState("");
  const load = () => api<Cart>("/api/cart", {}, true).then(setCart).catch((e: Error) => setError(e.message));
  useEffect(() => {
    void load();
  }, []);
  const update = async (productId: number, quantity: number) => { try { setCart(await api<Cart>(`/api/cart/items/${productId}`, { method: "PATCH", body: JSON.stringify({ quantity }) }, true)); } catch (e) { setError((e as Error).message); } };
  const remove = async (productId: number) => setCart(await api<Cart>(`/api/cart/items/${productId}`, { method: "DELETE" }, true));
  return <Protected><section className="shell page-section"><div className="page-title"><div><p className="kicker">Votre sélection</p><h1>Panier</h1></div><Link href="/" className="text-link">Continuer mes achats</Link></div>{error && <div className="alert alert-error">{error}</div>}{!cart ? <div className="page-loading">Chargement du panier…</div> : !cart.items.length ? <div className="empty-state"><h2>Votre panier est vide</h2><p>Découvrez le catalogue et ajoutez vos essentiels.</p><Link href="/" className="button">Voir les produits</Link></div> : <div className="cart-layout"><div className="cart-items">{cart.items.map((item) => { const image = assetUrl(item.image_url); return <article className="cart-item" key={item.product_id}><div className="cart-thumb">{image ? <img src={image} alt={item.name} /> : <span>{item.name[0]}</span>}</div><div className="cart-info"><p className="eyebrow">{item.brand}</p><Link href={`/products/${item.product_id}`}>{item.name}</Link><small>{money(item.unit_price, item.currency)} l’unité</small></div><div className="quantity-control"><button disabled={item.quantity <= 1} onClick={() => update(item.product_id, item.quantity - 1)}>−</button><span>{item.quantity}</span><button disabled={item.quantity >= item.stock} onClick={() => update(item.product_id, item.quantity + 1)}>+</button></div><strong>{money(item.subtotal, item.currency)}</strong><button className="remove-button" onClick={() => remove(item.product_id)}>Retirer</button></article>; })}</div><aside className="order-summary"><p className="kicker">Résumé</p><div><span>Articles</span><strong>{cart.item_count}</strong></div><div><span>Sous-total</span><strong>{money(cart.subtotal, cart.currency)}</strong></div><div><span>Livraison</span><strong>Calculée à la commande</strong></div><div className="summary-total"><span>Total</span><strong>{money(cart.subtotal, cart.currency)}</strong></div><Link href="/checkout" className="button">Passer la commande</Link><small>Paiement en espèces à la livraison</small></aside></div>}</section></Protected>;
}
