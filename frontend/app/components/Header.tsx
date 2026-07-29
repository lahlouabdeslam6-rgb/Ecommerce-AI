"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { NotificationBell } from "./NotificationBell";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const links = !user
    ? [["/", "Produits"], ["/cart", "Panier"], ["/orders", "Commandes"]]
    : user.role === "support"
      ? [["/", "Produits"], ["/support", "Espace support"], ["/account", "Compte"]]
      : user.role === "admin"
        ? [["/", "Produits"], ["/admin", "Administration"], ["/account", "Compte"]]
        : [["/", "Produits"], ["/cart", "Panier"], ["/orders", "Commandes"], ["/help", "Aide"], ["/account", "Compte"]];

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link href="/" className="brand" aria-label="NUTRIFIT accueil">
          <span className="brand-mark">N</span>
          <span>NUTRIFIT <strong>Nutrition &amp; Performance</strong></span>
        </Link>
        {links.length > 0 && (
          <nav className="main-nav" aria-label="Navigation principale">
            {links.map(([href, label]) => (
              <Link key={href} href={href} className={pathname === href ? "active" : ""}>
                {label}
              </Link>
            ))}
          </nav>
        )}
        <div className={`header-actions ${!user ? "guest-actions" : ""}`}>
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
    </header>
  );
}
