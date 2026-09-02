"""Episode-safe construction of causal residual-learning examples."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from motionworld.data import ValidatedEpisode
from motionworld.dynamics.coordinates import YawRadians
from motionworld.dynamics.nominal_episode import (
    current_snapshot_nominal_inputs,
    observable_from_state_record,
)
from motionworld.dynamics.smooth_walking_nominal import smooth_walking_nominal_step
from motionworld.models.residual_contract import residual_difference
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_LENGTH,
    encode_residual_step_features,
    stack_residual_history,
)


@dataclass(frozen=True, slots=True)
class ResidualExample:
    """One supervised target with auditable episode and sequence provenance."""

    episode_id: int
    transition_sequence: int
    previous_sample_sequence: int
    next_sample_sequence: int
    history_transition_sequences: tuple[int, ...]
    features: NDArray[np.float64]
    target: NDArray[np.float64]

    def __post_init__(self) -> None:
        for name in ("features", "target"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.ndim != 1 or not np.isfinite(value).all():
                raise ValueError(f"{name} must be a finite one-dimensional vector")
            value = value.copy()
            value.setflags(write=False)
            object.__setattr__(self, name, value)


def _has_hidden_external_event(transition: dict[str, object]) -> bool:
    event = transition.get("external_perturbation")
    return isinstance(event, dict) and event.get("type") != "none"


def _validate_local_episode_chain(episode: ValidatedEpisode) -> None:
    previous_transition_sequence: int | None = None
    previous_next_sample: int | None = None
    for transition in episode.transitions:
        if int(transition["episode_id"]) != episode.episode_id:
            raise ValueError("transition episode ID does not match its episode")
        transition_sequence = int(transition["transition_sequence"])
        previous_sample = int(transition["previous_state"]["sample_sequence"])
        next_sample = int(transition["next_state"]["sample_sequence"])
        if next_sample != previous_sample + 1:
            raise ValueError("transition does not contain adjacent state samples")
        if previous_transition_sequence is not None:
            if transition_sequence != previous_transition_sequence + 1:
                raise ValueError("transition sequences are not consecutive")
            if previous_sample != previous_next_sample:
                raise ValueError("state sample sequence crosses a reset or gap")
        previous_transition_sequence = transition_sequence
        previous_next_sample = next_sample


def build_residual_examples(
    episode: ValidatedEpisode,
    *,
    history_length: int,
    exclude_hidden_external_events: bool = True,
) -> tuple[ResidualExample, ...]:
    """Build no-history or four-query examples without crossing episode boundaries."""

    if history_length not in (1, RESIDUAL_HISTORY_LENGTH):
        raise ValueError(f"history_length must be 1 or {RESIDUAL_HISTORY_LENGTH}")
    _validate_local_episode_chain(episode)

    step_features: list[NDArray[np.float64]] = []
    targets: list[NDArray[np.float64] | None] = []
    for transition in episode.transitions:
        inputs = current_snapshot_nominal_inputs(transition)
        nominal_next = smooth_walking_nominal_step(
            inputs.observable,
            inputs.internal,
            inputs.action,
            parameters=inputs.parameters,
            dt_s=inputs.dt_s,
        ).observable_next
        actual_next = observable_from_state_record(transition["next_state"])
        step_features.append(encode_residual_step_features(inputs, nominal_next))
        if exclude_hidden_external_events and _has_hidden_external_event(transition):
            targets.append(None)
        else:
            targets.append(
                residual_difference(
                    actual_next,
                    nominal_next,
                    reference_yaw=YawRadians(float(inputs.observable.facing_yaw_rad)),
                ).as_array()
            )

    examples: list[ResidualExample] = []
    first_index = history_length - 1
    for index in range(first_index, len(episode.transitions)):
        transition = episode.transitions[index]
        if exclude_hidden_external_events and _has_hidden_external_event(transition):
            continue
        target = targets[index]
        if target is None:
            raise AssertionError("eligible residual example is missing its target")
        history_start = index - history_length + 1
        history_rows = episode.transitions[history_start : index + 1]
        chronological_features = step_features[history_start : index + 1]
        features = (
            chronological_features[0]
            if history_length == 1
            else stack_residual_history(chronological_features)
        )
        examples.append(
            ResidualExample(
                episode_id=episode.episode_id,
                transition_sequence=int(transition["transition_sequence"]),
                previous_sample_sequence=int(
                    transition["previous_state"]["sample_sequence"]
                ),
                next_sample_sequence=int(transition["next_state"]["sample_sequence"]),
                history_transition_sequences=tuple(
                    int(row["transition_sequence"]) for row in history_rows
                ),
                features=features,
                target=target,
            )
        )
    return tuple(examples)


def build_residual_dataset(
    episodes: tuple[ValidatedEpisode, ...],
    *,
    history_length: int,
    exclude_hidden_external_events: bool = True,
) -> tuple[ResidualExample, ...]:
    """Combine independently windowed episodes and reject ambiguous episode IDs."""

    episode_ids = [episode.episode_id for episode in episodes]
    if len(set(episode_ids)) != len(episode_ids):
        raise ValueError("dataset episode IDs must be unique")
    return tuple(
        example
        for episode in episodes
        for example in build_residual_examples(
            episode,
            history_length=history_length,
            exclude_hidden_external_events=exclude_hidden_external_events,
        )
    )
