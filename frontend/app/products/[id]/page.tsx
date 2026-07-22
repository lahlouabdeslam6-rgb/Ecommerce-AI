"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "../../components/AuthProvider";
import { api, assetUrl, money } from "../../lib/api";
import type { Cart, Product } from "../../types";

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user, loading } = useAuth();
  const [product, setProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Product>(`/api/products/${params.id}`)
      .then(setProduct)
      .catch((err: Error) => setError(err.message));
  }, [params.id]);

  const add = async () => {
    if (!user) return router.push(`/login?returnTo=/products/${params.id}`);
    try {
      await api<Cart>("/api/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: product?.product_id, quantity }),
      }, true);
      router.push("/cart");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (error && !product) return <div className="empty-state page-section"><h2>Produit introuvable</h2><p>{error}</p></div>;
  if (loading || !product) return <div className="page-loading">Chargement du produit...</div>;
  const image = assetUrl(product.images?.[0]);

  return <section className="shell page-section product-detail"><div className="detail-visual">{image ? <img src={image} alt={product.name || "Produit"} /> : <div className="detail-placeholder"><span>{(product.category || "S")[0].toUpperCase()}</span><small>Photo a venir</small></div>}</div><div className="detail-copy"><p className="kicker">{product.brand}</p><h1>{product.name}</h1><div className="detail-meta"><span>{product.category || "Complement"}</span><span>{product.form_type}</span></div><p className="detail-description">{product.description}</p><div className="price-line"><strong>{money(product.price || 0, product.currency)}</strong><span className={product.stock ? "text-success" : "text-danger"}>{product.stock ? `${product.stock} disponibles` : "Rupture de stock"}</span></div>{user?.role === "admin" || user?.role === "support" ? <div className="buy-row"><button className="button" onClick={() => router.push(user.role === "admin" ? `/admin?product=${product.product_id}` : `/support/products/${product.product_id}`)}>Modifier le produit</button></div> : <div className="buy-row"><input type="number" min={1} max={Math.min(product.stock, 99)} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} /><button className="button" onClick={add} disabled={!product.stock}>Ajouter au panier</button></div>}{error && <div className="alert alert-error">{error}</div>}<div className="ingredients-panel"><h2>Ingredients</h2>{product.ingredients.length ? <div className="ingredient-list">{product.ingredients.slice(0, 16).map((ingredient, index) => <div key={`${ingredient.name}-${index}`}><span>{ingredient.name}</span><strong>{ingredient.amount_per_serving_mg ? `${ingredient.amount_per_serving_mg} mg` : ingredient.form || "-"}</strong></div>)}</div> : <p>Aucune information disponible.</p>}</div></div></section>;
}
