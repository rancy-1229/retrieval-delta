# Contributing

Start with a reproducible retrieval failure: a small source document, a question,
expected evidence, and ranked retrieved spans. Remove private information first.

Run `python -m unittest discover -s tests -v`. New metric changes should include
hand-calculated expected values or an independent oracle. Keep runtime dependencies
at zero unless an explicit design discussion demonstrates the need.

Useful contributions: real labeled public examples, tested export adapters,
alternative-evidence-set design, and large-input performance measurements.
Do not add provider-specific telemetry or silently infer source locations.
