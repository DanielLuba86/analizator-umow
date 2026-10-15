import { toSegments } from "../src/document/segments";

test("splits on overlapping ranges", () => {
  expect(toSegments("abcdef", [{ id: 1, start: 1, end: 4 }, { id: 2, start: 3, end: 5 }])).toEqual([
    { text: "a", findingIds: [] },
    { text: "bc", findingIds: [1] },
    { text: "d", findingIds: [1, 2] },
    { text: "e", findingIds: [2] },
    { text: "f", findingIds: [] },
  ]);
});

test("clamps out-of-range", () => {
  expect(
    toSegments("abc", [
      { id: 1, start: -5, end: 2 },
      { id: 2, start: 2, end: 99 },
      { id: 3, start: 10, end: 20 },
      { id: 4, start: 2, end: 1 },
    ]),
  ).toEqual([
    { text: "ab", findingIds: [1] },
    { text: "c", findingIds: [2] },
  ]);
});

test("no ranges gives the whole text as one segment", () => {
  expect(toSegments("abc", [])).toEqual([{ text: "abc", findingIds: [] }]);
  expect(toSegments("", [{ id: 1, start: 0, end: 3 }])).toEqual([]);
});

test("identical ranges share segments and ids are sorted", () => {
  expect(toSegments("abcd", [{ id: 7, start: 0, end: 2 }, { id: 3, start: 0, end: 2 }])).toEqual([
    { text: "ab", findingIds: [3, 7] },
    { text: "cd", findingIds: [] },
  ]);
});

test("segments concatenate back to the original text", () => {
  const text = "§ 1. Przedmiot\nNajemca zapłaci karę.";
  const ranges = [
    { id: 1, start: 5, end: 20 },
    { id: 2, start: 0, end: 9 },
    { id: 3, start: 18, end: 40 },
  ];
  expect(
    toSegments(text, ranges)
      .map((s) => s.text)
      .join(""),
  ).toBe(text);
});
