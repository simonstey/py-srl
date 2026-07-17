# Product

## Register

product

## Users

RDF / SHACL practitioners, spec authors, and W3C data-shapes contributors evaluating
how faithfully `shacl-rules` (py-srl) implements the SHACL 1.2 Shape Rule Language.
Two contexts of use:

- **Auditing conformance** — reading the generated implementation report to see which
  W3C test-suite cases pass, fail, or can't-tell, and inspecting the source and the
  actually-inferred triples per test.
- **Trying SRL live** — writing rules + RDF data in the browser and watching the engine
  infer new triples to a fixed point, with per-triple provenance. Used to learn the
  language, sanity-check a rule, or build a minimal repro before filing a spec issue.

The job: *trust the implementation, and reason about SRL without installing anything.*

## Product Purpose

`shacl-rules` is a Python parser + fixed-point evaluation engine for W3C SHACL 1.2
Rules. `tests/run_shacl_rules_tests.py` runs the bundled W3C test suite and emits an
EARL report plus a self-contained HTML conformance report. This project adds an
**interactive SRL playground** to that HTML report — powered by the `srl-engine`
JavaScript library (same author, same spec) running entirely client-side — and serves
the report + playground together via GitHub Pages. Success: a visitor can read the
latest conformance results and, on the same page, author and evaluate SRL rules with
zero setup, seeing exactly which rule inferred which triple.

## Brand Personality

Precise, trustworthy, technical. Confident and spec-accurate; restraint over
decoration; the results carry the page. The tone of a conformance dashboard you would
trust enough to file a W3C issue from. Voice is exact and unembellished — the same
register as the existing report and CLI output.

## Anti-references

- Generic SaaS landing pages: hero-metric templates, gradient-text headings, tracked
  uppercase eyebrows over every section, identical icon-card grids.
- Toy/gamified "code sandbox" chrome — cartoonish run buttons, confetti, mascot.
- Playgrounds that hide errors or fail silently. Diagnostics must be first-class,
  line-referenced, and honest (mirrors the engine's own validation categories).
- Heavy client frameworks or build steps in the shipped report. The HTML report is a
  single self-contained file today; the playground must not turn it into an app bundle.

## Design Principles

- **Practice what you preach.** A SHACL-Rules conformance tool must itself be exact,
  legible, and correct. Diagnostics, provenance, and pass/fail states are the product.
- **One system, extended.** The playground inherits the report's existing design tokens
  (OKLCH restrained palette, light/dark, semantic state colors) rather than inventing a
  second visual language on the same page.
- **Zero-setup honesty.** Everything runs client-side from a static file. No server, no
  telemetry, no hidden state. What you see inferred is what the engine actually produced.
- **Teach by default, not by tutorial.** Preset scenarios and readable empty states let
  a newcomer understand SRL from the first open, without a separate docs detour.
- **Spec-conformant core, clearly-fenced extensions.** The opt-in FOR-IN shape-targeting
  feature is visibly marked non-W3C-spec, never blurred into the conformant surface.

## Accessibility & Inclusion

WCAG 2.1 AA. Body text ≥4.5:1 in both themes (the report tokens already target this).
Full keyboard operability for editors, run controls, presets, and filters; visible
focus-visible rings. Semantic landmarks and labels; state changes (validation result,
run outcome) announced to assistive tech. Honor `prefers-reduced-motion` (the report
already gates all animation behind it). Honor `prefers-color-scheme` with a manual
override, matching the report's existing theme toggle.
