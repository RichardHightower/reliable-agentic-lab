---
id: T002
title: Customer search misses real names
state: draft
loop: none-live
---

# Customer search misses real names

Search on `/customers` and `GET /api/customers?q=` only returns a row when the
query is an exact, case-sensitive match on the full name.

Sales people type "ada" or "Meadows" and get nothing.

This is a known bug in the starter app. Do not implement it during the live
Saturday labs unless the room finishes early.
