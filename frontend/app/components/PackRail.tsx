"use client";

import Link from "next/link";
import { useRef } from "react";
import { assetUrl, money } from "../lib/api";
import type { Pack } from "../types";

export function PackRail({ packs }: { packs: Pack[] }) {
  const rail = useRef<HTMLDivElement | null>(null);
  const scroll = (direction: -1 | 1) => rail.current?.scrollBy({
    left: direction * Math.max(320, rail.current.clientWidth * 0.82),
    behavior: "smooth",
  });
  if (!packs.length) return null;
  return (
    <section className="pack-rail-section shell" id="packs-promo">
      <div className="rail-heading pack-heading">
        <p className="kicker">Offres groupees</p>
        <h2>Packs en promo</h2>
        <p>Des combinaisons completes, validees par l&apos;admin.</p>
      </div>
      <div className="rail-shell">
        <button className="rail-arrow rail-arrow-left" onClick={() => scroll(-1)} aria-label="Packs precedents">←</button>
        <div className="pack-rail" ref={rail}>
          {packs.map((pack) => {
            const main = assetUrl(pack.main_image_url || pack.products[0]?.product.images?.[0]);
            return (
              <article className="pack-card" key={pack.id}>
                <Link href={`/packs/${pack.id}`} className="pack-card-visual">
                  {main ? <img src={main} alt={pack.name} /> : <span>N</span>}
                  <b>-{Math.round(pack.discount_percentage)}%</b>
                  <div className="pack-mini-products">
                    {pack.products.slice(0, 4).map(({ product }) => {
                      const image = assetUrl(product.images?.[0]);
                      return image ? <img key={product.product_id} src={image} alt="" /> : null;
                    })}
                  </div>
                </Link>
                <div className="pack-card-body">
                  <small>{pack.products.length} produits · {pack.stock} en stock</small>
                  <Link href={`/packs/${pack.id}`}>{pack.name}</Link>
                  <div className="pack-price">
                    <strong>{money(pack.promotional_price, pack.currency)}</strong>
                    <del>{money(pack.regular_price, pack.currency)}</del>
                  </div>
                  <Link href={`/packs/${pack.id}`} className="button button-small">Voir le pack</Link>
                </div>
              </article>
            );
          })}
        </div>
        <button className="rail-arrow rail-arrow-right" onClick={() => scroll(1)} aria-label="Packs suivants">→</button>
      </div>
    </section>
  );
}

