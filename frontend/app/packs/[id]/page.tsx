"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { SiteFooter } from "../../components/SiteFooter";
import { useAuth } from "../../components/AuthProvider";
import { api, assetUrl, money } from "../../lib/api";
import { addGuestPack } from "../../lib/guest-cart";
import type { Cart, Pack } from "../../types";

export default function PackDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const [pack, setPack] = useState<Pack | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    api<Pack>(`/api/packs/${params.id}`)
      .then((value) => {
        setPack(value);
        setSelectedIndex(0);
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, [params.id]);

  const slides = useMemo(() => {
    if (!pack) return [];
    const packImage = pack.main_image_url || pack.gallery[0] || null;

    return [
      {
        key: "pack",
        image: packImage,
        label: "Vue du pack",
        product: null,
        quantity: null,
      },
      ...pack.products.map(({ product, quantity: productQuantity }) => ({
        key: `product-${product.product_id}`,
        image: product.images?.[0] || null,
        label: product.name || `Produit #${product.product_id}`,
        product,
        quantity: productQuantity,
      })),
    ];
  }, [pack]);

  const activeIndex = slides.length ? Math.min(selectedIndex, slides.length - 1) : 0;
  const selectedSlide = slides[activeIndex];
  const selectedProduct = selectedSlide?.product;

  const moveSelection = (direction: number) => {
    if (slides.length < 2) return;
    setSelectedIndex((current) => (current + direction + slides.length) % slides.length);
  };

  const addToCart = async () => {
    if (!pack) return;
    setAdding(true);
    try {
      if (user?.role === "customer") {
        await api<Cart>("/api/cart/packs", {
          method: "POST",
          body: JSON.stringify({ pack_id: pack.id, quantity }),
        }, true);
      } else if (!user) {
        addGuestPack(pack, quantity);
      } else {
        throw new Error("Le panier est reserve aux clients.");
      }
      window.dispatchEvent(new CustomEvent("cart-changed"));
      window.dispatchEvent(new CustomEvent("toast", { detail: "Pack ajoute au panier" }));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setAdding(false);
    }
  };

  if (error && !pack) return <section className="shell page-section"><div className="alert alert-error">{error}</div><Link href="/" className="button">Retour au catalogue</Link></section>;
  if (!pack) return <div className="page-loading">Chargement du pack...</div>;

  return (
    <>
      <section className="shell page-section pack-detail">
        <div className="pack-gallery">
          <div className="pack-thumbnails" aria-label="Produits du pack">
            {slides.map((slide, index) => (
              <button
                key={slide.key}
                type="button"
                className={activeIndex === index ? "active" : ""}
                onClick={() => setSelectedIndex(index)}
                title={slide.label}
                aria-label={`Afficher ${slide.label}`}
                aria-pressed={activeIndex === index}
              >
                {slide.image ? <img src={assetUrl(slide.image) || ""} alt="" /> : <span>N</span>}
              </button>
            ))}
          </div>

          <div className="pack-main-image">
            {selectedSlide?.image ? (
              <img src={assetUrl(selectedSlide.image) || ""} alt={selectedSlide.label} />
            ) : (
              <span>N</span>
            )}
            {slides.length > 1 && (
              <>
                <button type="button" className="pack-gallery-arrow previous" onClick={() => moveSelection(-1)} aria-label="Produit precedent">&#8592;</button>
                <button type="button" className="pack-gallery-arrow next" onClick={() => moveSelection(1)} aria-label="Produit suivant">&#8594;</button>
              </>
            )}
            <span className="pack-gallery-counter">{activeIndex + 1} / {slides.length}</span>
          </div>
        </div>

        <div className="pack-detail-copy">
          <p className="kicker">Pack NUTRIFIT</p>
          <h1>{pack.name}</h1>

          <section className="pack-selected-card" aria-live="polite">
            <div className="pack-selected-heading">
              <div>
                <small>{selectedProduct ? "Produit selectionne" : "Vue generale"}</small>
                <h2>{selectedProduct?.name || "Le pack en bref"}</h2>
              </div>
              {selectedSlide?.quantity && <b>x{selectedSlide.quantity}</b>}
            </div>

            {selectedProduct ? (
              <>
                <p className="pack-selected-meta">
                  {[selectedProduct.brand, selectedProduct.category || selectedProduct.form_type].filter(Boolean).join(" · ")}
                </p>
                <p className="pack-selected-description">{selectedProduct.description || "Les informations detaillees de ce produit seront completees prochainement."}</p>
                {selectedProduct.ingredients.length > 0 && (
                  <div className="pack-selected-ingredients">
                    {selectedProduct.ingredients.slice(0, 4).map((ingredient, index) => (
                      <span key={`${ingredient.name || "ingredient"}-${index}`}>{ingredient.name || ingredient.category}</span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="pack-selected-description">{pack.description}</p>
                {pack.highlights.length > 0 && <ul className="pack-highlights">{pack.highlights.slice(0, 5).map((item) => <li key={item}>{item}</li>)}</ul>}
              </>
            )}
          </section>

          <div className="pack-detail-price">
            <strong>{money(pack.promotional_price * quantity, pack.currency)}</strong>
            <del>{money(pack.regular_price * quantity, pack.currency)}</del>
            <span>-{Math.round(pack.discount_percentage)}%</span>
          </div>
          <p className="pack-stock">{pack.stock > 0 ? `${pack.stock} packs disponibles` : "Rupture de stock"}</p>

          <div className="pack-components">
            <h2>Ce pack contient</h2>
            <div className="pack-component-grid">
              {pack.products.map(({ product, quantity: count }, index) => (
                <button
                  type="button"
                  className={activeIndex === index + 1 ? "active" : ""}
                  onClick={() => setSelectedIndex(index + 1)}
                  key={product.product_id}
                >
                  <span className="pack-component-image">{product.images?.[0] ? <img src={assetUrl(product.images[0]) || ""} alt="" /> : "N"}</span>
                  <span><strong>{product.name}</strong><small>{[product.brand, product.category || product.form_type].filter(Boolean).join(" · ")}</small></span>
                  <b>x{count}</b>
                </button>
              ))}
            </div>
          </div>

          <div className="pack-buy-row">
            <div className="quantity-control"><button disabled={quantity <= 1} onClick={() => setQuantity((value) => value - 1)}>-</button><span>{quantity}</span><button disabled={quantity >= pack.stock} onClick={() => setQuantity((value) => value + 1)}>+</button></div>
            <button className="button" onClick={addToCart} disabled={adding || !pack.is_available}>{adding ? "Ajout..." : "Ajouter le pack au panier"}</button>
          </div>
          {error && <div className="alert alert-error">{error}</div>}
        </div>
      </section>
      <SiteFooter />
    </>
  );
}
