/** Powody kwarantanny z backendu (services/analysis.py) opisane zwykłymi słowami. */
const REASONS: Record<string, string> = {
  wstrzyknięcie: "w umowie wykryto możliwą próbę wstrzyknięcia poleceń",
  klasyfikator_niedostępny: "klasyfikator wstrzyknięć był niedostępny, więc umowy nie udało się sprawdzić",
};

export function quarantineReason(reason: unknown): string {
  return (typeof reason === "string" && REASONS[reason]) || "umowa nie przeszła kontroli bezpieczeństwa";
}
