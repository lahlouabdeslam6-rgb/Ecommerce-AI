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
  assert.doesNotMatch(html, /href="\/cart"/);
  assert.doesNotMatch(html, /href="\/orders"/);
  assert.doesNotMatch(html, /href="\/help"/);
  assert.doesNotMatch(html, /href="\/account"/);
  assert.match(html, /\/nutrifit-hero\.png/);
  assert.doesNotMatch(html, /Ecommerce AI|Starter Project/i);
});

test("anonymous visitors can inspect products before sign-in", async () => {
  const [cardSource, detailSource] = await Promise.all([
    readFile(new URL("../app/components/ProductCard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(cardSource, /const detailHref = productPath/);
  assert.match(cardSource, /const loginHref = `\/login\?returnTo=/);
  assert.match(detailSource, /if \(!user\)[\s\S]*router\.push\(`\/login\?returnTo=/);
  assert.doesNotMatch(detailSource, /router\.replace\(`\/login\?returnTo=/);
});

test("catalogue includes price, brand and flavor filters plus full footer", async () => {
  const [homeSource, footerSource] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/SiteFooter.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(homeSource, /Prix minimum/);
  assert.match(homeSource, /Prix maximum/);
  assert.match(homeSource, /<span>Marque<\/span>/);
  assert.match(homeSource, /<span>Parfum<\/span>/);
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

test("checkout exposes COD and card payment without persisting sensitive fields", async () => {
  const response = await render("/checkout");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /NUTRIFIT \| Nutrition &amp; Performance/);
  assert.match(html, /Chargement de votre espace/);

  const checkoutSource = await readFile(
    new URL("../app/checkout/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(checkoutSource, /Livraison & paiement/);
  assert.match(checkoutSource, /Paiement a la livraison/);
  assert.match(checkoutSource, /Carte bancaire/);
  assert.match(checkoutSource, /aucun debit reel/i);
  assert.match(checkoutSource, /card_last4/);
  assert.match(checkoutSource, /payment_token/);
  assert.doesNotMatch(checkoutSource, /card_number\s*:/);
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
  assert.match(adminSource, /\["content", "Contenu AI"\]/);
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
  assert.match(source, /setCategory\(mentionedCategory\)/);
  assert.match(source, /setBrand\(mentionedBrand\)/);
  assert.match(source, /setFlavor\(mentionedFlavor\)/);
  assert.match(source, /Voir les produits/);
  assert.match(source, /cleanPublishedText/);
});

test("admin has a client message inbox and role-aware notification links", async () => {
  const [adminSource, inboxSource, bellSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/admin/AdminTicketWorkspace.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/NotificationBell.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(adminSource, /\["messages", "Messages clients"\]/);
  assert.match(adminSource, /AdminTicketWorkspace/);
  assert.match(inboxSource, /\/api\/support\/tickets\?page_size=100/);
  assert.match(inboxSource, /Reponse admin envoyee au client/);
  assert.match(inboxSource, /\/messages/);
  assert.match(bellSource, /\/admin\?tab=messages&ticket=/);
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
  assert.match(adminSource, /\["analytics", "Analytics AI"\]/);
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
  assert.match(adminSource, /\["stock-forecast", "Stock intelligent"\]/);
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
  assert.match(adminSource, /\["delivery", "Livraisons AI"\]/);
  assert.match(adminSource, /DeliveryAgentWorkspace/);
  assert.match(deliverySource, /\/api\/admin\/ai\/delivery\/report/);
  assert.match(deliverySource, /\/api\/admin\/ai\/delivery\/scan/);
  assert.match(deliverySource, /Analyser et notifier/);
  assert.match(deliverySource, /ne sont pas répétées pendant 24 heures/);
  assert.match(orchestratorSource, /Delivery Agent/);
});

test("admin SEO Agent audits and applies controlled product metadata", async () => {
  const [adminSource, seoSource, detailSource, cardSource] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/SEOAgentWorkspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/products/[id]/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/components/ProductCard.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(adminSource, /\["seo", "SEO AI"\]/);
  assert.match(adminSource, /SEOAgentWorkspace/);
  assert.match(seoSource, /\/api\/admin\/ai\/seo\/audit/);
  assert.match(seoSource, /Valider et appliquer/);
  assert.match(seoSource, /Aucune proposition n&apos;est appliquée sans validation/);
  assert.match(detailSource, /Questions fréquentes/);
  assert.match(detailSource, /product\.image_alt/);
  assert.match(cardSource, /product\.image_alt/);
});
