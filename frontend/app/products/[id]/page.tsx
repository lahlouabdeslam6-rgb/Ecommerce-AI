"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RecommendationSection } from "../../components/RecommendationSection";
import { useAuth } from "../../components/AuthProvider";
import { api, assetUrl, money } from "../../lib/api";
import { addGuestProduct } from "../../lib/guest-cart";
import type { Cart, Product } from "../../types";

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user, loading } = useAuth();
  const [product, setProduct] = useState<Product | null>(null);
  const [selectedMedia, setSelectedMedia] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Product>(`/api/products/${params.id}`)
      .then((item) => {
        setProduct(item);
        setSelectedMedia(item.images?.[0] || item.videos?.[0] || "");
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, [params.id]);

  const add = async () => {
    try {
      if (user) {
        await api<Cart>(
          "/api/cart/items",
          {
            method: "POST",
            body: JSON.stringify({
              product_id: product?.product_id,
              quantity,
            }),
          },
          true,
        );
      } else if (product) {
        addGuestProduct(product, quantity);
      }
      router.push("/cart");
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  if (error && !product) {
    return (
      <div className="empty-state page-section">
        <h2>Produit introuvable</h2>
        <p>{error}</p>
      </div>
    );
  }
  if (loading || !product) {
    return <div className="page-loading">Chargement du produit...</div>;
  }

  const videos = product.videos || [];
  const media = [
    ...product.images.map((url) => ({ type: "image" as const, url })),
    ...videos.map((url) => ({ type: "video" as const, url })),
  ];
  const activeMedia = selectedMedia || media[0]?.url || "";
  const activeIsVideo = videos.includes(activeMedia);
  const activeUrl = assetUrl(activeMedia);
  const isStaff = user?.role === "admin" || user?.role === "support";

  return (
    <>
      <section className="shell page-section product-detail">
        <div className="product-media-column">
          <div className="detail-visual">
            {activeUrl && activeIsVideo ? (
              <video src={activeUrl} controls playsInline preload="metadata" />
            ) : activeUrl ? (
              <img src={activeUrl} alt={product.image_alt || product.name || "Produit"} />
            ) : (
              <div className="detail-placeholder">
                <span>{(product.category || "S")[0].toUpperCase()}</span>
                <small>Média à venir</small>
              </div>
            )}
          </div>
          {media.length > 1 && (
            <div className="product-media-thumbnails" aria-label="Médias du produit">
              {media.map((item, index) => (
                <button
                  type="button"
                  key={item.url}
                  className={activeMedia === item.url ? "active" : ""}
                  onClick={() => setSelectedMedia(item.url)}
                  aria-label={
                    item.type === "video"
                      ? `Voir la vidéo ${index + 1}`
                      : `Voir la photo ${index + 1}`
                  }
                >
                  {item.type === "video" ? (
                    <>
                      <video src={assetUrl(item.url)} muted preload="metadata" />
                      <span>Vidéo</span>
                    </>
                  ) : (
                    <img
                      src={assetUrl(item.url)}
                      alt={`${product.name || "Produit"} ${index + 1}`}
                    />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="detail-copy">
          <p className="kicker">{product.brand}</p>
          <h1>{product.name}</h1>
          <div className="detail-meta">
            <span>{product.category || "Complement"}</span>
            <span>{product.form_type}</span>
          </div>
          <p className="detail-description">{product.description}</p>
          <div className="price-line">
            <strong>{money(product.price || 0, product.currency)}</strong>
            <span className={product.stock ? "text-success" : "text-danger"}>
              {product.stock
                ? `${product.stock} disponibles`
                : "Rupture de stock"}
            </span>
          </div>
          {isStaff ? (
            <div className="buy-row">
              <button
                className="button"
                onClick={() =>
                  router.push(
                    user?.role === "admin"
                      ? `/admin?product=${product.product_id}`
                      : `/support/products/${product.product_id}`,
                  )
                }
              >
                Modifier le produit
              </button>
            </div>
          ) : (
            <div className="buy-row">
              <input
                type="number"
                min={1}
                max={Math.min(product.stock, 99)}
                value={quantity}
                onChange={(event) => setQuantity(Number(event.target.value))}
              />
              <button
                className="button"
                onClick={add}
                disabled={!product.stock}
              >
                Ajouter au panier
              </button>
            </div>
          )}
          {error && <div className="alert alert-error">{error}</div>}
          <div className="ingredients-panel">
            <h2>Ingredients</h2>
            {product.ingredients.length ? (
              <div className="ingredient-list">
                {product.ingredients.slice(0, 16).map((ingredient, index) => (
                  <div key={`${ingredient.name}-${index}`}>
                    <span>{ingredient.name}</span>
                    <strong>
                      {ingredient.amount_per_serving_mg
                        ? `${ingredient.amount_per_serving_mg} mg`
                        : ingredient.form || "-"}
                    </strong>
                  </div>
                ))}
              </div>
            ) : (
              <p>Aucune information disponible.</p>
            )}
          </div>
          {!!product.seo_faq?.length && (
            <div className="ingredients-panel product-faq">
              <h2>Questions fréquentes</h2>
              {product.seo_faq.map((item) => (
                <details key={item.question}>
                  <summary>{item.question}</summary>
                  <p>{item.answer}</p>
                </details>
              ))}
            </div>
          )}
        </div>
      </section>

      <RecommendationSection
        endpoint={`/api/recommendations/products/${product.product_id}`}
        title="Produits proches de cette selection"
        subtitle="Des alternatives disponibles classees par categorie, profil produit et similarite semantique."
      />
    </>
  );
}
