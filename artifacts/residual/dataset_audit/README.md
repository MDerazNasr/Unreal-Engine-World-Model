# Accepted residual dataset audit

This report freezes the seven accepted train/validation files. The audit does not glob or open pending test files.

| Split | Episodes | Transitions | No history | Four history |
|---|---:|---:|---:|---:|
| train | 5 | 740 | 740 | 725 |
| validation | 2 | 283 | 283 | 277 |

## Accepted files

| Episode | Split | Rows | File | SHA-256 |
|---:|---|---:|---|---|
| 5101 | train | 130 | `episode_5101_20260902T203328Z_3ED1E0C50841.jsonl` | `eb437123d88dcf0c7b96b7f4fa5e2d75f502c2b70bc08408094b154693c3eaae` |
| 5102 | train | 156 | `episode_5102_20260902T205700Z_941B611C954B.jsonl` | `a70492872c8b5d55cf669b500c44a703cba6d6e14d8bb21a057cd8efb67094b1` |
| 5103 | train | 105 | `episode_5103_20260902T210855Z_6D0DE5726242.jsonl` | `59e4d5a2f0c6a2b2f4b3212d17335b8ead8a5d1f6ae947c86904e22f81626abf` |
| 5104 | train | 190 | `episode_5104_20260902T212705Z_633B73409941.jsonl` | `3a67867880654362434c496c0f81a184bc77e4b3e0ac2237dfdfb6c0554b5427` |
| 5105 | train | 159 | `episode_5105_20260902T215304Z_761D6EB9F04E.jsonl` | `d9e352128462909effb1b4ad45398a0db0a70aaeaef60f0ef874f09a063c2152` |
| 5201 | validation | 117 | `episode_5201_20260902T220337Z_DBA8A0798A4E.jsonl` | `7ef1cc4756e2e49a0f94a15b61fc553e4f595dffebad85dd5ca86855d22336aa` |
| 5202 | validation | 166 | `episode_5202_20260902T223029Z_A40FEF66DB4C.jsonl` | `34c3df8e3dbe893e7d89fdba001b8afd244af93dad2c2b3758b965feb5934ba1` |

## Coverage

### Train

- Requested directions: {'forward': 117, 'reverse': 115, 'right': 116, 'left': 113, 'diagonal': 111, 'stop': 168, 'other': 0}.
- Turning transitions: 568.
- Parameter-change transitions: 112.
- Actual speed median/p95/max: 74.834 / 144.250 / 154.841 cm/s.
- Timestep median/p95/max: 28.000 / 32.050 / 95.000 ms.
- Collision transitions: 0; external-event transitions: 0.

### Validation

- Requested directions: {'forward': 43, 'reverse': 44, 'right': 45, 'left': 40, 'diagonal': 50, 'stop': 61, 'other': 0}.
- Turning transitions: 222.
- Parameter-change transitions: 44.
- Actual speed median/p95/max: 75.547 / 143.134 / 149.988 cm/s.
- Timestep median/p95/max: 27.000 / 40.900 / 96.000 ms.
- Collision transitions: 0; external-event transitions: 0.

## Known limitations

- accepted train/validation episodes contain no collision transitions
- accepted train/validation episodes contain no external perturbation transitions
- only one deterministic eight-phase action family is represented
- final test episodes remain uncollected and unopened

## Reproduce

```bash
.venv/bin/python scripts/audit_residual_dataset.py \
  --raw-data-root "/path/to/GameAnimationSample/Saved/MotionWorld/Episodes" \
  --output-dir artifacts/residual/dataset_audit
```

## Scientific boundary

Normalization and model weights may use the training split only. Validation may compare predeclared model variants and checkpoints. Test episodes remain uncollected and are reserved for one final evaluation.
