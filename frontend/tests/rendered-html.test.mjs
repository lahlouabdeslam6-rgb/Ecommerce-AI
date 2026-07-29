import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${path}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the NUTRIFIT premium homepage", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<html lang="fr">/i);
  assert.match(html, /<title>NUTRIFIT \| Nutrition &amp; Performance<\/title>/i);
  assert.match(html, /Fuel Your Body\. Elevate Your Performance\./);
  assert.match(html, /La sélection NUTRIFIT/);
  assert.match(html, /href="#catalogue"/);
  assert.match(html, /href="\/login"/);
  assert.match(html, /href="\/register"/);
  assert.match(html, /header-actions guest-actions/);
  assert.match(html, /href="\/cart"/);
  assert.match(html, /href="\/orders"/);
  assert.doesNotMatch(html, /href="\/help"/);
  assert.doesNotMatch(html, /href="\/account"/);
  assert.match(html, /\/nutrifit-hero\.png/);
  assert.doesNotMatch(html, /Ecommerce AI|Starter Project/i);
});

test("anonymous visitors can inspect products and use a guest cart", async () => {
  const [cardSource, detailSource] = await Promise.all([
    readFile(new URL("../app/components/ProductCard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(cardSource, /const detailHref = productPath/);
  assert.match(cardSource, /addGuestProduct\(product, 1\)/);
  assert.match(detailSource, /addGuestProduct\(product, quantity\)/);
  assert.doesNotMatch(cardSource, /login\?returnTo=/);
  assert.doesNotMatch(detailSource, /router\.replace\(`\/login\?returnTo=/);
});

test("catalogue includes price, brand and flavor filters plus full footer", async () => {
  const [homeSource, headerSource, cartSummarySource, railSource, footerSource] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/Header.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/components/CommerceCartSummary.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/ProductRail.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/components/SiteFooter.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(homeSource, /Prix minimum/);
  assert.match(homeSource, /Prix maximum/);
  assert.match(homeSource, /<span>Marque<\/span>/);
  assert.match(homeSource, /<span>Parfum<\/span>/);
  assert.match(homeSource, /\/api\/products\/best-sellers\?limit=12/);
  assert.match(homeSource, /title="Les plus vendus"/);
  assert.match(homeSource, /title="Offres & packs"/);
  assert.match(homeSource, /title="Produits disponibles"/);
  assert.doesNotMatch(homeSource, /className="product-grid"/);
  assert.match(headerSource, /className="commerce-search"/);
  assert.match(headerSource, /CommerceCartSummary/);
  assert.match(headerSource, /Rechercher un produit ou une marque/);
  assert.match(cartSummarySource, /cart\.item_count/);
  assert.match(cartSummarySource, /money\(cart\.subtotal, cart\.currency\)/);
  assert.match(railSource, /className="product-rail"/);
  assert.match(railSource, /scrollBy/);
  assert.match(homeSource, /<SiteFooter \/>/);
  assert.match(footerSource, /footer-grid/);
  assert.match(footerSource, /support@nutrifit\.ma/);
});

test("support can edit products without cart controls", async () => {
  const [cardSource, detailSource, supportEditor] = await Promise.all([
    readFile(new URL("../app/components/ProductCard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/support/products/[id]/page.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(cardSource, /user\?\.role === "admin" \|\| user\?\.role === "support"/);
  assert.match(cardSource, /\/support\/products\/\$\{product\.product_id\}/);
  assert.match(detailSource, /user\?\.role === "admin" \|\| user\?\.role === "support"/);
  assert.match(supportEditor, /Protected roles=\{\["support", "admin"\]\}/);
  assert.match(supportEditor, /Produit mis a jour/);

  const supportWorkspace = await readFile(
    new URL("../app/support/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(supportWorkspace, />Produits<\/button>/);
  assert.match(supportWorkspace, /Modifier les produits/);
  assert.match(supportWorkspace, /\/support\/products\/\$\{product\.product_id\}/);
});

test("admin and support can upload multiple product photos and videos", async () => {
  const [adminSource, supportEditor, managerSource, detailSource] =
    await Promise.all([
      readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
      readFile(
        new URL("../app/support/products/[id]/page.tsx", import.meta.url),
        "utf8",
      ),
      readFile(
        new URL("../app/components/ProductImageManager.tsx", import.meta.url),
        "utf8",
      ),
      readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
    ]);
  for (const source of [adminSource, supportEditor]) {
    assert.match(source, /Ajouter des photos ou vidéos/);
    assert.match(source, /multiple/);
    assert.match(source, /\/api\/products\/\$\{[^}]+\}\/media/);
    assert.match(source, /video\/mp4/);
  }
  assert.match(managerSource, /\/videos\?video_url=/);
  assert.match(managerSource, /Vidéo principale/);
  assert.match(detailSource, /controls playsInline/);
  assert.match(detailSource, /product-media-thumbnails/);
});

test("catalogue product videos autoplay only near the viewport", async () => {
  const cardSource = await readFile(
    new URL("../app/components/ProductCard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(cardSource, /product\.videos\?\.\[0\]/);
  assert.match(cardSource, /IntersectionObserver/);
  assert.match(cardSource, /rootMargin: "180px 0px"/);
  assert.match(cardSource, /element\.play\(\)/);
  assert.match(cardSource, /element\.pause\(\)/);
  assert.match(cardSource, /muted/);
  assert.match(cardSource, /loop/);
  assert.match(cardSource, /playsInline/);
  assert.match(cardSource, /poster=\{image \|\| undefined\}/);
});

test("checkout exposes COD and card payment without persisting sensitive fields", async () => {
  const response = await render("/checkout");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /NUTRIFIT \| Nutrition &amp; Performance/);
  assert.doesNotMatch(html, /Chargement de votre espace/);

  const [checkoutSource, ordersSource, guestOrdersSource, headerSource] =
    await Promise.all([
      readFile(new URL("../app/checkout/page.tsx", import.meta.url), "utf8"),
      readFile(new URL("../app/orders/page.tsx", import.meta.url), "utf8"),
      readFile(new URL("../app/lib/guest-orders.ts", import.meta.url), "utf8"),
      readFile(new URL("../app/components/Header.tsx", import.meta.url), "utf8"),
    ]);
  assert.match(checkoutSource, /Livraison & paiement/);
  assert.match(checkoutSource, /Paiement a la livraison/);
  assert.match(checkoutSource, /Carte bancaire/);
  assert.match(checkoutSource, /Le compte est facultatif/);
  assert.match(checkoutSource, /L&apos;adresse\s+exacte sera confirmée/);
  assert.match(checkoutSource, /La commande ne sera\s+envoyée/);
  assert.doesNotMatch(checkoutSource, /\bEmail\b/);
  assert.doesNotMatch(checkoutSource, /\bAdresse\b/);
  assert.doesNotMatch(checkoutSource, /Notes de livraison/);
  assert.match(checkoutSource, /\/api\/orders\/guest-checkout/);
  assert.match(checkoutSource, /saveGuestOrderReceipt/);
  assert.match(checkoutSource, /clearGuestCart\(\)/);
  assert.match(checkoutSource, /router\.push\(`\/orders\?created=/);
  assert.doesNotMatch(checkoutSource, /setGuestOrder/);
  assert.match(checkoutSource, /aucun debit reel/i);
  assert.match(checkoutSource, /card_last4/);
  assert.match(checkoutSource, /payment_token/);
  assert.doesNotMatch(checkoutSource, /card_number\s*:/);
  assert.match(ordersSource, /\/api\/orders\/guest-track/);
  assert.match(ordersSource, /getGuestOrderReceipts/);
  assert.match(ordersSource, /Suivi sans compte/);
  assert.match(ordersSource, /Votre panier a été\s+vidé/);
  assert.doesNotMatch(ordersSource, /<Protected/);
  assert.match(guestOrdersSource, /nutrifit_guest_orders/);
  assert.match(guestOrdersSource, /nutrifit_guest_order/);
  assert.match(headerSource, /\["\/orders", "Commandes"\]/);
});

test("admin exposes the complete audit history workspace", async () => {
  const adminSource = await readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8");
  assert.match(adminSource, /\["audit", "Historique"\]/);
  assert.match(adminSource, /Historique des actions/);
  assert.match(adminSource, /\/api\/admin\/audit-logs\?page_size=100/);
  assert.match(adminSource, /Admin \/ acteur/);
});

test("admin roles are read-only and support accounts can be safely deleted", async () => {
  const adminSource = await readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8");
  assert.match(adminSource, /role-badge role-\$\{item\.role\}/);
  assert.doesNotMatch(adminSource, /onChange=\{\(e\) => updateRole/);
  assert.match(adminSource, /Supprimer le compte/);
  assert.match(adminSource, /method: "DELETE"/);
});

test("admin reviews Product Agent content before applying it", async () => {
  const adminSource = await readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8");
  assert.match(adminSource, /Optimiser avec Product Agent/);
  assert.match(adminSource, /Aucune information ne change sans ta validation/);
  assert.match(adminSource, /Proposition a valider/);
  assert.match(adminSource, /Valider et appliquer/);
  assert.match(adminSource, /\/api\/admin\/ai\/products\/\$\{editingId\}\/suggest/);
  assert.match(adminSource, /\/api\/admin\/ai\/products\/\$\{editingId\}\/apply/);
});

test("admin Content Agent uses draft review and controlled publishing", async () => {
  const [adminSource, contentSource, homeSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/ContentAgentWorkspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(adminSource, /\["content-seo", "Contenu & SEO"\]/);
  assert.match(contentSource, /Validation admin \+ Safety AI/);
  assert.match(contentSource, /Generer le brouillon/);
  assert.match(contentSource, /Enregistrer brouillon/);
  assert.match(contentSource, /"Publier"/);
  assert.match(contentSource, /\/api\/admin\/ai\/content\/\$\{draft\.id\}\/publish/);
  assert.match(homeSource, /\/api\/content\/published\?content_type=homepage_hero/);
  assert.match(homeSource, /\/api\/content\/published\?content_type=promotion/);
});

test("published promotions filter the matching catalogue segment", async () => {
  const source = await readFile(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /applyPromotionFilter/);
  assert.match(source, /promotionCriteria/);
  assert.match(source, /setCategory\(criteria\.category\)/);
  assert.match(source, /setBrand\(criteria\.brand\)/);
  assert.match(source, /setFlavor\(criteria\.flavor\)/);
  assert.match(source, /Voir toute la sélection/);
  assert.match(source, /cleanPublishedText/);
});

test("notifications open their exact order or conversation for every role", async () => {
  const [adminSource, supportSource, ordersSource, inboxSource, bellSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/support/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/orders/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/AdminTicketWorkspace.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/NotificationBell.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["support-delivery", "Support & livraison"\]/);
  assert.match(adminSource, /AdminTicketWorkspace/);
  assert.match(inboxSource, /\/api\/support\/tickets\?page_size=100/);
  assert.match(inboxSource, /\/api\/support\/tickets\/\$\{initialTicketId\}/);
  assert.match(inboxSource, /Reponse admin envoyee au client/);
  assert.match(inboxSource, /\/messages/);
  assert.match(adminSource, /requestedTab === "support-delivery"/);
  assert.match(adminSource, /admin-order-\$\{order\.id\}/);
  assert.match(supportSource, /support-order-\$\{order\.id\}/);
  assert.match(ordersSource, /customer-order-\$\{order\.id\}/);
  assert.match(bellSource, /\/admin\?tab=support-delivery&ticket=/);
  assert.match(bellSource, /\/support\?tab=operations&ticket=/);
  assert.match(bellSource, /\/admin\?tab=orders&order=/);
  assert.match(bellSource, /\/support\?tab=orders&order=/);
  assert.match(bellSource, /\/orders\?order=/);
  assert.doesNotMatch(bellSource, /return link \? \(/);
});

test("admin Marketing Agent keeps campaigns in a controlled approval flow", async () => {
  const [adminSource, marketingSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/MarketingAgentWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["marketing", "Marketing AI"\]/);
  assert.match(adminSource, /MarketingAgentWorkspace/);
  assert.match(marketingSource, /Generer la campagne/);
  assert.match(marketingSource, /Enregistrer brouillon/);
  assert.match(marketingSource, /Valider la campagne/);
  assert.match(marketingSource, /Aucun message n'a ete envoye automatiquement/);
  assert.match(
    marketingSource,
    /\/api\/admin\/ai\/marketing\/campaigns\/\$\{draft\.id\}\/approve/,
  );
});

test("admin Safety Agent reviews text and exposes the control history", async () => {
  const [adminSource, safetySource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/SafetyAgentWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["safety", "Safety AI"\]/);
  assert.match(adminSource, /SafetyAgentWorkspace/);
  assert.match(safetySource, /Analyser avec Safety AI/);
  assert.match(safetySource, /Historique des controles/);
  assert.match(safetySource, /Protection nutrition et sante/);
  assert.match(safetySource, /\/api\/admin\/ai\/safety\/review/);
  assert.match(safetySource, /\/api\/admin\/ai\/safety\/reviews/);
  assert.match(safetySource, /blocked: "Bloque"/);
});

test("Recommendation Agent appears on product detail and cart", async () => {
  const [detailSource, cartSource, recommendationSource] = await Promise.all([
    readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/cart/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/components/RecommendationSection.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(detailSource, /RecommendationSection/);
  assert.match(
    detailSource,
    /\/api\/recommendations\/products\/\$\{product\.product_id\}/,
  );
  assert.match(cartSource, /\/api\/recommendations\/cart/);
  assert.match(cartSource, /authenticated/);
  assert.match(cartSource, /interactive/);
  assert.match(recommendationSource, /Recommendation Agent/);
  assert.match(recommendationSource, /Budget max par produit/);
  assert.match(recommendationSource, /Qdrant \+ catalogue/);
  assert.match(recommendationSource, /result\.disclaimer/);
});

test("customer AI assistant routes requests through the Orchestrator", async () => {
  const [layoutSource, assistantSource, resultSource, helpSource] = await Promise.all([
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/components/AIShoppingAssistant.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/OrchestratorResult.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/help/page.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(layoutSource, /AIShoppingAssistant/);
  assert.match(assistantSource, /user\?\.role !== "customer"/);
  assert.match(assistantSource, /\/api\/orchestrator\/execute/);
  assert.match(assistantSource, /Je cherche de la créatine à moins de 300 MAD/);
  assert.match(assistantSource, /Où est ma dernière commande/);
  assert.match(assistantSource, /Produits \+ Commandes \+ Support \+ Sécurité/);
  assert.match(resultSource, /Recommendation Agent/);
  assert.match(resultSource, /Support Agent/);
  assert.match(resultSource, /Safety Agent/);
  assert.match(resultSource, /\/products\/\$\{productId\}/);
  assert.match(resultSource, /ai-recommendation-item ai-recommendation-link/);
  assert.match(resultSource, /Voir le produit/);
  assert.match(resultSource, /Contacter le support humain/);
  assert.match(resultSource, /Demande transmise/);
  assert.match(resultSource, /Suivre la demande/);
  assert.match(helpSource, /searchParams\.get\("ticket"\)/);
  assert.match(helpSource, /ticketToSelect/);
  assert.match(resultSource, /result\.agent === "support"/);
});

test("admin AI Orchestrator exposes routing, safety and persistent history", async () => {
  const [adminSource, workspaceSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/OrchestratorWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["orchestrator", "AI Orchestrator"\]/);
  assert.match(adminSource, /OrchestratorWorkspace/);
  assert.match(workspaceSource, /\/api\/orchestrator\/execute/);
  assert.match(workspaceSource, /\/api\/orchestrator\/history\?page_size=40/);
  assert.match(workspaceSource, /Historique Orchestrator/);
  assert.match(workspaceSource, /Prévisualisation \+ Safety/);
  assert.match(workspaceSource, /actor_email/);
  assert.match(workspaceSource, /Automatique \(recommandé\)/);
  assert.match(workspaceSource, /setTaskType\(example\.taskType\)/);
  assert.match(workspaceSource, /Le Product Agent nécessite un identifiant de produit valide/);
  assert.match(workspaceSource, /Résultat prêt/);
  assert.match(workspaceSource, /Analyse les ventes des 30 derniers jours/);
  assert.match(workspaceSource, /Analytics Agent/);
  assert.match(workspaceSource, /Support Agent/);
  assert.match(workspaceSource, /paiement à la livraison/);
});

test("admin Analytics Agent exposes read-only sales intelligence in French", async () => {
  const [adminSource, analyticsSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/AnalyticsAgentWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["business-intelligence", "Business Intelligence"\]/);
  assert.match(adminSource, /AnalyticsAgentWorkspace/);
  assert.match(analyticsSource, /\/api\/admin\/ai\/analytics\/report/);
  assert.match(analyticsSource, /Générer le résumé IA/);
  assert.match(analyticsSource, /Revenu confirmé/);
  assert.match(analyticsSource, /Produits les plus vendus/);
  assert.match(analyticsSource, /Produits sans vente/);
  assert.match(analyticsSource, /lecture seule/);
  assert.match(analyticsSource, /Période actuelle \/ précédente/);
  assert.match(analyticsSource, /Répartition des commandes/);
  assert.match(analyticsSource, /analytics-top-products-chart/);
  assert.match(analyticsSource, /Évolution quotidienne/);
});

test("admin Stock Forecast Agent explains stock risks with simple graphs", async () => {
  const [adminSource, stockSource, orchestratorSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/StockForecastWorkspace.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/admin/OrchestratorWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["business-intelligence", "Business Intelligence"\]/);
  assert.match(adminSource, /StockForecastWorkspace/);
  assert.match(stockSource, /\/api\/admin\/ai\/stock-forecast\/report/);
  assert.match(stockSource, /Répartition du risque/);
  assert.match(stockSource, /Jours de stock restants/);
  assert.match(stockSource, /Priorités de stock/);
  assert.match(stockSource, /quantité suggérée/);
  assert.match(stockSource, /ne passe aucune commande fournisseur/);
  assert.match(orchestratorSource, /Stock Forecast Agent/);
  assert.match(orchestratorSource, /Prévois les risques de rupture de stock/);
});

test("admin Delivery Agent monitors delays and controls notifications", async () => {
  const [adminSource, deliverySource, orchestratorSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/DeliveryAgentWorkspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/OrchestratorWorkspace.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(adminSource, /\["support-delivery", "Support & livraison"\]/);
  assert.match(adminSource, /DeliveryAgentWorkspace/);
  assert.match(deliverySource, /\/api\/admin\/ai\/delivery\/report/);
  assert.match(deliverySource, /\/api\/admin\/ai\/delivery\/scan/);
  assert.match(deliverySource, /Analyser et notifier/);
  assert.match(deliverySource, /ne sont pas répétées pendant 24 heures/);
  assert.match(orchestratorSource, /Delivery Agent/);
});

test("staff uses merged AI workspaces and human-controlled order verification", async () => {
  const [adminSource, supportSource, verificationSource, orchestratorSource] =
    await Promise.all([
      readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
      readFile(new URL("../app/support/page.tsx", import.meta.url), "utf8"),
      readFile(
        new URL(
          "../app/components/OrderVerificationWorkspace.tsx",
          import.meta.url,
        ),
        "utf8",
      ),
      readFile(
        new URL("../app/admin/OrchestratorWorkspace.tsx", import.meta.url),
        "utf8",
      ),
    ]);
  assert.match(adminSource, /\["content-seo", "Contenu & SEO"\]/);
  assert.match(adminSource, /\["business-intelligence", "Business Intelligence"\]/);
  assert.match(adminSource, /\["support-delivery", "Support & livraison"\]/);
  assert.match(supportSource, />Demandes clients<\/button>/);
  assert.match(supportSource, />Commandes<\/button>/);
  assert.match(supportSource, /requestedTab === "orders"/);
  assert.match(
    supportSource,
    /tab === "orders" && <><div className="page-title">/,
  );
  assert.match(
    supportSource,
    /orders\.items\.map[\s\S]*<OrderVerificationWorkspace \/><DeliveryAgentWorkspace/,
  );
  assert.match(supportSource, /OrderVerificationWorkspace/);
  assert.match(verificationSource, /\/api\/ai\/order-verification\/report/);
  assert.match(verificationSource, /ne refuse et n&apos;annule jamais/);
  assert.match(verificationSource, /Vérification prioritaire/);
  assert.match(verificationSource, /Doublon possible/);
  assert.match(orchestratorSource, /Order Verification Agent/);
});

test("admin SEO Agent audits and applies controlled product metadata", async () => {
  const [adminSource, seoSource, detailSource, cardSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/SEOAgentWorkspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/ProductCard.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(adminSource, /\["content-seo", "Contenu & SEO"\]/);
  assert.match(adminSource, /SEOAgentWorkspace/);
  assert.match(seoSource, /\/api\/admin\/ai\/seo\/audit/);
  assert.match(seoSource, /Valider et appliquer/);
  assert.match(seoSource, /Aucune proposition n&apos;est appliquée sans validation/);
  assert.match(detailSource, /Questions fréquentes/);
  assert.match(detailSource, /product\.image_alt/);
  assert.match(cardSource, /product\.image_alt/);
});

test("staff Pilotage supports catalogue and user search plus media on creation", async () => {
  const [adminSource, supportSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/support/page.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(adminSource, /Rechercher un produit/);
  assert.match(adminSource, /\/api\/products\/manage\?page_size=100/);
  assert.match(adminSource, /Rechercher un utilisateur/);
  assert.match(adminSource, /\/api\/admin\/users\?page_size=100/);
  assert.match(adminSource, /pendingMedia/);
  assert.match(
    adminSource,
    /Ces fichiers seront ajoutés automatiquement après la création du produit/,
  );
  assert.doesNotMatch(
    adminSource,
    /\{editingId && <label className="full-field">Ajouter des photos/,
  );
  assert.match(supportSource, /Rechercher un produit/);
  assert.match(supportSource, /\/api\/products\/manage\?page=/);
});
