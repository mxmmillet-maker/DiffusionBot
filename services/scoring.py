from dataclasses import dataclass


@dataclass
class PlatformMetrics:
    da_actuel: float  # 0-100
    dofollow: bool
    taux_survie: float  # 0.0-1.0
    traffic_estime: float  # estimation traffic mensuel
    pertinence_thematique: float  # 0.0-1.0
    da_tendance: float  # variation DA sur 3 mois
    difficulte: float  # 0.0-1.0 (1.0 = facile)
    jours_depuis_dernier_post: int  # anciennete du dernier post sur cette plateforme


class PlatformScorer:
    """Score composite pondere pour classer les plateformes."""

    DEFAULT_WEIGHTS = {
        "da": 0.25,
        "dofollow": 0.20,
        "survie": 0.15,
        "fraicheur": 0.10,
        "pertinence": 0.10,
        "traffic": 0.10,
        "da_tendance": 0.05,
        "difficulte": 0.05,
    }

    def __init__(self, weights: dict | None = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def calculate_score(self, m: PlatformMetrics) -> float:
        """Retourne un score entre 0 et 100."""
        scores = {
            "da": min(m.da_actuel / 100.0, 1.0),
            "dofollow": 1.0 if m.dofollow else 0.3,
            "survie": m.taux_survie,
            "traffic": min(m.traffic_estime / 1_000_000, 1.0),
            "pertinence": m.pertinence_thematique,
            "da_tendance": max(0, (m.da_tendance + 10) / 20),
            "difficulte": m.difficulte,
            "fraicheur": min(m.jours_depuis_dernier_post / 30, 1.0),
        }
        total = sum(scores[k] * self.weights[k] for k in self.weights)
        return round(total * 100, 2)
