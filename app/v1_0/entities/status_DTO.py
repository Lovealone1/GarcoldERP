from dataclasses import dataclass

@dataclass(slots=True)
class StatusDTO:
    id: int
    name: str