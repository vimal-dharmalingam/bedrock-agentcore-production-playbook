# 02 - Session Isolation & State

**Status:** Not started

The core Runtime differentiator: microVM-per-session hard isolation (Firecracker), session ID mechanics, and state persistence within a live session.

## What to cover here

- [ ] Session ID uniqueness/length requirements
- [ ] Prove two different session IDs can't see each other's state
- [ ] Demonstrate in-memory state and locally saved files persisting within one session
- [ ] Persistent filesystem across stop/resume cycles (distinct from in-session state)

## Notes

(Fill in as this is built -- real code, real errors, real fixes, same discipline as every other module in this repo.)
