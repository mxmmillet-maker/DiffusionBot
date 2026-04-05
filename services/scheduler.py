import random
from datetime import datetime, timedelta


class HumanScheduler:
    """Genere des horaires de publication qui imitent un comportement humain."""

    HOUR_WEIGHTS = {
        8: 0.5, 9: 1.0, 10: 1.2, 11: 1.0, 12: 0.3,
        13: 0.5, 14: 1.0, 15: 1.2, 16: 1.0, 17: 0.8,
        18: 0.5, 19: 0.3, 20: 0.2, 21: 0.1,
    }

    def __init__(
        self,
        min_hour: int = 8,
        max_hour: int = 22,
        skip_days: list[int] | None = None,
    ):
        self.min_hour = min_hour
        self.max_hour = max_hour
        self.skip_days = skip_days if skip_days is not None else [6]  # dimanche

    def should_post_today(self, base_rate: int = 2) -> int:
        """Nombre de posts a faire aujourd'hui (variation autour de base_rate)."""
        today = datetime.now()
        if today.weekday() in self.skip_days:
            return 0
        count = max(0, int(random.gauss(base_rate, 0.7)))
        return min(count, base_rate + 1)

    def next_post_time(self) -> datetime:
        """Prochain horaire de publication avec distribution ponderee."""
        now = datetime.now()
        available = {h: w for h, w in self.HOUR_WEIGHTS.items() if h > now.hour}

        if not available:
            # Reporter a demain
            tomorrow = now + timedelta(days=1)
            hours = list(self.HOUR_WEIGHTS.keys())
            weights = list(self.HOUR_WEIGHTS.values())
            chosen = random.choices(hours, weights)[0]
            return tomorrow.replace(
                hour=chosen, minute=random.randint(0, 59),
                second=random.randint(0, 59), microsecond=0,
            )

        hours = list(available.keys())
        weights = list(available.values())
        chosen = random.choices(hours, weights)[0]
        return now.replace(
            hour=chosen, minute=random.randint(0, 59),
            second=random.randint(0, 59), microsecond=0,
        )

    def random_delay_seconds(self, min_h: float = 2, max_h: float = 6) -> int:
        """Delai entre deux posts (distribution gaussienne, en secondes)."""
        mean = (min_h + max_h) / 2 * 3600
        std = (max_h - min_h) / 4 * 3600
        delay = random.gauss(mean, std)
        return int(max(min_h * 3600, min(max_h * 3600, delay)))
