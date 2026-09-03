# RUNTIME-001 planner latency

This benchmark times one complete offline Python CPU MPC call after three warm-ups. It excludes
dataset loading, Unreal communication, action application, rendering, and the second comparison
controller.

- Hardware: Apple arm64 Mac, Python 3.12.13, PyTorch 2.13.0 CPU with one thread.
- Frozen planner: 256 candidates, 32 elites, three CEM iterations, 15 planning steps, three
  dynamics substeps per step.
- Measurements: 30 calls per controller in alternating order.
- Deadline: 100 ms.
- Nominal: median 70.709 ms, p95 81.549 ms, 0/30 misses — passes the offline compute deadline.
- Residual: median 149.655 ms, p95 169.401 ms, 30/30 misses — fails the deadline.
- Test episodes opened: 0.

This is a useful negative result. Vectorization reduced the earlier paired-call diagnostic from
about 10 seconds to about 0.244 seconds without changing the selected first actions, but the
residual controller is still not ready for a 10 Hz live loop. Budget reduction, compilation, or a
faster inference backend must be evaluated against planning quality before deployment.
