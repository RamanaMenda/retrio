"""Composable retry policy primitives.

The retry engine uses these helpers to keep its public config surface small
while allowing users to compose richer retry predicates and wait strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ._retry import RetryConfig, RetryState

RetryPredicateFn = Callable[[Any, Any | None, BaseException | None], bool]
WaitPolicyFn = Callable[[int, Any, Any | None, BaseException | None], float]
StopConditionFn = Callable[[Any], bool]


@dataclass
class RetryPredicate:
    """Composable retry predicate wrapper."""

    func: RetryPredicateFn
    name: str = "custom"

    def __call__(self, state: Any, value: Any | None = None, exc: BaseException | None = None) -> bool:
        return bool(self.func(state, value, exc))

    def __and__(self, other: RetryPredicate) -> RetryPredicate:
        return RetryPredicate(
            lambda state, value=None, exc=None: self(state, value, exc) and other(state, value, exc),
            name=f"({self.name} and {other.name})",
        )

    def __or__(self, other: RetryPredicate) -> RetryPredicate:
        return RetryPredicate(
            lambda state, value=None, exc=None: self(state, value, exc) or other(state, value, exc),
            name=f"({self.name} or {other.name})",
        )

    def __invert__(self) -> RetryPredicate:
        return RetryPredicate(lambda state, value=None, exc=None: not self(state, value, exc), name=f"not {self.name}")


@dataclass
class WaitPolicy:
    """Composable wait policy wrapper."""

    func: WaitPolicyFn
    name: str = "custom"

    def __call__(self, attempt: int, config: Any, state: Any | None = None, value: Any | None = None, exc: BaseException | None = None) -> float:
        return max(0.0, float(self.func(attempt, config, state, value, exc)))

    def __add__(self, other: WaitPolicy) -> WaitPolicy:
        return WaitPolicy(
            lambda attempt, config, state=None, value=None, exc=None: self(attempt, config, state, value, exc)
            + other(attempt, config, state, value, exc),
            name=f"({self.name} + {other.name})",
        )

    def bounded_by(self, maximum: float) -> WaitPolicy:
        return WaitPolicy(
            lambda attempt, config, state=None, value=None, exc=None: min(maximum, self(attempt, config, state, value, exc)),
            name=f"bounded({self.name}, {maximum})",
        )


@dataclass
class StopCondition:
    """Composable stop condition wrapper."""

    func: StopConditionFn
    name: str = "custom"

    def __call__(self, state: Any) -> bool:
        return bool(self.func(state))

    def __or__(self, other: StopCondition) -> StopCondition:
        return StopCondition(lambda state: self(state) or other(state), name=f"({self.name} or {other.name})")

    def __and__(self, other: StopCondition) -> StopCondition:
        return StopCondition(lambda state: self(state) and other(state), name=f"({self.name} and {other.name})")


def retry_if_exception_type(*exception_types: type[BaseException]) -> RetryPredicate:
    return RetryPredicate(
        lambda state, value=None, exc=None: exc is not None and isinstance(exc, exception_types),
        name="exception_type",
    )


def retry_if_result(predicate: Callable[[Any], bool]) -> RetryPredicate:
    return RetryPredicate(
        lambda state, value=None, exc=None: exc is None and predicate(value),
        name="result",
    )


def retry_any(*predicates: RetryPredicate) -> RetryPredicate:
    if not predicates:
        return RetryPredicate(lambda state, value=None, exc=None: False, name="false")
    combined = predicates[0]
    for predicate in predicates[1:]:
        combined = combined | predicate
    return combined


def retry_all(*predicates: RetryPredicate) -> RetryPredicate:
    if not predicates:
        return RetryPredicate(lambda state, value=None, exc=None: True, name="true")
    combined = predicates[0]
    for predicate in predicates[1:]:
        combined = combined & predicate
    return combined


def constant_wait(delay: float) -> WaitPolicy:
    return WaitPolicy(lambda attempt, config, state=None, value=None, exc=None: delay, name=f"constant({delay})")


def exponential_wait(
    initial_delay: float,
    multiplier: float,
    max_delay: float,
    jitter: str,
    random: Random,
) -> WaitPolicy:
    def compute(attempt: int, config: Any, state: Any | None = None, value: Any | None = None, exc: BaseException | None = None) -> float:
        delay = min(max_delay, initial_delay * (multiplier ** (attempt - 1)))
        if jitter == "none":
            return delay
        if jitter == "equal":
            return delay / 2 + random.random() * (delay / 2)
        return random.random() * delay

    return WaitPolicy(compute, name=f"exponential({initial_delay}, {multiplier})")


def chain_wait_policies(*policies: WaitPolicy) -> WaitPolicy:
    if not policies:
        return constant_wait(0.0)
    combined = policies[0]
    for policy in policies[1:]:
        combined = combined + policy
    return combined


def stop_after_attempt(max_attempts: int) -> StopCondition:
    return StopCondition(lambda state: state.attempt >= max_attempts, name=f"attempts>={max_attempts}")


def stop_after_delay(max_elapsed: float) -> StopCondition:
    return StopCondition(lambda state: state.elapsed >= max_elapsed, name=f"elapsed>={max_elapsed}")


def stop_any(*conditions: StopCondition) -> StopCondition:
    if not conditions:
        return StopCondition(lambda state: False, name="false")
    combined = conditions[0]
    for condition in conditions[1:]:
        combined = combined | condition
    return combined


def stop_all(*conditions: StopCondition) -> StopCondition:
    if not conditions:
        return StopCondition(lambda state: True, name="true")
    combined = conditions[0]
    for condition in conditions[1:]:
        combined = combined & condition
    return combined
