from __future__ import annotations

import pytest

from motionworld.control.nominal_mpc_evidence import audit_nominal_mpc_live

SESSION = "ABCDEF123456"


def _raw(*, second_command="120.000000, 30.000000", move=True) -> bytes:
    position = "20.00, 4.00, 3.00" if move else "1.00, 2.00, 3.00"
    return "".join(
        [
            f"network evidence started: session={SESSION} controller=nominal_mpc\n",
            f"network reset boundary: session={SESSION} old_episode=-1 "
            "outstanding_observation=-1 action_state_cleared=true\n",
            "state sample: protocol=1 sequence=10 valid=true mover=1 sim_time_s=1.0 "
            "x resim=false mode=Walking position_world_cm=(1.00, 2.00, 3.00) "
            "velocity_world_cm_per_sec=(0.00, 0.00, 0.00) x "
            "angular_velocity_world_deg_per_sec=(0.00, 0.00, 0.00)\n",
            f"network episode started: session={SESSION} episode=7504 "
            "first_observation_sequence=0 applied_local_cm_per_sec=(0.00, 0.00) "
            "prior_state_cleared=true\n",
            "reset verified: episode=7504 attempts=1 state_sequence=10 x "
            "position_error_cm=0.000 facing_error_deg=0.000 "
            "linear_speed_cm_per_sec=0.000 angular_speed_deg_per_sec=0.000\n",
            f"network observation sent: session={SESSION} episode=7504 observation=0 "
            "state_sequence=10 simulation_time_s=1.000 previous_action_present=false\n",
            f"network action accepted: session={SESSION} episode=7504 source_observation=0 "
            "desired_local_cm_per_sec=(100.000000, 20.000000) "
            "unreal_end_to_end_latency_ms=50.0 current_identity_match=true before_deadline=true\n",
            "command echo: revision=1 finite=true requested_frame=(100.00, 20.00, 0.00) "
            "submitted_world=(100.00, 20.00, 0.00) echoed_world=(100.00, 20.00, 0.00) "
            "match=true\n",
            f"network observation sent: session={SESSION} episode=7504 observation=1 "
            "state_sequence=11 simulation_time_s=1.100 previous_action_present=true\n",
            f"network action accepted: session={SESSION} episode=7504 source_observation=1 "
            f"desired_local_cm_per_sec=({second_command}) "
            "unreal_end_to_end_latency_ms=60.0 current_identity_match=true before_deadline=true\n",
            "command echo: revision=2 finite=true requested_frame=(120.00, 30.00, 0.00) "
            "submitted_world=(120.00, 30.00, 0.00) echoed_world=(120.00, 30.00, 0.00) "
            "match=true\n",
            "state sample: protocol=1 sequence=11 valid=true mover=2 sim_time_s=1.1 "
            f"x resim=false mode=Walking position_world_cm=({position}) "
            "velocity_world_cm_per_sec=(10.00, 2.00, 0.00) x "
            "angular_velocity_world_deg_per_sec=(0.00, 0.00, 0.00)\n",
        ]
    ).encode()


def test_audit_accepts_bounded_identity_bound_motion() -> None:
    audit = audit_nominal_mpc_live(_raw(), SESSION, 7504)

    assert audit.observation_sequences == (0, 1)
    assert audit.accepted_sequences == (0, 1)
    assert audit.missing_action_sequences == ()
    assert audit.matched_action_echo_count == 2
    assert audit.maximum_planar_displacement_cm > 19.0
    assert audit.latency_summary()["p95"] == pytest.approx(59.5)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (_raw(second_command="0.000000, 0.000000"), "finite and nonzero"),
        (_raw(second_command="166.000000, 0.000000"), "165 cm/s"),
        (_raw().replace(b"before_deadline=true", b"before_deadline=false", 1), "accepted-action"),
        (
            _raw().replace(b"requested_frame=(100.00", b"requested_frame=(99.00", 1),
            "does not match",
        ),
        (_raw(move=False), "never displaced"),
        (_raw() + _raw(), "exactly once"),
    ],
)
def test_audit_rejects_unsafe_or_ambiguous_evidence(raw: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        audit_nominal_mpc_live(raw, SESSION, 7504)
