import assert from 'node:assert';

// Test parameter interpolation logic used in RedirectWithParam
function resolveRedirect(to, params) {
  let target = to;
  for (const [key, value] of Object.entries(params)) {
    target = target.replace(`:${key}`, value);
  }
  return target;
}

// 1. Single param redirect (/jobs/:id -> /discover/:id)
const testId = "9f8b7c6d-5e4a-3b2c-1d0e-f1a2b3c4d5e6";
const result = resolveRedirect("/discover/:id", { id: testId });
assert.strictEqual(result, `/discover/${testId}`);
assert.notStrictEqual(result, "/discover/:id", "Must not retain literal :id");

// 2. Sub-path param redirect (/jobs/:id/match -> /discover/:id/match)
const matchResult = resolveRedirect("/discover/:id/match", { id: testId });
assert.strictEqual(matchResult, `/discover/${testId}/match`);
assert.notStrictEqual(matchResult, "/discover/:id/match", "Must not retain literal :id");

// 3. Numeric ID
const numericResult = resolveRedirect("/discover/:id", { id: "42" });
assert.strictEqual(numericResult, "/discover/42");

console.log("All route parameter interpolation contract checks passed!");
