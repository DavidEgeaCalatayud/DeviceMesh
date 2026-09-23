from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThresholdRule:
    metric_name: str
    operator: str
    threshold: float
    duration_seconds: int = 0

    def matches(self, value: float) -> bool:
        operations = {
            ">": lambda: value > self.threshold,
            ">=": lambda: value >= self.threshold,
            "<": lambda: value < self.threshold,
            "<=": lambda: value <= self.threshold,
        }
        try:
            return operations[self.operator]()
        except KeyError as exc:
            raise ValueError(f"unsupported operator: {self.operator}") from exc
