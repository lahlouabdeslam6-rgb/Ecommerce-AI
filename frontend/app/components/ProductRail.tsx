"use client";

import { useRef } from "react";
import type { Product } from "../types";
import { ProductCard } from "./ProductCard";

export function ProductRail({
  eyebrow,
  title,
  subtitle,
  products,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  products: Product[];
}) {
  const railRef = useRef<HTMLDivElement | null>(null);

  const scroll = (direction: -1 | 1) => {
    railRef.current?.scrollBy({
      left: direction * Math.max(280, railRef.current.clientWidth * 0.82),
      behavior: "smooth",
    });
  };

  return (
    <section className="product-rail-section">
      <div className="rail-heading">
        <p className="kicker">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      <div className="rail-shell">
        <button
          type="button"
          className="rail-arrow rail-arrow-left"
          onClick={() => scroll(-1)}
          aria-label={`Voir les produits précédents de ${title}`}
        >
          ←
        </button>
        <div className="product-rail" ref={railRef}>
          {products.map((product) => (
            <ProductCard key={product.product_id} product={product} />
          ))}
        </div>
        <button
          type="button"
          className="rail-arrow rail-arrow-right"
          onClick={() => scroll(1)}
          aria-label={`Voir les produits suivants de ${title}`}
        >
          →
        </button>
      </div>
    </section>
  );
}
