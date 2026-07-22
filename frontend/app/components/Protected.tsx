"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./AuthProvider";

type Role = "customer" | "support" | "admin";

export function Protected({
  children,
  admin = false,
  roles,
}: {
  children: React.ReactNode;
  admin?: boolean;
  roles?: Role[];
}) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const allowed = admin
    ? user?.role === "admin"
    : !roles || (!!user && roles.includes(user.role));

  useEffect(() => {
    if (!loading && (!user || !allowed)) router.replace(user ? "/" : "/login");
  }, [user, loading, allowed, router]);

  if (loading || !user || !allowed) {
    return <div className="page-loading">Chargement de votre espace...</div>;
  }
  return <>{children}</>;
}
