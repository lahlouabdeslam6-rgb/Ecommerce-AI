const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("ecommerce_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("ecommerce_token", token);
  else window.localStorage.removeItem("ecommerce_token");
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("ecommerce_refresh_token");
}

export function setTokens(accessToken: string | null, refreshToken: string | null) {
  setToken(accessToken);
  if (typeof window === "undefined") return;
  if (refreshToken) {
    window.localStorage.setItem("ecommerce_refresh_token", refreshToken);
  } else {
    window.localStorage.removeItem("ecommerce_refresh_token");
  }
}

async function refreshSession(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  const response = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!response.ok) {
    setTokens(null, null);
    return null;
  }
  const tokens = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  setTokens(tokens.access_token, tokens.refresh_token);
  return tokens.access_token;
}

export function assetUrl(path?: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  authenticated = false,
): Promise<T> {
  const headers = new Headers(options.headers);
  const bodyIsForm =
    options.body instanceof FormData || options.body instanceof URLSearchParams;
  if (options.body && !bodyIsForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated) {
    const token = getToken();
    if (!token) throw new Error("Vous devez vous connecter.");
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (authenticated && response.status === 401) {
    const renewedAccessToken = await refreshSession();
    if (renewedAccessToken) {
      headers.set("Authorization", `Bearer ${renewedAccessToken}`);
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        cache: "no-store",
      });
    }
  }
  if (response.status === 204) return undefined as T;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (authenticated && response.status === 401 && typeof window !== "undefined") {
      setTokens(null, null);
      const returnTo = window.location.pathname;
      window.location.assign(`/login?expired=1&returnTo=${encodeURIComponent(returnTo)}`);
      throw new Error("Votre session a expiré. Reconnectez-vous.");
    }
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg).join(", ")
      : detail || "Une erreur est survenue. Veuillez réessayer.";
    throw new Error(message);
  }
  return data as T;
}

export function money(value: number, currency = "MAD") {
  return new Intl.NumberFormat("fr-MA", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}
