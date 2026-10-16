Discarded Arize runs (kept for audit, not numbers): is_scam came back from the Arize
dataset as a string, so bool("False") marked benign rows as scams in both the task and
evaluators. Fixed with _truthy(); the valid run is arize_experiment_20261016T153959Z.json.
Arize experiments with the bug: scam-rules-20261016T153717Z, scam-model-20261016T153825Z.
