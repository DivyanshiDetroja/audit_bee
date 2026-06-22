# Operating rules for building Audit Bee

1. DESIGN.md is the single source of truth. Read it before doing any work on a
   phase. If a prompt, or your own plan, conflicts with DESIGN.md, DESIGN.md
   wins — and tell me about the conflict before proceeding.

2. When ANYTHING is ambiguous or you are unsure how to proceed, ask me directly
   before writing code. Do not guess and do not silently assume. A wrong
   assumption costs more than a question. It is always correct to stop and ask.

3. Work ONE phase at a time. When a phase is complete:
   - Stop.
   - Summarize exactly what you built and changed.
   - Give me precise steps to test it: commands to run, what to click, and what
     I should expect to see.
   - Do NOT begin the next phase until I confirm it works and I've made any
     changes I want.

4. Keep every change scoped to the current phase. Do not scaffold ahead, and do
   not refactor unrelated code without asking.

5. Security is non-negotiable. Every endpoint that reads or mutates client data
   MUST enforce object-level authorization per DESIGN.md Section 5.2, and
   unauthorized access to a resource returns 404 (not 403). If you are ever
   unsure whether an endpoint is properly scoped, stop and ask.