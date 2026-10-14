"""Tests for the timetable solver; plain unittest, no Django needed."""

import unittest
from datetime import time
from time import perf_counter

from timetable.solver import Block, Period, Placement, Rules, Session, generate, score

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


def period(start, end):
    return Period(time.fromisoformat(start), time.fromisoformat(end))


# 09-11, short break, 11:15-13:15, lunch, 14-17.
WEEK = [period('09:00', '10:00'), period('10:00', '11:00'), period('11:15', '12:15'),
        period('12:15', '13:15'), period('14:00', '15:00'), period('15:00', '16:00'),
        period('16:00', '17:00')]


def lecture(key, course, teacher):
    return Session(key, course, (teacher,), 'Lecture')


def lab(key, course, teacher, batch, length=2):
    return Session(key, course, (teacher,), 'Lab', batch, length)


def realistic_sessions():
    """5 courses x 3 lectures, plus 2 courses whose 2-period labs run per batch A/B."""
    sessions = [lecture(f'{c}-L{n}', c, c) for c in range(1, 6) for n in range(1, 4)]
    for course, teachers in ((6, (6, 7)), (7, (8, 9))):
        for batch, teacher in zip('AB', teachers):
            sessions.append(lab(f'{course}-{batch}', course, teacher, batch))
    return sessions


def overlap(a, b):
    return a.day == b.day and a.start < b.end and b.start < a.end


class SolverTestCase(unittest.TestCase):

    def assertValid(self, days, periods, sessions, rules, result):
        """Check every hard rule independently of the solver's own bookkeeping."""
        rules = rules or Rules()
        by_key = {s.key: s for s in sessions}
        placed = {}
        for pl in result.placements:
            s = by_key[pl.session_key]
            last = pl.period + s.length - 1
            self.assertNotIn(s.key, placed)
            self.assertIn(pl.day, days)
            self.assertLess(last, len(periods))
            for q in range(pl.period, last):
                self.assertEqual(periods[q].end, periods[q + 1].start, f'{s.key} spans a break')
            self.assertEqual((pl.start, pl.end), (periods[pl.period].start, periods[last].end))
            placed[s.key] = pl
        unplaced = {key for key, _ in result.unplaced}
        self.assertFalse(unplaced & set(placed))
        self.assertEqual(unplaced | set(placed), set(by_key))

        def clashes(blocks, pl):
            return any(b.day == pl.day and b.start < pl.end and pl.start < b.end for b in blocks)

        for key, pl in placed.items():
            self.assertFalse(clashes(rules.class_blocked, pl), f'{key} is in blocked time')
            for t in by_key[key].teacher_ids:
                self.assertFalse(clashes(rules.teacher_busy.get(t, []), pl), f'{key}: teacher busy')
        items = list(placed.values())
        for n, a in enumerate(items):
            for b in items[n + 1:]:
                if not overlap(a, b):
                    continue
                sa, sb = by_key[a.session_key], by_key[b.session_key]
                self.assertTrue('All' not in (sa.batch, sb.batch) and sa.batch != sb.batch,
                                f'{sa.key} overlaps {sb.key}')
                self.assertFalse(set(sa.teacher_ids) & set(sb.teacher_ids),
                                 f'{sa.key} and {sb.key} share a teacher')
        if rules.max_periods_per_day is not None:
            batches = {s.batch for s in sessions} - {'All'} or {'All'}
            for day in days:
                for batch in batches:
                    busy = sum(by_key[k].length for k, pl in placed.items()
                               if pl.day == day and by_key[k].batch in ('All', batch))
                    self.assertLessEqual(busy, rules.max_periods_per_day, f'{day} {batch}')

    def by_key(self, result):
        return {pl.session_key: pl for pl in result.placements}


class HardRuleTests(SolverTestCase):

    def test_no_double_booking_and_labs_stay_inside_one_stretch(self):
        sessions = realistic_sessions() + [
            lab('8-A', 8, 1, 'A', 3),   # teacher 1 also teaches the course-1 lectures
            lab('8-B', 8, 2, 'B', 3),
            lab('9-C', 9, 3, 'C'),
        ]
        for seed in range(3):
            result = generate(DAYS, WEEK, sessions, seed=seed, time_budget=0)
            self.assertEqual(result.unplaced, [])
            self.assertValid(DAYS, WEEK, sessions, None, result)
            # A 3-period lab only fits in the unbroken 14:00-17:00 stretch.
            for key in ('8-A', '8-B'):
                self.assertEqual(self.by_key(result)[key].start, time(14))

    def test_teacher_busy_and_class_blocked_are_respected(self):
        sessions = realistic_sessions()
        rules = Rules(
            teacher_busy={1: [Block('Monday', time(9), time(17)),
                              Block('Tuesday', time(9), time(12))],
                          6: [Block('Wednesday', time(9), time(17))]},
            class_blocked=[Block('Wednesday', time(14), time(17)),
                           Block('Thursday', time(10, 30), time(10, 45)),
                           Block('Friday', time(9), time(11))],
        )
        result = generate(DAYS, WEEK, sessions, rules, time_budget=0)
        self.assertEqual(result.unplaced, [])
        self.assertValid(DAYS, WEEK, sessions, rules, result)
        for pl in result.placements:
            self.assertFalse(pl.day == 'Thursday' and pl.start == time(10))

    def test_max_periods_per_day(self):
        sessions = realistic_sessions()   # each batch needs 19 periods, the cap allows 20
        rules = Rules(max_periods_per_day=4)
        result = generate(DAYS, WEEK, sessions, rules, time_budget=0)
        self.assertEqual(result.unplaced, [])
        self.assertValid(DAYS, WEEK, sessions, rules, result)


class SoftRuleTests(SolverTestCase):

    def test_batch_labs_run_in_parallel(self):
        periods = WEEK[:4]
        sessions = [lab('1-A', 1, 1, 'A'), lab('1-B', 1, 2, 'B'),
                    lab('2-A', 2, 3, 'A'), lab('2-B', 2, 4, 'B')]
        result = generate(DAYS[:3], periods, sessions, time_budget=0)
        self.assertEqual(result.unplaced, [])
        placed = self.by_key(result)
        pairs = [(a, b) for a in ('1-A', '2-A') for b in ('1-B', '2-B')
                 if overlap(placed[a], placed[b])]
        self.assertTrue(pairs)
        self.assertEqual(len(pairs), 2)   # every A lab runs alongside a B lab
        self.assertNotIn('gaps', result.breakdown)

    def test_lectures_of_a_course_go_on_different_days(self):
        sessions = realistic_sessions()
        result = generate(DAYS, WEEK, sessions, time_budget=0)
        placed = self.by_key(result)
        for course in range(1, 6):
            days = [placed[f'{course}-L{n}'].day for n in range(1, 4)]
            self.assertEqual(len(set(days)), 3)
        self.assertNotIn('same_day_repeat', result.breakdown)

    def test_avoid_days(self):
        sessions = realistic_sessions()
        rules = Rules(avoid_days={1: {'Monday', 'Tuesday'}, 6: {'Friday'}})
        result = generate(DAYS, WEEK, sessions, rules, time_budget=0)
        course = {s.key: s.course_id for s in sessions}
        for pl in result.placements:
            self.assertNotIn(pl.day, rules.avoid_days.get(course[pl.session_key], ()))
        self.assertNotIn('avoid_day', result.breakdown)

    def test_preferred_time(self):
        sessions = realistic_sessions()
        rules = Rules(preferred_time={1: 'morning', 2: 'afternoon'})
        result = generate(DAYS, WEEK, sessions, rules, time_budget=0)
        course = {s.key: s.course_id for s in sessions}
        for pl in result.placements:
            if course[pl.session_key] == 1:
                self.assertLess(pl.start, time(12))
            if course[pl.session_key] == 2:
                self.assertGreaterEqual(pl.start, time(12))


class UnplacedTests(SolverTestCase):

    def test_teacher_busy_all_week(self):
        sessions = realistic_sessions() + [lecture('9-L1', 9, 99)]
        rules = Rules(teacher_busy={99: [Block(day, time(8), time(18)) for day in DAYS]})
        result = generate(DAYS, WEEK, sessions, rules, time_budget=0)
        self.assertEqual(result.unplaced,
                         [('9-L1', 'The teacher is busy at every remaining free time')])
        self.assertEqual(len(result.placements), len(sessions) - 1)
        self.assertValid(DAYS, WEEK, sessions, rules, result)

    def test_no_window_without_a_break(self):
        periods = [WEEK[1], WEEK[3], WEEK[4]]   # 10-11, 12:15-13:15, 14-15: all split by breaks
        result = generate(DAYS, periods, [lab('1-A', 1, 1, 'A')], time_budget=0)
        self.assertEqual(result.unplaced, [('1-A', 'Needs 2 periods in a row, but every day '
                                                   'has a break inside each 2-period window')])

    def test_class_has_no_free_time(self):
        rules = Rules(class_blocked=[Block(day, time(9), time(17)) for day in DAYS])
        result = generate(DAYS, WEEK, [lecture('1-L1', 1, 1)], rules, time_budget=0)
        self.assertEqual(result.unplaced, [('1-L1', 'No free time left for the class')])

    def test_day_cap_leaves_no_room(self):
        sessions = [lecture('1-L1', 1, 1), lecture('2-L1', 2, 2)]
        rules = Rules(max_periods_per_day=1)
        result = generate(DAYS[:1], WEEK, sessions, rules, time_budget=0)
        self.assertEqual(len(result.placements), 1)
        self.assertEqual(result.unplaced[0][1], 'No free time left for the class')

    def test_clashes_with_other_sessions(self):
        sessions = [lecture('1-L1', 1, 1), lecture('2-L1', 2, 2)]
        result = generate(DAYS[:1], WEEK[:1], sessions, time_budget=0)
        self.assertEqual(len(result.placements), 1)
        self.assertEqual(result.unplaced[0][1], 'No slot left without clashing with other sessions')


class ScoreTests(SolverTestCase):

    def test_same_seed_same_result(self):
        sessions = realistic_sessions()
        first = generate(DAYS, WEEK, sessions, seed=7, time_budget=0)
        self.assertEqual(first, generate(DAYS, WEEK, sessions, seed=7, time_budget=0))
        layouts = {tuple(generate(DAYS, WEEK, sessions, seed=s, time_budget=0).placements)
                   for s in range(3)}
        self.assertGreater(len(layouts), 1)

    def test_score_matches_generate(self):
        sessions = realistic_sessions()
        rules = Rules(avoid_days={1: {'Monday'}}, preferred_time={2: 'afternoon'},
                      max_consecutive=2, avoid_first_period=True, avoid_last_period=True)
        result = generate(DAYS, WEEK, sessions, rules, time_budget=0)
        self.assertEqual(score(DAYS, WEEK, sessions, result.placements, rules),
                         (result.score, result.breakdown))
        self.assertAlmostEqual(result.score, sum(result.breakdown.values()))

    def test_score_categories(self):
        periods = [period('09:00', '10:00'), period('10:00', '11:00'), period('11:00', '12:00'),
                   period('12:00', '13:00'), period('14:00', '15:00')]
        sessions = [lecture('1-L1', 1, 1), lecture('1-L2', 1, 1), lecture('2-L1', 2, 2),
                    lecture('3-L1', 3, 3), lecture('4-L1', 4, 4), lecture('5-L1', 5, 5)]
        spots = {'1-L1': ('Monday', 0), '1-L2': ('Monday', 1), '2-L1': ('Monday', 2),
                 '3-L1': ('Monday', 3), '4-L1': ('Tuesday', 0), '5-L1': ('Tuesday', 4)}
        placements = [Placement(key, day, p, periods[p].start, periods[p].end)
                      for key, (day, p) in spots.items()]
        rules = Rules(avoid_days={2: {'Monday'}}, preferred_time={2: 'afternoon'},
                      avoid_first_period=True, avoid_last_period=True)
        total, breakdown = score(DAYS[:2], periods, sessions, placements, rules)
        self.assertEqual(breakdown, {
            'same_day_repeat': 50,   # two course-1 lectures on Monday
            'avoid_day': 40,
            'time_preference': 15,   # 11:00 is not afternoon
            'gaps': 24,              # Tuesday idles for 3 periods between 09:00 and 14:00
            'imbalance': 4,          # 4 and 2 busy periods: variance 1
            'long_stretch': 10,      # 4 periods in a row on Monday
            'first_period': 10,
            'last_period': 5,
        })
        self.assertEqual(total, 158)

    def test_idle_batch_time_counts_as_gaps(self):
        periods = WEEK[:2] + [period('11:00', '12:00'), period('12:00', '13:00')]
        sessions = [lecture('1-L1', 1, 1), lab('2-A', 2, 2, 'A'), lecture('3-L1', 3, 3),
                    lab('4-A', 4, 4, 'A'), lab('4-B', 4, 5, 'B')]

        length = {s.key: s.length for s in sessions}

        def gaps(spots):
            placements = [Placement(key, 'Monday', p, periods[p].start,
                                    periods[p + length[key] - 1].end)
                          for key, p in spots.items()]
            return score(DAYS[:1], periods, sessions, placements, None)[1].get('gaps', 0)

        # Lecture, batch A lab, lecture: batch B idles for two periods in between.
        self.assertEqual(gaps({'1-L1': 0, '2-A': 1, '3-L1': 3}), 16)
        # Staggered labs leave each batch idle while the other works; parallel ones do not.
        self.assertEqual(gaps({'4-A': 0, '4-B': 2}), 32)
        self.assertEqual(gaps({'4-A': 0, '4-B': 0}), 0)


class ValidationTests(unittest.TestCase):

    def test_bad_input(self):
        one = [lecture('1-L1', 1, 1)]
        with self.assertRaisesRegex(ValueError, 'Duplicate session key'):
            generate(DAYS, WEEK, one + one)
        with self.assertRaisesRegex(ValueError, 'length 0'):
            generate(DAYS, WEEK, [Session('x', 1, (1,), 'Lab', 'A', 0)])
        with self.assertRaisesRegex(ValueError, 'day'):
            generate([], WEEK, one)
        with self.assertRaisesRegex(ValueError, 'period'):
            generate(DAYS, [], one)
        with self.assertRaisesRegex(ValueError, 'Unknown session key'):
            score(DAYS, WEEK, one, [Placement('nope', 'Monday', 0, time(9), time(10))], None)


class RealisticWeekTests(SolverTestCase):

    def test_realistic_week(self):
        sessions = realistic_sessions()
        started = perf_counter()
        result = generate(DAYS, WEEK, sessions)
        self.assertLess(perf_counter() - started, 3)
        self.assertEqual(result.unplaced, [])
        self.assertEqual(len(result.placements), len(sessions))
        self.assertGreaterEqual(result.attempts, 30)
        self.assertValid(DAYS, WEEK, sessions, None, result)
        placed = self.by_key(result)
        for a in ('6-A', '7-A'):
            self.assertTrue(any(overlap(placed[a], placed[b]) for b in ('6-B', '7-B')))


if __name__ == '__main__':
    unittest.main()
