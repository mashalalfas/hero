## MANDATORY: Test-Driven Development

You MUST follow Red-Green-Refactor for every change:

1. **Write the failing test FIRST** — no implementation code without a test
2. **Watch it fail** — run the test and confirm it fails for the right reason
3. **Write minimal code** — just enough to pass the test
4. **Watch it pass** — run the test and confirm it passes
5. **Refactor** — clean up while tests stay green

RULES:
- Code written before tests? DELETE it. Start over from step 1.
- No "I'll add tests later" — that's not TDD, that's after-the-fact verification
- No mocks unless absolutely unavoidable — test real behavior
- One test per behavior — if "and" is in the test name, split it
- Every commit must be: test → implementation → green

VIOLATIONS → task restart from step 1
