import test from "node:test";
import assert from "node:assert/strict";
import { xCaption } from "../lib/x-text.ts";
test("X caption validation handles Latin, emoji and CJK weights", () => {
  assert.equal(xCaption("a".repeat(280)).valid, true);
  assert.equal(xCaption("a".repeat(281)).valid, false);
  assert.equal(xCaption("😀".repeat(140)).valid, true);
  assert.equal(xCaption("😀".repeat(141)).valid, false);
  assert.equal(xCaption("界".repeat(141)).valid, false);
});
test("X caption validation counts URLs and composed emoji correctly", () => {
  assert.equal(
    xCaption("https://example.com/" + "a".repeat(500)).weightedLength,
    23,
  );
  assert.equal(xCaption("👨‍👩‍👧‍👦").weightedLength, 2);
  assert.equal(xCaption("cafe\u0301").weightedLength, 4);
});
test("X caption validation rejects empty and invalid text", () => {
  assert.equal(xCaption("").valid, false);
  assert.equal(xCaption("bad\uFEFFtext").valid, false);
});
