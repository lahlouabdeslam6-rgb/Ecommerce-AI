"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { RecommendationResponse } from "../types";
import { ProductCard } from "./ProductCard";

type RecommendationSectionProps = {
  endpoint: string;
  title: string;
  subtitle: string;
  authenticated?: boolean;
  interactive?: boolean;
};

const objectives = [
  ["", "Tous les objectifs"],
  ["proteines", "Proteines"],
  ["prise de masse", "Prise de masse"],
  ["energie", "Energie"],
  ["recuperation", "Recuperation"],
  ["bien-etre", "Bien-etre"],
];

export function RecommendationSection({
  endpoint,
  title,
  subtitle,
  authenticated = false,
  interactive = false,
}: RecommendationSectionProps) {
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [objective, setObjective] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [appliedObjective, setAppliedObjective] = useState("");
  const [appliedMaxPrice, setAppliedMaxPrice] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ limit: "4" });
    if (appliedObjective) params.set("objective", appliedObjective);
    if (appliedMaxPrice) params.set("max_price", appliedMaxPrice);
    setLoading(true);
    setError("");
    api<RecommendationResponse>(
      `${endpoint}?${params.toString()}`,
      {},
      authenticated,
    )
      .then((response) => {
        if (active) setResult(response);
      })
      .catch((requestError: Error) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    endpoint,
    authenticated,
    appliedObjective,
    appliedMaxPrice,
  ]);

  const applyPreferences = (event: FormEvent) => {
    event.preventDefault();
    setAppliedObjective(objective);
    setAppliedMaxPrice(maxPrice);
  };

  return (
    <section className="recommendation-section shell">
      <div className="recommendation-heading">
        <div>
          <p className="kicker">Recommendation Agent</p>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <span className="recommendation-engine">
          {result?.strategy === "semantic+catalogue"
            ? "Qdrant + catalogue"
            : "Catalogue intelligent"}
        </span>
      </div>

      {interactive && (
        <form className="recommendation-controls" onSubmit={applyPreferences}>
          <label>
            <span>Objectif</span>
            <select
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
            >
              {objectives.map(([value, label]) => (
                <option value={value} key={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Budget max par produit</span>
            <input
              type="number"
              min="1"
              max="100000"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
              placeholder="Ex: 300 MAD"
            />
          </label>
          <button className="button button-secondary">Actualiser</button>
        </form>
      )}

      {error ? (
        <div className="recommendation-empty">
          Recommendations temporairement indisponibles.
        </div>
      ) : loading ? (
        <div className="recommendation-loading">
          {Array.from({ length: 4 }).map((_, index) => (
            <span key={index} />
          ))}
        </div>
      ) : result?.items.length ? (
        <>
          <div className="product-grid recommendation-grid">
            {result.items.map((item) => (
              <div className="recommendation-item" key={item.product.product_id}>
                <ProductCard product={item.product} />
                <div className="recommendation-reasons">
                  {item.reasons.slice(0, 2).map((reason) => (
                    <span key={reason}>{reason}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p className="recommendation-disclaimer">{result.disclaimer}</p>
        </>
      ) : (
        <div className="recommendation-empty">
          Ma l9inach produits disponibles kaynasbo had les criteres.
        </div>
      )}
    </section>
  );
}
