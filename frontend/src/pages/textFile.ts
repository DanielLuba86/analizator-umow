/** Limit znaków umowy z backendu (`max_contract_chars`). */
export const MAX_CONTRACT_CHARS = 200_000;
/** Najgorszy przypadek UTF-8: 4 bajty na znak — większego pliku nie ma sensu wczytywać. */
export const MAX_FILE_BYTES = 4 * MAX_CONTRACT_CHARS;

/** Czyta plik .md/.txt w przeglądarce jako tekst; inne rozszerzenia i za duże pliki odrzuca. */
export async function readTextFile(file: File): Promise<string> {
  if (!/\.(md|txt)$/i.test(file.name)) {
    throw new Error("Obsługiwane są tylko pliki .md i .txt.");
  }
  const tooLong = `Umowa może mieć najwyżej ${MAX_CONTRACT_CHARS.toLocaleString("pl-PL")} znaków.`;
  if (file.size > MAX_FILE_BYTES) throw new Error(`Plik jest za duży. ${tooLong}`);
  const text = await file.text();
  if (text.length > MAX_CONTRACT_CHARS) throw new Error(`Plik jest za duży. ${tooLong}`);
  return text;
}
