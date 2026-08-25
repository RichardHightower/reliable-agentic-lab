from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Score:
    ticket_id: str
    iteration: int
    passed: bool
    failed_node_ids: list[str] = field(default_factory=list)
    repeat_failure: bool = False
    gate: str = "retry"
    trace_id: str = ""
    pytest_exit_code: int = 1

    def to_dict(self) -> dict:
        return asdict(self)
