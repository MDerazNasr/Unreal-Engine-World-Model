from pathlib import Path

import yaml


def _plan() -> dict[str, object]:
    path = Path(__file__).parents[2] / "configs" / "residual_collection_plan.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_collection_plan_has_disjoint_unique_episode_splits() -> None:
    plan = _plan()
    episodes = plan["episodes"]
    episode_ids = [episode["episode_id"] for episode in episodes]

    assert plan["schema_version"] == 1
    assert plan["frozen_before_training"] is True
    assert len(episode_ids) == len(set(episode_ids)) == 9
    assert {episode["split"] for episode in episodes} == {"train", "validation", "test"}
    assert [episode["episode_id"] for episode in episodes if episode["split"] == "test"] == [
        5301,
        5302,
    ]


def test_every_planned_schedule_is_valid_and_nonidentical() -> None:
    episodes = _plan()["episodes"]
    schedule_keys = (
        "motion_phase_duration_s",
        "intermediate_stop_duration_s",
        "final_stop_duration_s",
        "forward_speed_cm_s",
        "reverse_speed_cm_s",
        "lateral_speed_cm_s",
        "diagonal_component_speed_cm_s",
    )
    schedules = []
    for episode in episodes:
        values = tuple(float(episode[key]) for key in schedule_keys)
        assert all(value > 0.0 for value in values)
        schedules.append(values)

    assert len(schedules) == len(set(schedules))


def test_only_audited_episodes_are_accepted() -> None:
    plan = _plan()
    episodes = plan["episodes"]
    accepted = [episode for episode in episodes if episode["status"] == "accepted"]

    assert [episode["episode_id"] for episode in accepted] == [
        5101,
        5102,
        5103,
        5104,
        5105,
        5201,
    ]
    assert accepted[0]["raw_file"] == "episode_5101_20260902T203328Z_3ED1E0C50841.jsonl"
    assert accepted[0]["raw_sha256"] == (
        "eb437123d88dcf0c7b96b7f4fa5e2d75f502c2b70bc08408094b154693c3eaae"
    )
    assert accepted[1]["raw_file"] == "episode_5102_20260902T205700Z_941B611C954B.jsonl"
    assert accepted[1]["raw_sha256"] == (
        "a70492872c8b5d55cf669b500c44a703cba6d6e14d8bb21a057cd8efb67094b1"
    )
    assert accepted[2]["raw_file"] == "episode_5103_20260902T210855Z_6D0DE5726242.jsonl"
    assert accepted[2]["raw_sha256"] == (
        "59e4d5a2f0c6a2b2f4b3212d17335b8ead8a5d1f6ae947c86904e22f81626abf"
    )
    assert accepted[3]["raw_file"] == "episode_5104_20260902T212705Z_633B73409941.jsonl"
    assert accepted[3]["raw_sha256"] == (
        "3a67867880654362434c496c0f81a184bc77e4b3e0ac2237dfdfb6c0554b5427"
    )
    assert accepted[4]["raw_file"] == "episode_5105_20260902T215304Z_761D6EB9F04E.jsonl"
    assert accepted[4]["raw_sha256"] == (
        "d9e352128462909effb1b4ad45398a0db0a70aaeaef60f0ef874f09a063c2152"
    )
    assert accepted[5]["split"] == "validation"
    assert accepted[5]["raw_file"] == "episode_5201_20260902T220337Z_DBA8A0798A4E.jsonl"
    assert accepted[5]["raw_sha256"] == (
        "7ef1cc4756e2e49a0f94a15b61fc553e4f595dffebad85dd5ca86855d22336aa"
    )
    assert plan["rejected_attempts"] == [
        {
            "embedded_episode_id": 5201,
            "intended_configuration_episode_id": 5102,
            "reason": "training_configuration_recorded_under_reserved_validation_id",
            "raw_file": "episode_5201_20260902T204916Z_14E3988C3842.jsonl",
            "raw_sha256": (
                "4c5629c510fdb9a2ca15646694dd90950687e4e0a4b1bb87cab4333bccf79305"
            ),
        }
    ]
