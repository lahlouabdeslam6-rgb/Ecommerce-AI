import type { Cart, CartItem, Pack, Product } from "../types";

const GUEST_CART_KEY = "nutrifit_guest_cart";

function readItems(): CartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const value = JSON.parse(
      window.localStorage.getItem(GUEST_CART_KEY) || "[]",
    ) as CartItem[];
    return Array.isArray(value)
      ? value.map((item) => ({
          ...item,
          item_type: item.item_type || "product",
          pack_id: item.pack_id ?? null,
        })).filter(
          (item) =>
            ((item.item_type === "product" && Number.isInteger(item.product_id) && Number(item.product_id) > 0) ||
              (item.item_type === "pack" && Number.isInteger(item.pack_id) && Number(item.pack_id) > 0)) &&
            Number.isInteger(item.quantity) &&
            item.quantity > 0,
        )
      : [];
  } catch {
    return [];
  }
}

function writeItems(items: CartItem[]) {
  window.localStorage.setItem(GUEST_CART_KEY, JSON.stringify(items));
  window.dispatchEvent(new CustomEvent("guest-cart-changed"));
}

export function getGuestCart(): Cart {
  const items = readItems().map((item) => ({
    ...item,
    subtotal: Math.round(item.unit_price * item.quantity * 100) / 100,
  }));
  return {
    items,
    item_count: items.reduce((total, item) => total + item.quantity, 0),
    subtotal:
      Math.round(
        items.reduce((total, item) => total + item.subtotal, 0) * 100,
      ) / 100,
    currency: "MAD",
  };
}

export function addGuestProduct(product: Product, quantity: number): Cart {
  const items = readItems();
  const existing = items.find(
    (item) => item.product_id === product.product_id,
  );
  const safeQuantity = Math.max(
    1,
    Math.min(Math.floor(quantity), product.stock, 99),
  );
  if (existing) {
    existing.quantity = Math.min(
      existing.quantity + safeQuantity,
      product.stock,
      99,
    );
    existing.stock = product.stock;
    existing.unit_price = Number(product.price || 0);
    existing.subtotal = existing.unit_price * existing.quantity;
  } else {
    items.push({
      product_id: product.product_id,
      pack_id: null,
      item_type: "product",
      name: product.name || "Produit NUTRIFIT",
      brand: product.brand,
      image_url: product.images?.[0] || null,
      unit_price: Number(product.price || 0),
      currency: product.currency || "MAD",
      quantity: safeQuantity,
      subtotal: Number(product.price || 0) * safeQuantity,
      stock: product.stock,
      is_available: product.stock > 0,
    });
  }
  writeItems(items);
  return getGuestCart();
}

export function addGuestPack(pack: Pack, quantity: number): Cart {
  const items = readItems();
  const existing = items.find(
    (item) => item.item_type === "pack" && item.pack_id === pack.id,
  );
  const safeQuantity = Math.max(1, Math.min(Math.floor(quantity), pack.stock, 20));
  if (existing) {
    existing.quantity = Math.min(existing.quantity + safeQuantity, pack.stock, 20);
    existing.stock = pack.stock;
    existing.unit_price = pack.promotional_price;
  } else {
    items.push({
      item_type: "pack",
      product_id: null,
      pack_id: pack.id,
      name: pack.name,
      brand: "Pack NUTRIFIT",
      image_url: pack.main_image_url,
      unit_price: pack.promotional_price,
      currency: pack.currency,
      quantity: safeQuantity,
      subtotal: pack.promotional_price * safeQuantity,
      stock: pack.stock,
      is_available: pack.is_available,
    });
  }
  writeItems(items);
  return getGuestCart();
}

export function updateGuestQuantity(
  productId: number,
  quantity: number,
): Cart {
  const items = readItems();
  const item = items.find((value) => value.product_id === productId);
  if (item) {
    item.quantity = Math.max(1, Math.min(quantity, item.stock, 99));
    item.subtotal = item.unit_price * item.quantity;
  }
  writeItems(items);
  return getGuestCart();
}

export function removeGuestProduct(productId: number): Cart {
  writeItems(readItems().filter((item) => item.item_type !== "product" || item.product_id !== productId));
  return getGuestCart();
}

export function updateGuestPackQuantity(packId: number, quantity: number): Cart {
  const items = readItems();
  const item = items.find((value) => value.item_type === "pack" && value.pack_id === packId);
  if (item) item.quantity = Math.max(1, Math.min(quantity, item.stock, 20));
  writeItems(items);
  return getGuestCart();
}

export function removeGuestPack(packId: number): Cart {
  writeItems(readItems().filter((item) => item.item_type !== "pack" || item.pack_id !== packId));
  return getGuestCart();
}

export function clearGuestCart(): void {
  if (typeof window === "undefined") return;
  writeItems([]);
}
