import { test } from "node:test";
import assert from "node:assert/strict";
import { add, div } from "../src/calc.js";

test("add sums two numbers", () => assert.equal(add(2, 3), 5));
test("div divides", () => assert.equal(div(6, 3), 2));
test("div rejects zero", () => assert.throws(() => div(1, 0)));
