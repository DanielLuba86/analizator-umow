export type Segment = { text: string; findingIds: number[] };
export type Range = { id: number; start: number; end: number };

/**
 * Dzieli tekst na kolejne segmenty w granicach wszystkich zakresów. Zakresy mogą się nakładać;
 * te poza tekstem są przycinane, a puste po przycięciu pomijane. Segmenty sklejone dają tekst.
 */
export function toSegments(text: string, ranges: Range[]): Segment[] {
  const clamp = (n: number) => Math.min(Math.max(n, 0), text.length);
  const valid = ranges
    .map((r) => ({ id: r.id, start: clamp(r.start), end: clamp(r.end) }))
    .filter((r) => r.start < r.end);

  const bounds = new Set([0, text.length]);
  for (const r of valid) {
    bounds.add(r.start);
    bounds.add(r.end);
  }
  const points = [...bounds].sort((a, b) => a - b);

  const segments: Segment[] = [];
  for (let i = 0; i + 1 < points.length; i++) {
    const [a, b] = [points[i], points[i + 1]];
    const findingIds = valid
      .filter((r) => r.start <= a && b <= r.end)
      .map((r) => r.id)
      .sort((x, y) => x - y);
    segments.push({ text: text.slice(a, b), findingIds });
  }
  return segments;
}
