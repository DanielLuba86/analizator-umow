import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { NewVersionForm } from "../src/pages/NewVersionForm";
import { mockFetch, problem } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("adds a new version from a .md file read in the browser", async () => {
  const fetch = mockFetch([
    { method: "POST", path: "/api/contracts/3/versions", status: 201, body: { version_id: 12, nr: 3 } },
  ]);
  const onCreated = vi.fn();
  render(<NewVersionForm contractId={3} onCreated={onCreated} />);

  const file = new File(["§ 1. Aneks\nNowa treść umowy."], "aneks.md", { type: "text/markdown" });
  await userEvent.upload(screen.getByLabelText("Plik (.md, .txt)"), file);
  expect(screen.getByLabelText("Tekst nowej wersji")).toHaveValue("§ 1. Aneks\nNowa treść umowy.");
  await userEvent.click(screen.getByRole("button", { name: "Dodaj wersję" }));

  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(12));
  const [, init] = fetch.mock.calls[0];
  expect(JSON.parse(String(init?.body))).toEqual({ text: "§ 1. Aneks\nNowa treść umowy." });
});

test("rejects files other than .md and .txt", async () => {
  mockFetch([]);
  render(<NewVersionForm contractId={3} onCreated={vi.fn()} />);
  const file = new File(["x"], "umowa.html", { type: "text/html" });
  await userEvent.upload(screen.getByLabelText("Plik (.md, .txt)"), file, { applyAccept: false });
  expect(await screen.findByRole("alert")).toHaveTextContent("Obsługiwane są tylko pliki .md i .txt.");
  expect(screen.getByLabelText("Tekst nowej wersji")).toHaveValue("");
});

test("413 shows the server message", async () => {
  mockFetch([
    {
      method: "POST",
      path: "/api/contracts/3/versions",
      status: 413,
      body: problem(413, "Tekst umowy przekracza dopuszczalną długość.", "rid-1"),
    },
  ]);
  render(<NewVersionForm contractId={3} onCreated={vi.fn()} />);
  await userEvent.type(screen.getByLabelText("Tekst nowej wersji"), "bardzo długi tekst");
  await userEvent.click(screen.getByRole("button", { name: "Dodaj wersję" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Tekst umowy przekracza dopuszczalną długość.");
});


test("rejects file larger than limit before reading", async () => {
  mockFetch([]);
  render(<NewVersionForm contractId={3} onCreated={vi.fn()} />);
  const file = new File(["x"], "duza.md", { type: "text/markdown" });
  Object.defineProperty(file, "size", { value: 800_001 });
  const text = vi.spyOn(file, "text");
  await userEvent.upload(screen.getByLabelText("Plik (.md, .txt)"), file);
  expect(await screen.findByRole("alert")).toHaveTextContent("Plik jest za duży");
  expect(text).not.toHaveBeenCalled();
});

test("rejects text longer than 200000 chars", async () => {
  mockFetch([]);
  render(<NewVersionForm contractId={3} onCreated={vi.fn()} />);
  const file = new File(["a".repeat(200_001)], "dluga.md", { type: "text/markdown" });
  await userEvent.upload(screen.getByLabelText("Plik (.md, .txt)"), file);
  expect(await screen.findByRole("alert")).toHaveTextContent("200 000 znaków");
  expect(screen.getByLabelText("Tekst nowej wersji")).toHaveValue("");
});
