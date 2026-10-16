import { matchRoute } from "../src/router";

test.each([
  ["/contracts/:id", "/contracts/3", { id: 3 }],
  ["/contracts/:id/versions/:vid", "/contracts/3/versions/11", { id: 3, vid: 11 }],
  ["/contracts/:id/versions/:vid/analyses/:aid", "/contracts/3/versions/11/analyses/7", { id: 3, vid: 11, aid: 7 }],
  ["/contracts/:id/compare", "/contracts/3/compare", { id: 3 }],
  ["/analyses/:id", "/analyses/9", { id: 9 }],
])("matchRoute(%s, %s) → params", (pattern, path, params) => {
  expect(matchRoute(pattern, path)).toEqual(params);
});

test.each([
  ["/contracts/:id", "/contracts/0"],
  ["/contracts/:id", "/contracts/-1"],
  ["/contracts/:id", "/contracts/abc"],
  ["/contracts/:id", "/contracts/3/extra"],
  ["/contracts/:id", "/contracts/12345678901"],
  ["/contracts/:id/compare", "/contracts/3/porownaj"],
])("matchRoute(%s, %s) → null", (pattern, path) => {
  expect(matchRoute(pattern, path)).toBeNull();
});
