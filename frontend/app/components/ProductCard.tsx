"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, assetUrl, money } from "../lib/api";
import { addGuestProduct } from "../lib/guest-cart";
import type { Cart, Product } from "../types";
import { useAuth } from "./AuthProvider";

export function ProductCard({ product }: { product: Product }) {
  const { user } = useAuth();
  const image = assetUrl(product.images?.[0]);
  const video = assetUrl(product.videos?.[0]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoFailed, setVideoFailed] = useState(false);
  const productPath = `/products/${product.product_id}`;
  const detailHref = productPath;

  useEffect(() => {
    const element = videoRef.current;
    if (!element || !video || videoFailed) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          void element.play().catch(() => undefined);
        } else {
          element.pause();
        }
      },
      { rootMargin: "180px 0px", threshold: 0.05 },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      element.pause();
    };
  }, [video, videoFailed]);

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
        {video && !videoFailed ? (
          <video
            ref={videoRef}
            src={video}
            poster={image || undefined}
            muted
            loop
            playsInline
            preload="metadata"
            aria-label={`Vidéo de ${product.name || "ce produit"}`}
            onError={() => setVideoFailed(true)}
          />
        ) : image ? (
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
