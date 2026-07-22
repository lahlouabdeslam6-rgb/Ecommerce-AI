"use client";

import { api, assetUrl } from "../lib/api";
import type { Product } from "../types";

export function ProductImageManager({
  product,
  onChange,
  onError,
}: {
  product: Product;
  onChange: (product: Product) => void;
  onError: (message: string) => void;
}) {
  const remove = async (image: string) => {
    if (!window.confirm("Supprimer cette photo ?")) return;
    try {
      const updated = await api<Product>(
        `/api/products/${product.product_id}/images?image_url=${encodeURIComponent(image)}`,
        { method: "DELETE" },
        true,
      );
      onChange(updated);
    } catch (err) {
      onError((err as Error).message);
    }
  };

  const setMain = async (image: string) => {
    const images = [image, ...product.images.filter((item) => item !== image)];
    try {
      const updated = await api<Product>(
        `/api/products/${product.product_id}/images/order`,
        { method: "PATCH", body: JSON.stringify({ images }) },
        true,
      );
      onChange(updated);
    } catch (err) {
      onError((err as Error).message);
    }
  };

  if (!product.images.length) return <p className="muted">Aucune photo ajoutee.</p>;
  return (
    <div className="product-image-manager">
      {product.images.map((image, index) => (
        <article key={image}>
          <img src={assetUrl(image) || image} alt={`${product.name || "Produit"} ${index + 1}`} />
          <div>
            {index === 0 ? <span>Photo principale</span> : <button type="button" className="text-link" onClick={() => setMain(image)}>Mettre en premier</button>}
            <button type="button" className="text-link danger-link" onClick={() => remove(image)}>Supprimer</button>
          </div>
        </article>
      ))}
    </div>
  );
}
