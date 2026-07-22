"use client";

import { useEffect, useState } from "react";

export function Toast() {
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    const listener = (event: Event) => {
      const custom = event as CustomEvent<string>;
      setMessage(custom.detail);
      setIsError(Boolean((custom as unknown as { error?: boolean }).error));
      window.setTimeout(() => setMessage(""), 2800);
    };
    window.addEventListener("toast", listener);
    return () => window.removeEventListener("toast", listener);
  }, []);

  if (!message) return null;
  return <div className={`toast ${isError ? "toast-error" : ""}`}>{message}</div>;
}
