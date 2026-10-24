from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    mill_id: str = Field(..., description="Machine identifier, e.g., RS-01")
    signal: str = Field(..., description="Type of signal, e.g., motor_current")
    timestamp: str = Field(..., description="ISO-8601 timestamp in UTC")
    value: float = Field(..., description="Numeric sensor reading")
    unit: str = Field(..., description="Measurement unit")
    # Training-only labels; omitted from live stream when not set
    ground_truth_state: str | None = Field(
        default=None, description="FSM state at sample time (offline / training)"
    )
    pass_profile: str | None = Field(
        default=None, description="Pass fate: NORMAL / FALSE_ISSUE / COBBLE"
    )
