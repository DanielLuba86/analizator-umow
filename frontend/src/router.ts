import { useEffect, useState } from "react";

/** Minimalny router na `location.hash` (bez zależności): "#/contracts/3" → "/contracts/3". */
export function currentPath(): string {
  const path = window.location.hash.replace(/^#/, "");
  return path.startsWith("/") ? path : "/";
}

export function navigate(path: string): void {
  window.location.hash = `#${path}`;
}

export function useRoute(): string {
  const [path, setPath] = useState(currentPath);
  useEffect(() => {
    const onChange = () => setPath(currentPath());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return path;
}

/** Dopasowanie wzorca typu "/contracts/:id"; parametry tylko jako dodatnie liczby całkowite. */
export function matchRoute(pattern: string, path: string): Record<string, number> | null {
  const p = pattern.split("/");
  const s = path.split("/");
  if (p.length !== s.length) return null;
  const params: Record<string, number> = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(":")) {
      if (!/^[1-9]\d{0,9}$/.test(s[i])) return null;
      params[p[i].slice(1)] = Number(s[i]);
    } else if (p[i] !== s[i]) {
      return null;
    }
  }
  return params;
}
