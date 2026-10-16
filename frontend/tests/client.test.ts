import { ApiError, errorMessage } from "../src/api/client";

test("errorMessage without request id shows only the title", () => {
  expect(errorMessage(new ApiError(500, "Wewnętrzny błąd serwera.", null))).toBe("Wewnętrzny błąd serwera.");
});

test("errorMessage with request id appends it", () => {
  expect(errorMessage(new ApiError(500, "Błąd.", "abc"))).toBe("Błąd. (identyfikator żądania: abc)");
});

test("errorMessage for a network error", () => {
  expect(errorMessage(new TypeError("Failed to fetch"))).toBe("Nie udało się połączyć z serwerem.");
});
