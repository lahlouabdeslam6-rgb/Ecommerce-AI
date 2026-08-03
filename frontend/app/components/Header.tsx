"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { CommerceCartSummary } from "./CommerceCartSummary";
import { NotificationBell } from "./NotificationBell";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading, logout } = useAuth();
  const [catalogSearch, setCatalogSearch] = useState("");
  const isShopper = !user || user.role === "customer";
  const links = !user
    ? [["/", "Produits"], ["/orders", "Commandes"]]
    : user.role === "support"
      ? [["/", "Produits"], ["/support", "Espace support"], ["/account", "Compte"]]
      : user.role === "admin"
        ? [["/", "Produits"], ["/admin", "Administration"], ["/account", "Compte"]]
        : [["/", "Produits"], ["/orders", "Commandes"], ["/help", "Aide"], ["/account", "Compte"]];

  useEffect(() => {
    if (pathname === "/") {
      setCatalogSearch(searchParams.get("search") || "");
    }
  }, [pathname, searchParams]);

  const searchCatalogue = (event: FormEvent) => {
    event.preventDefault();
    const term = catalogSearch.trim();
    router.push(term ? `/?search=${encodeURIComponent(term)}#catalogue` : "/#catalogue");
  };

  const navigation = (
    <nav className="main-nav" aria-label="Navigation principale">
      {links.map(([href, label]) => (
        <Link key={href} href={href} className={pathname === href ? "active" : ""}>
          {label}
        </Link>
      ))}
    </nav>
  );

  return (
    <header className={`site-header ${isShopper ? "storefront-header" : ""}`}>
      {isShopper && (
        <div className="commerce-strip">
          <span>Livraison partout au Maroc</span>
          <strong>Paiement à la livraison</strong>
          <span>Support NUTRIFIT</span>
        </div>
      )}
      <div className={`header-inner ${isShopper ? "commerce-header-inner" : ""}`}>
        <Link href="/" className="brand" aria-label="NUTRIFIT accueil">
          <span className="brand-mark">N</span>
          <span>NUTRIFIT <strong>Nutrition &amp; Performance</strong></span>
        </Link>
        {isShopper ? (
          <form className="commerce-search" role="search" onSubmit={searchCatalogue}>
            <input
              value={catalogSearch}
              onChange={(event) => setCatalogSearch(event.target.value)}
              placeholder="Rechercher un produit ou une marque..."
              aria-label="Rechercher un produit"
            />
            <button type="submit" aria-label="Lancer la recherche">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="11" cy="11" r="6.5" />
                <path d="m16 16 4 4" />
              </svg>
            </button>
          </form>
        ) : navigation}
        <div className={`header-actions ${!user ? "guest-actions" : ""}`}>
          {isShopper && <CommerceCartSummary user={user} />}
          {!loading && user ? (
            <>
              <NotificationBell />
              <span className="user-chip">{user.full_name || user.email.split("@")[0]}</span>
              <button className="link-button" onClick={() => { logout(); router.push("/"); }}>
                Sortir
              </button>
            </>
          ) : (
            <>
              <Link href="/register" className="button button-small button-outline">Créer un compte</Link>
              <Link href="/login" className="button button-small">Se connecter</Link>
            </>
          )}
        </div>
      </div>
      {isShopper && (
        <div className="commerce-nav-row">
          <div className="commerce-nav-inner">
            {navigation}
            <div className="category-shortcuts" aria-label="Catégories populaires">
              <Link href="/?category=proteines#catalogue">Protéines</Link>
              <Link href="/?category=creatine#catalogue">Créatine</Link>
              <Link href="/?category=vitamines#catalogue">Vitamines</Link>
              <Link href="/?category=bien-etre#catalogue">Bien-être</Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
