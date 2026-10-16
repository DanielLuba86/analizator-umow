import { render, screen, waitFor } from "@testing-library/react";

import { AnalysisRedirect } from "../src/pages/AnalysisRedirect";
import { mockFetch, problem } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

test("redirects to the contract page with version and analysis", async () => {
  mockFetch([
    { path: "/api/analyses/7", body: { id: 7, version_id: 11 } },
    { path: "/api/versions/11", body: { id: 11, contract_id: 3 } },
  ]);
  render(<AnalysisRedirect analysisId={7} />);
  await waitFor(() => expect(window.location.hash).toBe("#/contracts/3/versions/11/analyses/7"));
});

test("unknown analysis shows the error", async () => {
  mockFetch([{ path: "/api/analyses/7", status: 404, body: problem(404, "Nie znaleziono analizy.", "r-9") }]);
  render(<AnalysisRedirect analysisId={7} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Nie znaleziono analizy.");
});
