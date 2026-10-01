# Run artifacts

Each run creates a fresh directory containing resolved config, environment, input hashes, manifest snapshot, predictions, per-sample and summary CSVs, failure CSV/Markdown and a decision-support summary.

Real runs are ignored by Git because predictions and failure examples contain document text. Missing annotations produce blank accuracy values. Metrics always include sample counts. Synthetic smoke reports are explicitly named `synthetic_*` and do not establish quality on real contracts.
