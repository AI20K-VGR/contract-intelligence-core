from pydantic import BaseModel, ConfigDict, Field, model_validator


class BBox(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self) -> "BBox":
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("bbox corners must be ordered")
        return self

    @classmethod
    def normalize(cls, box: list[float], width: float, height: float) -> "BBox":
        if width <= 0 or height <= 0:
            raise ValueError("positive dimensions required")
        values = [
            max(0.0, min(1.0, v / d))
            for v, d in zip(box, [width, height, width, height], strict=True)
        ]
        return cls(**dict(zip(["x1", "y1", "x2", "y2"], values, strict=True)))

    def iou(self, other: "BBox") -> float:
        intersection = max(0.0, min(self.x2, other.x2) - max(self.x1, other.x1)) * max(
            0.0, min(self.y2, other.y2) - max(self.y1, other.y1)
        )
        union = (
            (self.x2 - self.x1) * (self.y2 - self.y1)
            + (other.x2 - other.x1) * (other.y2 - other.y1)
            - intersection
        )
        return intersection / union if union else 0.0
