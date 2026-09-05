from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class PeriodDTO:
    """
    The range the server actually filtered on, echoed back to the caller.

    A client cannot derive this from its own clock: the boundaries are resolved
    in America/Bogota and the browser runs in the viewer's zone, so a label
    computed locally would disagree with the rows returned. `resolved_from`
    says which selector produced it, so a screen can print "Septiembre 2026"
    for a calendar month and an explicit range for a picker without guessing.
    """

    date_from: Optional[datetime]
    date_to: Optional[datetime]
    resolved_from: str  # "default" | "calendar" | "range" | "all"
