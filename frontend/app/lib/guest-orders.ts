export type GuestOrderReceipt = {
  order_id: number;
  tracking_token: string;
};

const GUEST_ORDERS_KEY = "nutrifit_guest_orders";
const LEGACY_GUEST_ORDER_KEY = "nutrifit_guest_order";
const MAX_GUEST_ORDERS = 20;

function isReceipt(value: unknown): value is GuestOrderReceipt {
  if (!value || typeof value !== "object") return false;
  const receipt = value as Partial<GuestOrderReceipt>;
  return (
    Number.isInteger(receipt.order_id) &&
    Number(receipt.order_id) > 0 &&
    typeof receipt.tracking_token === "string" &&
    receipt.tracking_token.length >= 32
  );
}

function parseReceipts(value: string | null): GuestOrderReceipt[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.filter(isReceipt) : [];
  } catch {
    return [];
  }
}

export function getGuestOrderReceipts(): GuestOrderReceipt[] {
  if (typeof window === "undefined") return [];

  const receipts = parseReceipts(
    window.localStorage.getItem(GUEST_ORDERS_KEY),
  );
  const legacyValue = window.localStorage.getItem(LEGACY_GUEST_ORDER_KEY);
  if (!legacyValue) return receipts;

  try {
    const legacyReceipt = JSON.parse(legacyValue) as unknown;
    if (
      isReceipt(legacyReceipt) &&
      !receipts.some((item) => item.order_id === legacyReceipt.order_id)
    ) {
      receipts.unshift(legacyReceipt);
    }
  } catch {
    // Ignore invalid legacy data and remove it below.
  }

  window.localStorage.removeItem(LEGACY_GUEST_ORDER_KEY);
  writeGuestOrderReceipts(receipts);
  return receipts;
}

export function saveGuestOrderReceipt(receipt: GuestOrderReceipt): void {
  if (typeof window === "undefined") return;
  const receipts = getGuestOrderReceipts().filter(
    (item) => item.order_id !== receipt.order_id,
  );
  writeGuestOrderReceipts([receipt, ...receipts]);
}

export function removeGuestOrderReceipt(orderId: number): void {
  if (typeof window === "undefined") return;
  writeGuestOrderReceipts(
    getGuestOrderReceipts().filter((item) => item.order_id !== orderId),
  );
}

function writeGuestOrderReceipts(receipts: GuestOrderReceipt[]): void {
  window.localStorage.setItem(
    GUEST_ORDERS_KEY,
    JSON.stringify(receipts.slice(0, MAX_GUEST_ORDERS)),
  );
}
