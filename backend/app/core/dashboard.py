"""The shape every module's dashboard answers with (DASH-001), so one screen draws them all.

A module computes its own figures from its own tables (`GET /api/v1/{module}/dashboard?period=3m`); the general dashboard
puts the modules' summaries side by side. A period is one of 1w, 1m, 3m (default), 6m, ytd, 1y; every card is compared
with the period just before it, of the same length, and shows today's figure next to it.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from datetime import date as Day  # a field named "date" would shadow the type in its own annotation
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Period = Literal["1w", "1m", "3m", "6m", "ytd", "1y"]
_DAYS = {"1w": 7, "1m": 30, "3m": 90, "6m": 182, "1y": 365}


@dataclass(frozen=True)
class Window:
    """The period [start, end) and the one before it, as dates (UTC days); `buckets` are the chart's points."""
    start: date
    end: date  # exclusive: tomorrow
    previous_start: date
    today: date
    weekly: bool

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def at(self, day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=timezone.utc)

    def buckets(self) -> list[date]:
        """Each day of the period, or each week (from its Monday) when the period is longer than three months."""
        step = 7 if self.weekly else 1
        first = self.start - timedelta(days=self.start.weekday()) if self.weekly else self.start
        out, day = [], first
        while day < self.end:
            out.append(day)
            day += timedelta(days=step)
        return out

    def bucket_of(self, day: date) -> date:
        return day - timedelta(days=day.weekday()) if self.weekly else day


def window(period: Period, today: date | None = None) -> Window:
    today = today or datetime.now(timezone.utc).date()
    end = today + timedelta(days=1)
    start = date(today.year, 1, 1) if period == "ytd" else end - timedelta(days=_DAYS[period])
    length = (end - start).days
    return Window(start=start, end=end, previous_start=start - timedelta(days=length), today=today, weekly=length > 92)


class Card(BaseModel):
    """One figure: this period, the period before (for the change), and today; `spark` is its small trend over the period.

    A "gauge" is a rate drawn as a dial (0–100 %, with the target when there is one); a "count" is a figure of now (open
    items), with no period to compare."""
    key: str
    value: Decimal | None
    previous: Decimal | None = None
    today: Decimal | None = None
    unit: str | None = None  # a unit code (kg) or "%" or "h"; the screen formats it
    good_when: Literal["up", "down"] = "up"  # whether a rise is good news (green) or bad (red)
    href: str | None = None
    style: Literal["tile", "gauge", "count"] = "tile"
    target: Decimal | None = None
    spark: list[Decimal] | None = None


class BreakdownItem(BaseModel):
    key: str  # a status, a category, a stage… the screen names it in its language; `label` when it is a name (a city)
    value: Decimal
    label: str | None = None


class Breakdown(BaseModel):
    """How a figure divides: a donut (shares of a whole), bars (largest first) or a funnel (stages in order)."""
    key: str
    style: Literal["donut", "bars", "funnel"] = "bars"
    unit: str | None = None
    items: list[BreakdownItem]


class RankItem(BaseModel):
    label: str
    value: Decimal
    detail: str | None = None
    href: str | None = None


class Ranking(BaseModel):
    """The first few of something (customers, products), largest first."""
    key: str
    unit: str | None = None
    items: list[RankItem]


class Point(BaseModel):
    date: Day
    value: Decimal


class Series(BaseModel):
    key: str
    unit: str | None = None
    points: list[Point]


class Attention(BaseModel):
    """Something that waits for someone: an overdue order, an open stop, a demand waiting for planning."""
    kind: str
    id: str | None = None
    label: str
    detail: str | None = None
    date: Day | None = None
    href: str | None = None
    severity: Literal["danger", "warning", "info"] = "warning"


class Dashboard(BaseModel):
    module: str
    period: Period
    start: Day
    end: Day
    cards: list[Card] = Field(default_factory=list)
    series: list[Series] = Field(default_factory=list)
    breakdowns: list[Breakdown] = Field(default_factory=list)
    rankings: list[Ranking] = Field(default_factory=list)
    attention: list[Attention] = Field(default_factory=list)
    attention_total: int = 0


# ── helpers every module uses ───────────────────────────────────────────────────────────────────────────────────────

def as_day(moment) -> date:
    """A date, or a datetime as its UTC day."""
    if isinstance(moment, datetime):
        return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).date()
    return moment


def tally(w: Window, by_day: dict) -> tuple[Decimal, Decimal, Decimal]:
    """(this period, the period before, today) of {day: amount}."""
    zero = Decimal(0)
    def total(first, last):
        return sum((Decimal(v) for d, v in by_day.items() if first <= d < last), zero)
    return total(w.start, w.end), total(w.previous_start, w.start), total(w.today, w.end)


def card(key: str, w: Window, by_day: dict, **extra) -> Card:
    """A card from {day: amount}: the period, the one before, today, and the trend over the period."""
    now, before, today = tally(w, by_day)
    return Card(key=key, value=now, previous=before, today=today, spark=[p.value for p in points(w, by_day)], **extra)


def points(w: Window, by_day: dict) -> list[Point]:
    """{day: amount} added up per point of the chart (per day, or per week for long periods)."""
    buckets = w.buckets()
    sums = {b: Decimal(0) for b in buckets}
    for d, v in by_day.items():
        if w.start <= d < w.end:
            b = w.bucket_of(d)
            if b in sums:
                sums[b] += Decimal(v)
    return [Point(date=b, value=sums[b]) for b in buckets]


def rate(part: Decimal, whole: Decimal) -> Decimal | None:
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1")) if whole else None


def count_by_day(days) -> dict:
    """[day, day, …] → {day: how many}."""
    out: dict = {}
    for d in days:
        out[d] = out.get(d, 0) + 1
    return out


def breakdown(key: str, rows, style="bars", unit=None, labels=None, limit=None) -> Breakdown:
    """[(key, value)] → a breakdown, largest first (a funnel keeps its order); zero values are left out."""
    items = [BreakdownItem(key=str(getattr(k, "value", k)), value=Decimal(v), label=(labels or {}).get(k)) for k, v in rows if v]
    if style != "funnel":
        items.sort(key=lambda i: i.value, reverse=True)
    return Breakdown(key=key, style=style, unit=unit, items=items[:limit] if limit else items)
