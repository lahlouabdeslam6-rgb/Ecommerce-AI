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
  assert.match(detailSource, /if \(!user\) return router\.push\(`\/login\?returnTo=/);
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
  assert.match(contentSource, /Validation admin obligatoire/);
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
