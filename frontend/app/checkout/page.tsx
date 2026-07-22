"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Protected } from "../components/Protected";
import { useAuth } from "../components/AuthProvider";
import { api, money } from "../lib/api";
import type { Cart, Order } from "../types";

type PaymentMethod = "cash_on_delivery" | "card";

export default function CheckoutPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const [form, setForm] = useState({ full_name: "", phone: "", address: "", city: "", notes: "" });
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash_on_delivery");
  const [card, setCard] = useState({ holder: "", number: "", expiry: "", cvv: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) setForm((value) => ({ ...value, full_name: user.full_name || "" }));
    api<Cart>("/api/cart", {}, true).then(setCart).catch((err: Error) => setError(err.message));
  }, [user]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const digits = card.number.replace(/\D/g, "");
    if (paymentMethod === "card") {
      if (!card.holder.trim() || !luhnValid(digits) || !expiryValid(card.expiry) || !/^\d{3,4}$/.test(card.cvv)) {
        setError("Verifiez le nom, le numero, la date et le CVV de la carte.");
        return;
      }
    }
    setSubmitting(true);
    try {
      const payload = paymentMethod === "card"
        ? { ...form, payment_method: paymentMethod, card_last4: digits.slice(-4), card_brand: cardBrand(digits), payment_token: `demo_${crypto.randomUUID()}` }
        : { ...form, payment_method: paymentMethod };
      const order = await api<Order>("/api/orders/checkout", { method: "POST", body: JSON.stringify(payload) }, true);
      setCard({ holder: "", number: "", expiry: "", cvv: "" });
      router.push(`/orders?created=${order.id}`);
    } catch (err) { setError((err as Error).message); }
    finally { setSubmitting(false); }
  };

  return <Protected roles={["customer"]}><section className="shell page-section checkout-page"><div><p className="kicker">Derniere etape</p><h1>Livraison & paiement</h1><p className="muted">Choisissez le paiement a la livraison ou par carte en mode test local.</p><form className="checkout-form" onSubmit={submit}><div className="form-grid"><label>Nom complet<input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></label><label>Telephone<input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+212 6..." required /></label><label className="full-field">Adresse<input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} required /></label><label>Ville<input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required /></label><label>Notes<textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label></div><fieldset className="payment-methods"><legend>Mode de paiement</legend><label className={`payment-option ${paymentMethod === "cash_on_delivery" ? "selected" : ""}`}><input type="radio" name="payment" checked={paymentMethod === "cash_on_delivery"} onChange={() => setPaymentMethod("cash_on_delivery")} /><span><strong>Paiement a la livraison</strong><small>Payez en especes quand la commande arrive.</small></span></label><label className={`payment-option ${paymentMethod === "card" ? "selected" : ""}`}><input type="radio" name="payment" checked={paymentMethod === "card"} onChange={() => setPaymentMethod("card")} /><span><strong>Carte bancaire</strong><small>Interface de test securisee, aucun debit reel.</small></span></label></fieldset>{paymentMethod === "card" && <div className="card-payment-panel"><div className="card-preview"><span>NUTRIFIT</span><strong>{card.number ? card.number.replace(/\d(?=\d{4})/g, "*") : "**** **** **** 4242"}</strong><small>{card.holder || "NOM DU TITULAIRE"} - {card.expiry || "MM/AA"}</small></div><div className="form-grid"><label className="full-field">Nom sur la carte<input autoComplete="cc-name" value={card.holder} onChange={(e) => setCard({ ...card, holder: e.target.value })} required /></label><label className="full-field">Numero de carte<input inputMode="numeric" autoComplete="cc-number" maxLength={23} value={card.number} onChange={(e) => setCard({ ...card, number: formatCard(e.target.value) })} placeholder="4242 4242 4242 4242" required /></label><label>Expiration<input inputMode="numeric" autoComplete="cc-exp" maxLength={5} value={card.expiry} onChange={(e) => setCard({ ...card, expiry: formatExpiry(e.target.value) })} placeholder="MM/AA" required /></label><label>CVV<input type="password" inputMode="numeric" autoComplete="cc-csc" maxLength={4} value={card.cvv} onChange={(e) => setCard({ ...card, cvv: e.target.value.replace(/\D/g, "") })} placeholder="123" required /></label></div><p className="card-security-note">Le numero complet et le CVV ne sont jamais enregistres. Pour un paiement reel, cette zone sera connectee a un prestataire bancaire.</p></div>}{error && <div className="alert alert-error">{error}</div>}<button className="button" disabled={submitting || !cart?.items.length}>{submitting ? "Confirmation..." : paymentMethod === "card" ? "Payer et confirmer" : "Confirmer la commande"}</button></form></div><aside className="order-summary sticky"><p className="kicker">Votre commande</p>{cart?.items.map((item) => <div key={item.product_id}><span>{item.quantity} x {item.name}</span><strong>{money(item.subtotal, item.currency)}</strong></div>)}<div><span>Paiement</span><strong>{paymentMethod === "card" ? "Carte" : "A la livraison"}</strong></div><div className="summary-total"><span>Total</span><strong>{money(cart?.subtotal || 0)}</strong></div></aside></section></Protected>;
}

function formatCard(value: string) { return value.replace(/\D/g, "").slice(0, 19).replace(/(.{4})/g, "$1 ").trim(); }
function formatExpiry(value: string) { const digits = value.replace(/\D/g, "").slice(0, 4); return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits; }
function cardBrand(value: string) { if (/^4/.test(value)) return "Visa"; if (/^(5[1-5]|2[2-7])/.test(value)) return "Mastercard"; return "Carte"; }
function luhnValid(value: string) { if (value.length < 13 || value.length > 19) return false; let sum = 0; let double = false; for (let index = value.length - 1; index >= 0; index--) { let digit = Number(value[index]); if (double) { digit *= 2; if (digit > 9) digit -= 9; } sum += digit; double = !double; } return sum % 10 === 0; }
function expiryValid(value: string) { const match = /^(\d{2})\/(\d{2})$/.exec(value); if (!match) return false; const month = Number(match[1]); const year = 2000 + Number(match[2]); if (month < 1 || month > 12) return false; const expiry = new Date(year, month, 1); return expiry > new Date(); }
