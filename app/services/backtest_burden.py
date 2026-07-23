"""
Burden-ratio backtest (Addendum v161a acceptance criterion 1). READ-ONLY.

Replays historical Assigned/Confirmed substitute_request rows in chronological
order through the REAL engine pool builder (get_free_teachers_for_period),
selecting by burden ratio (covered-in-window / free-per-cycle, tie-break
first name A-Z, Pass 1 before Pass 2) at 21 / 28 / 42 day windows.

Run in Render Shell from ~/project/src:
    python3 -m app.services.backtest_burden

No writes. Safe to run repeatedly. Delete after acceptance if desired.
"""
import os
os.environ.setdefault('DATABASE_PATH', '/var/data/schoolops.db')

from collections import defaultdict
from datetime import datetime, timedelta

from app.services.db import get_connection
from app.services.substitute_engine import (
    get_free_teachers_for_period, get_cycle_day, TENANT_ID,
)

WINDOWS = [21, 28, 42]


def derive_slots_per_cycle(conn):
    """Teaching periods x cycle length, derived from DB (nothing hardcoded).
    Expected 7 x 7 = 49 as of 23 Jul 2026 -- printed for cross-check."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM period "
                "WHERE tenant_id = ? AND is_teaching = 1", (TENANT_ID,))
    periods = cur.fetchone()['c']
    cur.execute("SELECT cycle_length FROM substitute_config "
                "WHERE tenant_id = ?", (TENANT_ID,))
    row = cur.fetchone()
    cycle_len = row['cycle_length'] if row and row['cycle_length'] else 7
    return periods * cycle_len


def load_free_and_names(conn, slots_per_cycle):
    """free periods per cycle + first names for all eligible substitutes."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, first_name, display_name FROM staff
        WHERE tenant_id = ? AND is_active = 1 AND can_substitute = 1
    """, (TENANT_ID,))
    free, names = {}, {}
    for r in cur.fetchall():
        free[r['id']] = slots_per_cycle
        names[r['id']] = r['display_name'] or r['first_name']
    cur.execute("""
        SELECT staff_id, COUNT(*) AS c FROM timetable_slot
        WHERE tenant_id = ? GROUP BY staff_id
    """, (TENANT_ID,))
    for r in cur.fetchall():
        if r['staff_id'] in free:
            free[r['staff_id']] = slots_per_cycle - r['c']
    return free, names


def load_history(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT request_date, period_id, substitute_id
        FROM substitute_request
        WHERE tenant_id = ?
          AND status IN ('Assigned', 'Confirmed') AND substitute_id IS NOT NULL
        ORDER BY request_date, COALESCE(assigned_at, ''), rowid
    """, (TENANT_ID,))
    return [dict(r) for r in cur.fetchall()]


def rank_pick(pool, sim_dates, free, window_days, on_date):
    """Lowest (covered_in_window / free) wins; tie-break first_name A-Z.
    free == 0 ranks last (inf). Pool is one pass only."""
    best, best_key = None, None
    lo = on_date - timedelta(days=window_days)
    for t in pool:
        f = free.get(t['id'], 0)  # unknown teacher -> ranks last (inf)
        covered = sum(1 for d in sim_dates[t['id']] if lo < d <= on_date)
        ratio = covered / f if f > 0 else float('inf')
        key = (ratio, (t['first_name'] or '').upper())
        if best_key is None or key < best_key:
            best, best_key = t, key
    return best


def simulate(history, free, window_days):
    sim_dates = defaultdict(list)   # staff_id -> [date, ...] of simulated covers
    assigned_on = defaultdict(set)  # date_str -> staff_ids picked that day
    picks = defaultdict(int)
    pick_seq = []
    unfilled = mentor_rows = 0
    cd_cache = {}

    for req in history:
        dstr = req['request_date']
        d = datetime.strptime(dstr, '%Y-%m-%d').date()

        if req['period_id'] is None:
            # Mentor-register cover: selection not pointer/ratio driven
            # (backup/head mechanism). Burden still counts in the window.
            mentor_rows += 1
            sim_dates[req['substitute_id']].append(d)
            # Mirror cross-run behaviour: get_teachers_assigned_on_date has
            # no period filter, so a mentor-cover teacher is excluded from
            # later runs that day. (Within-run the real engine does not
            # exclude them; per-request replay cannot distinguish runs --
            # accepted approximation.)
            assigned_on[dstr].add(req['substitute_id'])
            pick_seq.append(('MENTOR', req['substitute_id']))
            continue

        if dstr not in cd_cache:
            cd_cache[dstr] = get_cycle_day(dstr)
        p1, p2 = get_free_teachers_for_period(
            req['period_id'], cd_cache[dstr],
            exclude_staff_ids=list(assigned_on[dstr]), target_date=dstr,
        )
        pool = p1 if p1 else p2
        if not pool:
            unfilled += 1
            pick_seq.append(('NONE', None))
            continue

        pick = rank_pick(pool, sim_dates, free, window_days, d)
        picks[pick['id']] += 1
        sim_dates[pick['id']].append(d)
        assigned_on[dstr].add(pick['id'])
        pick_seq.append(('PICK', pick['id']))

    return picks, pick_seq, unfilled, mentor_rows


def norm_stats(counts, free, eligible_ids):
    """Normalized burden (covers / free) across ALL eligible subs."""
    vals = []
    for sid in eligible_ids:
        f = free.get(sid, 0)
        vals.append((counts.get(sid, 0) / f) if f > 0 else 0.0)
    n = len(vals)
    if not n:
        return 0.0, 0.0, 0.0, 0.0
    mean = sum(vals) / n
    sd = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
    return mean, sd, min(vals), max(vals)


def main():
    with get_connection() as conn:
        slots = derive_slots_per_cycle(conn)
        free, names = load_free_and_names(conn, slots)
        history = load_history(conn)

    eligible_ids = list(free.keys())
    print(f"slots per cycle (derived): {slots}")
    if not eligible_ids or not history:
        print(f"nothing to backtest: eligible={len(eligible_ids)} "
              f"history={len(history)}")
        return
    print(f"eligible subs: {len(eligible_ids)}  free range: "
          f"{min(free.values())}-{max(free.values())}")
    print(f"history rows (Assigned/Confirmed): {len(history)}  "
          f"span: {history[0]['request_date']} -> {history[-1]['request_date']}")

    # Actual (pointer-era) distribution for comparison
    actual = defaultdict(int)
    for req in history:
        actual[req['substitute_id']] += 1
    am, asd, amn, amx = norm_stats(actual, free, eligible_ids)
    zero_actual = sum(1 for s in eligible_ids if actual.get(s, 0) == 0)
    print(f"\nACTUAL (pointer): norm-burden mean={am:.3f} sd={asd:.3f} "
          f"min={amn:.3f} max={amx:.3f}  never-used={zero_actual}/{len(eligible_ids)}")

    seqs = {}
    for w in WINDOWS:
        picks, seq, unfilled, mentor = simulate(history, free, w)
        seqs[w] = seq
        m, sd, mn, mx = norm_stats(picks, free, eligible_ids)
        zero = sum(1 for s in eligible_ids if picks.get(s, 0) == 0)
        print(f"\nWINDOW {w}d: norm-burden mean={m:.3f} sd={sd:.3f} "
              f"min={mn:.3f} max={mx:.3f}  never-used={zero}/{len(eligible_ids)}"
              f"  unfilled={unfilled}  mentor-rows={mentor}")
        top = sorted(picks.items(), key=lambda kv: -kv[1])[:5]
        print("  top5: " + ", ".join(
            f"{names.get(s, s)}={c}" for s, c in top))

    # Sensitivity: how many picks differ vs the 28d run
    base = seqs[28]
    for w in WINDOWS:
        if w == 28:
            continue
        diff = sum(1 for a, b in zip(seqs[w], base)
                   if a[0] == 'PICK' and b[0] == 'PICK' and a[1] != b[1])
        print(f"\npicks differing {w}d vs 28d: {diff}")


if __name__ == '__main__':
    main()
