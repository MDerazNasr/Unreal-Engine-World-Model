# R0.1 recovery baseline

Captured: 2026-09-03, Europe/Copenhagen
Source commit: `96d8879673300d4d53db9d8dfb0df78bac090d1e`
Branch: `feature/cem-runtime`

The source commit is the accepted offline interview package. At capture time the worktree contained
only intentional, uncommitted recovery-plan documentation changes. No tracked model, dataset,
planning artifact, evidence, implementation source, or test file differed from the source commit.

## Environment

- Machine architecture: Apple arm64
- macOS: 26.5.2 (`25F84`)
- Unreal Engine: 5.8.2, changelist `56702186`, branch `++UE5+Release-5.8`
- `uv`: 0.12.2
- Python: 3.12.13
- PyTorch: 2.13.0
- Current PyTorch default CPU threads: 4
- Frozen RUNTIME-001 benchmark threads: 1
- MPS: built and available; deterministic project tests and accepted model training use CPU

## Verified immutable hashes

| Artifact | SHA-256 |
|---|---|
| No-history checkpoint | `d979549b30bd01b3a304697074c295caf6c7fa16a4a8e25a08c15eec1da7a4f6` |
| Four-history checkpoint | `da4e2281c50b5ff329dd41ea3b02811ba634a35c461923c7afc240c11872c30f` |
| Accepted dataset manifest | `4c5d921194d339ba0617c930ce1ae41497ac5e04b14280c9ea8610bc3cc4d770` |
| OFFPLAN-001 summary | `8c54ed47b9f7ab684065a67526f2de6215f4710b8c02fb1c4c1dd1c7658cebed` |
| RUNTIME-001 result | `7fbf2696bebf038ecb93a8af8c4d5fbc663bfcc9671e087fca6ad737bcc55f42` |
| CEM-BUDGET-001 selection | `6a0da4bf1bed46a558b7bb6c1e55c4f5fc4db633d80082193371c2ea57fcfb14` |
| RESIDUAL-COMPRESS-001 result | `eaa2e136504e501019bf5d0e2512cc0f12774356ccfcbe19aba0dd040a7ecce7` |

## Validation

```text
uv run pytest
368 passed in 6.42s

uv run ruff check .
All checks passed!

uv run python scripts/verify_interview_package.py
interview_package=valid files=8 developer_paths=0

git diff --check
passed
```

The full test suite includes the residual-manifest regression that prohibits pending test entries
from containing observed file metadata. Frozen planning artifacts also report
`test_files_opened=0`.

## Claim boundary

This baseline verifies preservation and reproducibility of the accepted offline state. It adds no
live MPC, runtime, prediction, or control evidence.
