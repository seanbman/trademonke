from dataclasses import dataclass


@dataclass
class KillSwitch:
    active: bool = False

    def engage(self) -> None:
        self.active = True

    def permits_new_entry(self) -> bool:
        return not self.active


def authorize(user_id: int, allowed_user_ids: set[int]) -> bool:
    return user_id in allowed_user_ids


def require_authorized(user_id: int, allowed_user_ids: set[int]) -> None:
    if not authorize(user_id, allowed_user_ids):
        raise PermissionError("Telegram user is not allowlisted")

