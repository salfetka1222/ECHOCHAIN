"""Deterministic genome rules for the ECHOCHAIN universe."""
from dataclasses import asdict, dataclass
import hashlib
import json

TRAITS = ("stability", "energy", "resonance", "adaptation", "complexity")


@dataclass(frozen=True)
class Genome:
    stability: int = 50
    energy: int = 50
    resonance: int = 20
    adaptation: int = 25
    complexity: int = 10

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError(f"{name} must be an integer from 0 to 100")

    def to_dict(self) -> dict[str, int]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_json(cls, raw: str) -> "Genome":
        data = json.loads(raw)
        genome = cls(**data)
        genome.validate()
        return genome


def evolve(parent: Genome, artifact_code: str, generation: int) -> Genome:
    """Return a reproducible mutation based on artifact identity and generation."""
    parent.validate()
    if generation < 1:
        raise ValueError("generation must be >= 1")

    seed = f"ECHOCHAIN:v1:{artifact_code}:{generation}:{json.dumps(parent.to_dict(), sort_keys=True)}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    values = parent.to_dict()

    boost_index = digest[0] % len(TRAITS)
    penalty_index = digest[1] % len(TRAITS)
    if penalty_index == boost_index:
        penalty_index = (penalty_index + 1) % len(TRAITS)

    boost = TRAITS[boost_index]
    penalty = TRAITS[penalty_index]
    values[boost] = min(100, values[boost] + 3 + digest[2] % 6)
    values[penalty] = max(0, values[penalty] - (digest[3] % 3))
    return Genome(**values)
