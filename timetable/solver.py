"""Weekly timetable generator for one class.

Pure standard library, so it runs (and is tested) without Django. Sessions are laid on a
days x periods grid by a randomised greedy with restarts, then polished by hill climbing.
Hard rules are never broken; soft rules add the penalties in ``WEIGHTS`` (lower is better).
"""

import random
from dataclasses import dataclass, field
from datetime import time
from time import perf_counter

ALL = 'All'
NOON = time(12)
MIN_ATTEMPTS = 30     # greedy restarts always run, however small the time budget
RESTART_SHARE = 0.5   # part of the time budget spent on restarts; polishing uses the rest
TOP_K = 3             # a restart picks randomly among this many cheapest starts
POLISH_BEST = 5       # distinct restart results that get polished
POLISH_ROUNDS = 40
EPS = 1e-9

WEIGHTS = {
    'same_day_repeat': 50,   # per extra session of one course + kind + batch on a day
    'avoid_day': 40,
    'time_preference': 15,
    'gaps': 8,               # per idle period of a batch inside the class's day
    'imbalance': 4,          # times the variance of busy periods per day
    'long_stretch': 10,      # per period beyond max_consecutive, per batch and per teacher
    'first_period': 5,
    'last_period': 5,
}


@dataclass(frozen=True)
class Period:
    start: time
    end: time


@dataclass(frozen=True)
class Session:
    key: str
    course_id: int
    teacher_ids: tuple
    kind: str
    batch: str = ALL
    length: int = 1


@dataclass(frozen=True)
class Block:
    day: str
    start: time
    end: time


@dataclass
class Rules:
    teacher_busy: dict = field(default_factory=dict)
    class_blocked: list = field(default_factory=list)
    max_periods_per_day: int | None = None
    avoid_days: dict = field(default_factory=dict)
    preferred_time: dict = field(default_factory=dict)
    max_consecutive: int = 3
    avoid_first_period: bool = False
    avoid_last_period: bool = False


@dataclass(frozen=True)
class Placement:
    session_key: str
    day: str
    period: int
    start: time
    end: time


@dataclass
class Result:
    placements: list
    unplaced: list
    score: float
    breakdown: dict
    attempts: int


def _variance(values):
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _union(masks):
    out = 0
    for m in masks:
        out |= m
    return out


def _by_day(blocks):
    out = {}
    for b in blocks:
        out.setdefault(b.day, []).append(b)
    return out


class _Problem:
    """The inputs plus everything derived from them that stays fixed while searching."""

    def __init__(self, days, periods, sessions, rules):
        self.days, self.periods, self.sessions = list(days), list(periods), list(sessions)
        self.rules = rules or Rules()
        self._validate()
        self.joined = [a.end == b.start for a, b in zip(self.periods, self.periods[1:])]
        self.batches = sorted({s.batch for s in self.sessions} - {ALL})
        self.teachers = list(dict.fromkeys(t for s in self.sessions for t in s.teacher_ids))
        blocked = _by_day(self.rules.class_blocked)
        busy = {t: _by_day(b) for t, b in self.rules.teacher_busy.items()}
        self.windows, self.class_ok, self.static = [], [], []
        for s in self.sessions:
            runs = [p for p in range(len(self.periods) - s.length + 1)
                    if all(self.joined[p:p + s.length - 1])]
            wins = [(d, p) for d in range(len(self.days)) for p in runs]
            free = [w for w in wins if not self._clash(blocked, s, *w)]
            self.windows.append(wins)
            self.class_ok.append(free)
            self.static.append([w for w in free if not any(
                self._clash(busy.get(t, {}), s, *w) for t in s.teacher_ids)])
        self.allowed = [set(w) for w in self.static]
        self._local, self._info = {}, {}

    def _validate(self):
        if not self.days:
            raise ValueError('At least one day is needed.')
        if not self.periods:
            raise ValueError('At least one period is needed.')
        if len(set(self.days)) != len(self.days):
            raise ValueError('Each day may only be listed once.')
        if any(p.start >= p.end for p in self.periods):
            raise ValueError('Every period must end after it starts.')
        if any(b.start < a.end for a, b in zip(self.periods, self.periods[1:])):
            raise ValueError('Periods must be sorted by start time and must not overlap.')
        keys = set()
        for s in self.sessions:
            if s.key in keys:
                raise ValueError(f'Duplicate session key: {s.key!r}.')
            if s.length < 1:
                raise ValueError(f'Session {s.key!r} has length {s.length}; the minimum is 1.')
            keys.add(s.key)

    def _clash(self, by_day, s, d, p):
        start, end = self.periods[p].start, self.periods[p + s.length - 1].end
        return any(b.start < end and start < b.end for b in by_day.get(self.days[d], ()))

    def span(self, i, p):
        """Bitmask of the periods session ``i`` covers when it starts at period ``p``."""
        return ((1 << self.sessions[i].length) - 1) << p

    def local_parts(self, i, d, p):
        """Soft-rule categories hit by session ``i`` itself sitting at (d, p)."""
        s, r = self.sessions[i], self.rules
        parts = []
        if self.days[d] in r.avoid_days.get(s.course_id, ()):
            parts.append('avoid_day')
        pref = r.preferred_time.get(s.course_id)
        morning = self.periods[p].start < NOON
        if pref in ('morning', 'afternoon') and morning != (pref == 'morning'):
            parts.append('time_preference')
        if r.avoid_first_period and p == 0:
            parts.append('first_period')
        if r.avoid_last_period and p + s.length == len(self.periods):
            parts.append('last_period')
        return parts

    def local_cost(self, i, d, p):
        key = (i, d, p)
        if key not in self._local:
            self._local[key] = sum(WEIGHTS[c] for c in self.local_parts(i, d, p))
        return self._local[key]

    def info(self, mask):
        """(busy periods, first-to-last span, periods beyond max_consecutive) of a day mask."""
        if mask not in self._info:
            limit, run, over = self.rules.max_consecutive, 0, 0
            for i in range(len(self.periods)):
                if not mask >> i & 1:
                    run = 0
                    continue
                run = run + 1 if run and self.joined[i - 1] else 1
                over += run > limit
            span = mask.bit_length() - (mask & -mask).bit_length() + 1 if mask else 0
            self._info[mask] = (mask.bit_count(), span, over)
        return self._info[mask]


class _State:
    """A (partial) timetable that keeps running penalties so moves are cheap to score."""

    def __init__(self, prob):
        n = len(prob.days)
        self.prob = prob
        self.all = [0] * n
        self.batch = {b: [0] * n for b in prob.batches}
        self.teacher = {t: [0] * n for t in prob.teachers}
        self.teacher_over = [0] * n
        self.groups = {}
        self.repeats = [0] * n
        self.day_cost = [0] * n
        self.load = [0] * n
        self.local = 0
        self.where = {}

    def views(self, d):
        """Busy-period masks of day ``d`` as each batch sees it (All sessions included)."""
        if not self.batch:
            return [self.all[d]]
        return [self.all[d] | masks[d] for masks in self.batch.values()]

    def total(self):
        return self.local + sum(self.day_cost) + WEIGHTS['imbalance'] * _variance(self.load)

    def place(self, i, d, p):
        self.where[i] = (d, p)
        self._apply(i, d, p, 1)

    def remove(self, i, refresh=True):
        d, p = self.where.pop(i)
        self._apply(i, d, p, -1, refresh)

    def trial(self, i, d, p):
        """Penalty total with session ``i`` placed at (d, p); the state is left unchanged."""
        saved = self.day_cost[d], self.load[d]
        self.place(i, d, p)
        cost = self.total()
        self.remove(i, refresh=False)
        self.day_cost[d], self.load[d] = saved
        return cost

    def _apply(self, i, d, p, sign, refresh=True):
        """Add (sign 1) or take away (sign -1) session ``i`` at (d, p) and update penalties."""
        prob, s = self.prob, self.prob.sessions[i]
        m = prob.span(i, p)
        own = self.all if s.batch == ALL else self.batch[s.batch]
        own[d] = own[d] | m if sign > 0 else own[d] & ~m
        for t in s.teacher_ids:
            old = self.teacher[t][d]
            new = old | m if sign > 0 else old & ~m
            self.teacher[t][d] = new
            self.teacher_over[d] += prob.info(new)[2] - prob.info(old)[2]
        group = (s.course_id, s.kind, s.batch, d)
        before = self.groups.get(group, 0)
        self.groups[group] = before + sign
        self.repeats[d] += max(before + sign - 1, 0) - max(before - 1, 0)
        self.local += sign * prob.local_cost(i, d, p)
        if refresh:
            gaps, over, self.load[d] = self._day_parts(d)
            self.day_cost[d] = (WEIGHTS['gaps'] * gaps + WEIGHTS['long_stretch'] * over
                                + WEIGHTS['same_day_repeat'] * self.repeats[d])

    def _day_parts(self, d):
        """Gaps, long-stretch periods and load of day ``d``.

        A batch's gaps are its idle periods inside the class's day (first to last period anyone
        is busy), so batch A sitting idle while batch B is in a lab counts against A. This is
        what makes parallel batch labs win over staggered ones.
        """
        info = self.prob.info
        views = self.views(d)
        class_span = info(_union(views))[1]
        stats = [info(v) for v in views]
        gaps = sum(class_span - busy for busy, _, _ in stats)
        over = sum(o for _, _, o in stats) + self.teacher_over[d]
        return gaps, over, max(busy for busy, _, _ in stats)

    def taken(self, i, d):
        """Periods of day ``d`` already used by sessions that clash with session ``i``'s batch."""
        s = self.prob.sessions[i]
        if s.batch == ALL:
            return _union(self.views(d))
        return self.all[d] | self.batch[s.batch][d]

    def teacher_clash(self, i, d, p):
        """Whether a teacher of session ``i`` is busy elsewhere or in this class at (d, p)."""
        s, m = self.prob.sessions[i], self.prob.span(i, p)
        return (d, p) not in self.prob.allowed[i] or any(
            self.teacher[t][d] & m for t in s.teacher_ids)

    def cap_ok(self, i, d, p):
        cap = self.prob.rules.max_periods_per_day
        if cap is None:
            return True
        s = self.prob.sessions[i]
        views = self.views(d) if s.batch == ALL else [self.all[d] | self.batch[s.batch][d]]
        return all(v.bit_count() + s.length <= cap for v in views)

    def fits(self, i, d, p):
        """Whether session ``i`` can start at (d, p) without breaking any hard rule."""
        return ((d, p) in self.prob.allowed[i]
                and not self.taken(i, d) & self.prob.span(i, p)
                and not self.teacher_clash(i, d, p)
                and self.cap_ok(i, d, p))

    def place_best(self, i, rng=None, top_k=1):
        """Put session ``i`` at one of its cheapest free starts; False when none is free."""
        options = [(self.trial(i, d, p), d, p) for d, p in self.prob.static[i]
                   if self.fits(i, d, p)]
        if not options:
            return False
        if rng:
            rng.shuffle(options)
        options.sort(key=lambda o: o[0])
        _, d, p = rng.choice(options[:top_k]) if rng else options[0]
        self.place(i, d, p)
        return True

    def blockers(self, i, d, p):
        """Placed sessions that stop session ``i`` from starting at (d, p)."""
        s, m = self.prob.sessions[i], self.prob.span(i, p)
        out = []
        for j, (dj, pj) in self.where.items():
            o = self.prob.sessions[j]
            if dj == d and self.prob.span(j, pj) & m and (
                    ALL in (s.batch, o.batch) or s.batch == o.batch
                    or set(s.teacher_ids) & set(o.teacher_ids)):
                out.append(j)
        return out

    def breakdown(self):
        counts = dict.fromkeys(WEIGHTS, 0)
        for i, (d, p) in self.where.items():
            for category in self.prob.local_parts(i, d, p):
                counts[category] += 1
        for d in range(len(self.prob.days)):
            gaps, over, _ = self._day_parts(d)
            counts['gaps'] += gaps
            counts['long_stretch'] += over
        counts['same_day_repeat'] = sum(self.repeats)
        counts['imbalance'] = _variance(self.load)
        out = {}
        for category, n in counts.items():
            value = round(float(WEIGHTS[category] * n), 2)
            if value > 0:
                out[category] = value
        return out


def _construct(prob, rng, top_k):
    """One greedy pass: most constrained sessions first, each at a cheap free start."""
    st = _State(prob)
    order = sorted(range(len(prob.sessions)), key=lambda i: (
        -prob.sessions[i].length, len(prob.static[i]), rng.random()))
    missing = [i for i in order if not st.place_best(i, rng, top_k)]
    return st, missing


def _bump(st, i, rng):
    """Fit session ``i`` by moving the one or two sessions in its way somewhere else."""
    starts = st.prob.static[i]
    for d, p in rng.sample(starts, len(starts)):
        moved = st.blockers(i, d, p)
        if not moved or len(moved) > 2:
            continue
        old = {j: st.where[j] for j in moved}
        for j in moved:
            st.remove(j)
        if st.fits(i, d, p):
            st.place(i, d, p)
            if all(st.place_best(j) for j in moved):
                return True
            for j in moved:
                if j in st.where:
                    st.remove(j)
            st.remove(i)
        for j, (dj, pj) in old.items():
            st.place(j, dj, pj)
    return False


def _polish(st, missing, rng):
    """Hill climb: move or swap sessions while the penalty drops; retry unplaced ones."""
    sessions = st.prob.sessions
    for _ in range(POLISH_ROUNDS):
        missing[:] = [i for i in missing if not _bump(st, i, rng)]
        current, better = st.total(), False
        for i in rng.sample(list(st.where), len(st.where)):
            old = st.where[i]
            st.remove(i)
            st.place_best(i)
            if st.total() < current - EPS:
                current, better = st.total(), True
            else:
                st.remove(i)
                st.place(i, *old)
        placed = list(st.where)
        for a, i in enumerate(placed):
            for j in placed[a + 1:]:
                if sessions[i].length == sessions[j].length and st.where[i] != st.where[j]:
                    if _swap(st, i, j, current):
                        current, better = st.total(), True
        if not better:
            break


def _swap(st, i, j, current):
    """Swap the starts of sessions ``i`` and ``j`` if that is legal and lowers the penalty."""
    wi, wj = st.where[i], st.where[j]
    st.remove(i)
    st.remove(j)
    if st.fits(i, *wj):
        st.place(i, *wj)
        if st.fits(j, *wi):
            st.place(j, *wi)
            if st.total() < current - EPS:
                return True
            st.remove(j)
        st.remove(i)
    st.place(i, *wi)
    st.place(j, *wj)
    return False


def _reason(st, i):
    """Plain-language reason why session ``i`` could not be placed."""
    prob = st.prob
    s, n = prob.sessions[i], len(prob.periods)
    if not prob.windows[i]:
        if s.length > n:
            return f'Needs {s.length} periods in a row, but a day only has {n} periods'
        return (f'Needs {s.length} periods in a row, but every day has a break inside each '
                f'{s.length}-period window')
    free = [w for w in prob.class_ok[i] if st.cap_ok(i, *w)]
    if not free:
        return 'No free time left for the class'
    if all(st.teacher_clash(i, *w) for w in free):
        return 'The teacher is busy at every remaining free time'
    return 'No slot left without clashing with other sessions'


def generate(days, periods, sessions, rules=None, seed=0, time_budget=1.5):
    """Build a weekly timetable.

    Greedy restarts run for part of ``time_budget`` (at least ``MIN_ATTEMPTS`` of them), then
    the best few distinct results are polished and the best of those wins. The same seed and
    number of attempts always give the same result.
    """
    started = perf_counter()
    prob = _Problem(days, periods, sessions, rules)
    pool, attempts = [], 0
    while attempts < MIN_ATTEMPTS or perf_counter() - started < time_budget * RESTART_SHARE:
        rng = random.Random(f'{seed}:{attempts}')
        st, missing = _construct(prob, rng, 1 if attempts == 0 else TOP_K)
        missing = [i for i in missing if not _bump(st, i, rng)]
        pool.append(((len(missing), st.total(), attempts), st, missing))
        pool.sort(key=lambda entry: entry[0])
        del pool[3 * POLISH_BEST:]
        attempts += 1
        if not missing and st.total() < EPS:
            break
    best, seen = None, set()
    for _, st, missing in pool:
        layout = frozenset(st.where.items())
        if layout in seen:
            continue
        seen.add(layout)
        _polish(st, missing, random.Random(f'{seed}:polish'))
        key = (len(missing), st.total())
        if best is None or key < best[0]:
            best = (key, st, missing)
        if len(seen) == POLISH_BEST:
            break
    _, st, missing = best
    return _result(st, missing, attempts)


def _result(st, missing, attempts):
    prob = st.prob
    placements = []
    for i, (d, p) in sorted(st.where.items(), key=lambda item: (item[1], item[0])):
        s = prob.sessions[i]
        placements.append(Placement(s.key, prob.days[d], p, prob.periods[p].start,
                                    prob.periods[p + s.length - 1].end))
    unplaced = [(prob.sessions[i].key, _reason(st, i)) for i in sorted(missing)]
    breakdown = st.breakdown()
    total = round(sum(breakdown.values(), 0.0), 2)
    return Result(placements, unplaced, total, breakdown, attempts)


def score(days, periods, sessions, placements, rules):
    """Penalty total and per-category breakdown of an existing (e.g. hand-edited) timetable."""
    prob = _Problem(days, periods, sessions, rules)
    index = {s.key: i for i, s in enumerate(prob.sessions)}
    st = _State(prob)
    for pl in placements:
        i = index.get(pl.session_key)
        if i is None:
            raise ValueError(f'Unknown session key: {pl.session_key!r}.')
        if i in st.where:
            raise ValueError(f'Session {pl.session_key!r} is placed more than once.')
        if pl.day not in prob.days:
            raise ValueError(f'Unknown day: {pl.day!r}.')
        if not 0 <= pl.period <= len(prob.periods) - prob.sessions[i].length:
            raise ValueError(f'Session {pl.session_key!r} does not fit from period {pl.period}.')
        st.place(i, prob.days.index(pl.day), pl.period)
    breakdown = st.breakdown()
    return round(sum(breakdown.values(), 0.0), 2), breakdown
