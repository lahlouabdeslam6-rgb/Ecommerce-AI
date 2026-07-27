import type { Metadata } from "next";
import { headers } from "next/headers";
import { AuthProvider } from "./components/AuthProvider";
import { AIShoppingAssistant } from "./components/AIShoppingAssistant";
import { Header } from "./components/Header";
import { Toast } from "./components/Toast";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") || "localhost:5173";
  const protocol = requestHeaders.get("x-forwarded-proto") || "http";
  const origin = `${protocol}://${host}`;
  const description =
    "NUTRIFIT, Nutrition & Performance. Fuel Your Body. Elevate Your Performance.";
  return {
    title: {
      default: "NUTRIFIT | Nutrition & Performance",
      template: "%s | NUTRIFIT",
    },
    description,
    icons: { icon: "/favicon.png", shortcut: "/favicon.png" },
    openGraph: {
      title: "NUTRIFIT | Nutrition & Performance",
      description,
      images: [{ url: `${origin}/nutrifit-hero.png`, width: 1684, height: 934 }],
    },
    twitter: {
      card: "summary_large_image",
      title: "NUTRIFIT | Nutrition & Performance",
      description,
      images: [`${origin}/nutrifit-hero.png`],
    },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>
        <AuthProvider>
          <Header />
          <main>{children}</main>
          <AIShoppingAssistant />
          <Toast />
        </AuthProvider>
      </body>
    </html>
  );
}
