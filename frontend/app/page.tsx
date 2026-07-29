"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { ProductRail } from "./components/ProductRail";
import { SiteFooter } from "./components/SiteFooter";
import { api } from "./lib/api";
import type { Product, ProductList } from "./types";

type PublishedContent = {
  id: number;
  topic: string;
  title: string;
  subtitle: string | null;
  body: string;
  cta_label: string | null;
  hashtags: string[];
  content_type: string;
};

const PROMOTION_SEARCH_TERMS = [
  "creatine",
  "whey",
  "protein",
  "omega 3",
  "multivitamin",
  "vitamin",
  "magnesium",
  "zinc",
  "bcaa",
  "pre workout",
  "collagen",
];

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function cleanPublishedText(value: string): string {
  return value
    .replace(/<li[^>]*>/gi, "\n- ")
    .replace(/<\/(?:p|div|li|ul|ol|h[1-6])>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function promotionCriteria(
  promotion: PublishedContent,
  filters: { brands: string[]; categories: string[]; flavors: string[] },
) {
  const promotionText = normalizeText([
    promotion.topic,
    promotion.title,
    promotion.subtitle || "",
    promotion.body,
    ...(promotion.hashtags || []),
  ].join(" "));
  const category = filters.categories.find((item) =>
    promotionText.includes(normalizeText(item)),
  );
  const brand = filters.brands.find((item) =>
    promotionText.includes(normalizeText(item)),
  );
  const flavor = filters.flavors.find((item) =>
    promotionText.includes(normalizeText(item)),
  );
  const search = PROMOTION_SEARCH_TERMS.find((term) =>
    promotionText.includes(term),
  ) || promotion.topic;
  return { category, brand, flavor, search };
}

export default function Home() {
  const searchParams = useSearchParams();
  const requestedSearch = searchParams.get("search") || "";
  const [products, setProducts] = useState<ProductList | null>(null);
  const [bestSellers, setBestSellers] = useState<Product[]>([]);
  const [promotionProducts, setPromotionProducts] = useState<Product[]>([]);
  const [filters, setFilters] = useState<{ brands: string[]; categories: string[]; flavors: string[] }>({ brands: [], categories: [], flavors: [] });
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [flavor, setFlavor] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [inStock, setInStock] = useState(false);
  const [sortBy, setSortBy] = useState("newest");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [heroContent, setHeroContent] = useState<PublishedContent | null>(null);
  const [promotion, setPromotion] = useState<PublishedContent | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "16" });
    if (search.trim()) params.set("search", search.trim());
    if (category) params.set("category", category);
    if (brand) params.set("brand", brand);
    if (flavor) params.set("flavor", flavor);
    if (minPrice) params.set("min_price", minPrice);
    if (maxPrice) params.set("max_price", maxPrice);
    if (inStock) params.set("in_stock", "true");
    params.set("sort_by", sortBy);
    return params.toString();
  }, [search, category, brand, flavor, minPrice, maxPrice, inStock, sortBy, page]);

  const resetFilters = () => {
    setSearch("");
    setCategory("");
    setBrand("");
    setFlavor("");
    setMinPrice("");
    setMaxPrice("");
    setInStock(false);
    setSortBy("newest");
    setPage(1);
  };

  const applyPromotionFilter = () => {
    if (!promotion) return;
    const criteria = promotionCriteria(promotion, filters);

    resetFilters();
    if (criteria.category) {
      setCategory(criteria.category);
    } else if (criteria.brand) {
      setBrand(criteria.brand);
    } else if (criteria.flavor) {
      setFlavor(criteria.flavor);
    } else {
      setSearch(criteria.search);
    }
    window.requestAnimationFrame(() => {
      document.getElementById("catalogue")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  useEffect(() => {
    api<{ brands: string[]; categories: string[]; flavors: string[] }>("/api/products/filters").then(setFilters).catch(() => undefined);
    api<Product[]>("/api/products/best-sellers?limit=12").then(setBestSellers).catch(() => undefined);
    api<PublishedContent | null>("/api/content/published?content_type=homepage_hero").then(setHeroContent).catch(() => undefined);
    api<PublishedContent | null>("/api/content/published?content_type=promotion").then(setPromotion).catch(() => undefined);
  }, []);

  useEffect(() => {
    setSearch(requestedSearch);
    setPage(1);
  }, [requestedSearch]);

  useEffect(() => {
    if (!promotion) {
      setPromotionProducts([]);
      return;
    }
    const criteria = promotionCriteria(promotion, filters);
    const params = new URLSearchParams({
      page: "1",
      page_size: "12",
      in_stock: "true",
      sort_by: "stock_desc",
    });
    if (criteria.category) params.set("category", criteria.category);
    else if (criteria.brand) params.set("brand", criteria.brand);
    else if (criteria.flavor) params.set("flavor", criteria.flavor);
    else if (criteria.search) params.set("search", criteria.search);
    api<ProductList>(`/api/products?${params.toString()}`)
      .then((result) => setPromotionProducts(result.items))
      .catch(() => setPromotionProducts([]));
  }, [filters, promotion]);

  useEffect(() => {
    setProducts(null);
    setError("");
    const timer = window.setTimeout(() => {
      api<ProductList>(`/api/products?${query}`).then(setProducts).catch((err: Error) => setError(err.message));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <>
      <section className="hero">
        <div className="hero-content shell">
          <div className="hero-copy">
            <p className="kicker">Nutrition &amp; Performance</p>
            <h1>{heroContent?.title || "Fuel Your Body. Elevate Your Performance."}</h1>
            <p>{heroContent?.body || "Des compléments sélectionnés pour accompagner chaque objectif. Explorez 300 références et commandez avec paiement à la livraison."}</p>
            <a href="#catalogue" className="button hero-cta">{heroContent?.cta_label || "Explorer les compléments"}</a>
            <div className="hero-trust">
              <span><strong>300</strong> produits</span>
              <span><strong>100%</strong> transparence</span>
              <span><strong>COD</strong> au Maroc</span>
            </div>
          </div>
        </div>
      </section>

      {bestSellers.length > 0 && (
        <div className="storefront-rail shell">
          <ProductRail
            eyebrow="Choix des clients"
            title="Les plus vendus"
            subtitle="Les références les plus commandées sur NUTRIFIT."
            products={bestSellers}
          />
        </div>
      )}

      {promotion && (
        <>
          <section className="content-promotion shell">
            <div>
              <p className="kicker">Offre NUTRIFIT</p>
              <h2>{cleanPublishedText(promotion.title)}</h2>
              {promotion.subtitle && <strong>{cleanPublishedText(promotion.subtitle)}</strong>}
              <p>{cleanPublishedText(promotion.body)}</p>
            </div>
            <a href="#catalogue" className="button" onClick={applyPromotionFilter}>
              Voir toute la sélection
            </a>
          </section>
          {promotionProducts.length > 0 && (
            <div className="storefront-rail promotion-rail shell">
              <ProductRail
                eyebrow="Sélection promotionnelle"
                title="Offres & packs"
                subtitle="Les sélections publiées par votre équipe et les agents NUTRIFIT."
                products={promotionProducts}
              />
            </div>
          )}
        </>
      )}

      <section className="catalogue shell" id="catalogue">
        <div className="catalogue-heading">
          <p className="kicker">La sélection NUTRIFIT</p>
          <h2>Tout le catalogue</h2>
          <p>
            {products
              ? `${products.total} produits selon tes critères`
              : "Chargement de la sélection..."}
          </p>
        </div>
        <div className="filters-bar">
          <label className="search-field"><span>Rechercher</span><input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Produit ou marque…" /></label>
          <label><span>Catégorie</span><select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}><option value="">Toutes</option>{filters.categories.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label><span>Marque</span><select value={brand} onChange={(e) => { setBrand(e.target.value); setPage(1); }}><option value="">Toutes</option>{filters.brands.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label><span>Parfum</span><select value={flavor} onChange={(e) => { setFlavor(e.target.value); setPage(1); }}><option value="">Tous</option>{filters.flavors.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label><span>Prix minimum</span><input type="number" min="0" value={minPrice} onChange={(e) => { setMinPrice(e.target.value); setPage(1); }} placeholder="0 MAD" /></label>
          <label><span>Prix maximum</span><input type="number" min="0" value={maxPrice} onChange={(e) => { setMaxPrice(e.target.value); setPage(1); }} placeholder="500 MAD" /></label>
          <label className="check-filter"><input type="checkbox" checked={inStock} onChange={(e) => { setInStock(e.target.checked); setPage(1); }} /><span>En stock uniquement</span></label>
          <label><span>Trier par</span><select value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(1); }}><option value="newest">Nouveautes</option><option value="name">Nom A-Z</option><option value="price_asc">Prix croissant</option><option value="price_desc">Prix decroissant</option><option value="stock_desc">Stock disponible</option></select></label>
          <button className="button button-secondary" type="button" onClick={resetFilters}>Effacer les filtres</button>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        {!products ? (
          <div className="product-rail product-rail-loading">{Array.from({ length: 6 }).map((_, index) => <div className="skeleton-card" key={index}><Skeleton height={230} borderRadius={8} /><Skeleton count={3} /></div>)}</div>
        ) : products.items.length ? (
          <ProductRail
            eyebrow="Résultats"
            title="Produits disponibles"
            subtitle="Fais défiler horizontalement pour découvrir toute la sélection."
            products={products.items}
          />
        ) : (
          <div className="empty-state"><h3>Aucun produit trouvé</h3><p>Essayez une autre recherche.</p></div>
        )}
        {products && products.total_pages > 1 && <div className="pagination"><button disabled={page === 1} onClick={() => setPage((v) => v - 1)}>Précédent</button><span>Page {page} sur {products.total_pages}</span><button disabled={page === products.total_pages} onClick={() => setPage((v) => v + 1)}>Suivant</button></div>}
      </section>
      <SiteFooter />
    </>
  );
}
