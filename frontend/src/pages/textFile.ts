/** Czyta plik .md/.txt w przeglądarce jako tekst; inne rozszerzenia odrzuca. */
export async function readTextFile(file: File): Promise<string> {
  if (!/\.(md|txt)$/i.test(file.name)) {
    throw new Error("Obsługiwane są tylko pliki .md i .txt.");
  }
  return file.text();
}
