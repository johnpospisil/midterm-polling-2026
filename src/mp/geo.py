"""US state names, postal codes, and race-id helpers."""

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

CYCLE = 2026


def race_id(office: str, state: str, district: str | None = None, cycle: int = CYCLE) -> str:
    """Build a race id like SEN-PA-2026, GOV-GA-2026, HOU-AZ06-2026, GEN-US-2026."""
    office = office.upper()
    if office not in {"SEN", "GOV", "HOU", "GEN"}:
        raise ValueError(f"unknown office {office!r}")
    if office == "HOU":
        if district is None:
            raise ValueError("House race ids need a district")
        d = "AL" if str(district).upper() in {"AL", "AT-LARGE", "0"} else f"{int(district):02d}"
        return f"HOU-{state}{d}-{cycle}"
    return f"{office}-{state}-{cycle}"
