"use client";

import Link from "next/link";
import { api, assetUrl, money } from "../lib/api";
import { addGuestProduct } from "../lib/guest-cart";
import type { Cart, Product } from "../types";
import { useAuth } from "./AuthProvider";

export function ProductCard({ product }: { product: Product }) {
  const { user } = useAuth();
  const image = assetUrl(product.images?.[0]);
  const productPath = `/products/${product.product_id}`;
  const detailHref = productPath;

  const addToCart = async () => {
    try {
      if (user) {
        await api<Cart>(
          "/api/cart/items",
          {
            method: "POST",
            body: JSON.stringify({
              product_id: product.product_id,
              quantity: 1,
            }),
          },
          true,
        );
      } else {
        addGuestProduct(product, 1);
      }
      window.dispatchEvent(new CustomEvent("toast", { detail: "Produit ajouté au panier" }));
    } catch (error) {
      window.dispatchEvent(
        new CustomEvent("toast", { detail: (error as Error).message, error: true }),
      );
    }
  };

  return (
    <article className="product-card">
      <Link href={detailHref} className="product-visual">
        {image ? (
          <img src={image} alt={product.image_alt || product.name || "Produit"} />
        ) : (
          <div className="product-placeholder" aria-hidden="true">
            <span>{(product.category || "S").slice(0, 1).toUpperCase()}</span>
          </div>
        )}
        <span className={`stock-badge ${product.stock > 0 ? "available" : "out"}`}>
          {product.stock > 0 ? `${product.stock} en stock` : "Rupture"}
        </span>
      </Link>
      <div className="product-card-body">
        <p className="eyebrow">{product.brand || "Marque sélectionnée"}</p>
        <Link href={detailHref} className="product-title">
          {product.name}
        </Link>
        <p className="product-category">{product.category || product.form_type || "Complément"}</p>
        <div className="product-card-footer">
          <strong>{money(product.price || 0, product.currency)}</strong>
          {user?.role === "admin" || user?.role === "support" ? (
            <Link
              href={user.role === "admin" ? `/admin?product=${product.product_id}` : `/support/products/${product.product_id}`}
              className="admin-product-link"
            >
              Modifier
            </Link>
          ) : (
            <button
              className="add-button"
              onClick={addToCart}
              disabled={product.stock < 1}
              aria-label={`Ajouter ${product.name} au panier`}
            >
              +
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
