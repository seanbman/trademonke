from datetime import datetime

from .models import Setup, SetupState, Transition

TERMINAL = {SetupState.INVALIDATED, SetupState.EXPIRED, SetupState.CANCELLED, SetupState.CLOSED}
ALLOWED = {
    SetupState.DETECTED: {SetupState.DEVELOPING, SetupState.INVALIDATED, SetupState.EXPIRED},
    SetupState.DEVELOPING: {SetupState.WATCH, SetupState.STRONG_WATCH, SetupState.ELIGIBLE, SetupState.INVALIDATED, SetupState.EXPIRED},
    SetupState.WATCH: {SetupState.STRONG_WATCH, SetupState.ELIGIBLE, SetupState.INVALIDATED, SetupState.EXPIRED},
    SetupState.STRONG_WATCH: {SetupState.ELIGIBLE, SetupState.INVALIDATED, SetupState.EXPIRED},
    SetupState.ELIGIBLE: {SetupState.AWAITING_APPROVAL, SetupState.ENTERED, SetupState.CANCELLED, SetupState.EXPIRED},
    SetupState.AWAITING_APPROVAL: {SetupState.ENTERED, SetupState.CANCELLED, SetupState.EXPIRED},
    SetupState.ENTERED: {SetupState.PARTIALLY_FILLED, SetupState.OPEN, SetupState.CANCELLED},
    SetupState.PARTIALLY_FILLED: {SetupState.OPEN, SetupState.CANCELLED},
    SetupState.OPEN: {SetupState.CLOSED},
}


def transition(setup: Setup, target: SetupState, timestamp: datetime, reason: str) -> None:
    if target not in ALLOWED.get(setup.state, set()):
        raise ValueError(f"invalid setup transition: {setup.state} -> {target}")
    previous = setup.state
    setup.state = target
    setup.transitions.append(Transition(previous, target, timestamp, reason))


def state_for_score(score: int, moderate: int = 4, strong: int = 5, eligible: int = 6) -> SetupState:
    if score >= eligible:
        return SetupState.ELIGIBLE
    if score >= strong:
        return SetupState.STRONG_WATCH
    if score >= moderate:
        return SetupState.WATCH
    return SetupState.DEVELOPING

