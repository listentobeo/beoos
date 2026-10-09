import assert from "node:assert/strict";
import test from "node:test";
import { isPublicQuoteRequest } from "../lib/public-quote-route.ts";

const token = "a".repeat(64);

test("guests can view and accept a token-protected proposal", () => {
  assert.equal(isPublicQuoteRequest(["quotes", token], "GET"), true);
  assert.equal(isPublicQuoteRequest(["quotes", token, "accept"], "POST"), true);
  assert.equal(isPublicQuoteRequest(["quotes", "a_b-".repeat(11), "accept"], "POST"), true);
});

test("guest access is restricted to the public quote endpoints", () => {
  for (const method of ["PATCH", "PUT", "DELETE", "POST"]) {
    assert.equal(isPublicQuoteRequest(["quotes", token], method), false);
  }
  assert.equal(isPublicQuoteRequest(["quotes", token, "payment-link"], "POST"), false);
  assert.equal(isPublicQuoteRequest(["quotes", token, "accept", "extra"], "POST"), false);
  assert.equal(isPublicQuoteRequest(["quotes", "public", token], "GET"), false);
  assert.equal(isPublicQuoteRequest(["businesses", token, "quotes"], "GET"), false);
  assert.equal(isPublicQuoteRequest(["quotes", "short"], "GET"), false);
  assert.equal(isPublicQuoteRequest(["quotes", "../".repeat(15)], "GET"), false);
});
