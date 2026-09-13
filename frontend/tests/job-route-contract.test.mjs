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

// 2. Backward-compatible consolidated match redirect (/jobs/:id/match -> /discover/:id?tab=fit)
const matchTabResult = resolveRedirect("/discover/:id?tab=fit", { id: testId });
assert.strictEqual(matchTabResult, `/discover/${testId}?tab=fit`);
assert.notStrictEqual(matchTabResult, "/discover/:id?tab=fit", "Must not retain literal :id");

// 3. Numeric ID interpolation
const numericResult = resolveRedirect("/discover/:id", { id: "42" });
assert.strictEqual(numericResult, "/discover/42");

const numericMatchResult = resolveRedirect("/discover/:id?tab=fit", { id: "42" });
assert.strictEqual(numericMatchResult, "/discover/42?tab=fit");

console.log("All route parameter interpolation contract checks passed!");
