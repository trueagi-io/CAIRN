"""Priced import link. Pure account: no PeTTa, no snapshot I/O.

One line of credit, spent by the influenced arm only. Query atoms match
first, then STI descending. A new match spends that atom's STI. An atom
the link has already bought stays in the hold and is not charged again.
The hold stops at k. When the next new atom costs more than the remainder
the link suspends: the closed pass drops the tail, the open pass admits
further atoms free until the hold reaches k.
"""

from __future__ import annotations

import json
from pathlib import Path

LINK_FIELDS = [
    "credit_open",
    "spent",
    "remainder",
    "n_held",
    "bound",
    "suspended",
    "forgotten",
    "n_free",
    "n_retained",
    "n_bought",
    "n_released",
    "wage_credit",
    "influenced_confidence",
    "weighted_credit_open",
    "weighted_spent",
    "weighted_remainder",
    "weighted_n_held",
    "weighted_bound",
    "weighted_suspended",
    "weighted_forgotten",
    "weighted_confidence",
    "distracted_credit_open",
    "distracted_spent",
    "distracted_remainder",
    "distracted_n_held",
    "distracted_bound",
    "distracted_suspended",
    "distracted_forgotten",
    "distracted_confidence",
]


def _sti_map(sti) -> dict[str, float]:
    out = {}
    if not isinstance(sti, dict):
        return out
    for key, value in sti.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def focus_mass(af, sti) -> float:
    """STI mass of the attentional focus. Missing atoms contribute nothing."""
    table = _sti_map(sti)
    total = 0.0
    for atom in af or []:
        total += max(0.0, table.get(str(atom), 0.0))
    return total


def order_candidates(candidates, query, sti) -> list[str]:
    """Query atoms first, in given order, then the rest by STI descending."""
    table = _sti_map(sti)
    seen: set[str] = set()
    front: list[str] = []
    for atom in query or []:
        name = str(atom)
        if not name or name in seen:
            continue
        seen.add(name)
        front.append(name)
    rest: list[str] = []
    for atom in candidates or []:
        name = str(atom)
        if not name or name in seen:
            continue
        seen.add(name)
        rest.append(name)
    rest.sort(key=lambda name: (-table.get(name, 0.0), name))
    return front + rest


RELEASE_ABSENT = "absent"
RELEASE_DEAD = "dead"
RELEASE_ONE = "one"
RELEASE_MODES = (RELEASE_ABSENT, RELEASE_DEAD, RELEASE_ONE)


def release_owned(owned, query, sti, present, mode: str) -> tuple[list[str], list[str]]:
    """Drop bought atoms that no longer earn their slot.

    `absent` drops atoms missing from the snapshot. `dead` also drops STI 0.
    `one` does that, and when nothing was dead drops the cheapest non-query
    atom once. Query atoms stay.
    """
    if mode not in RELEASE_MODES:
        raise ValueError(f"unknown release mode {mode!r}")
    table = _sti_map(sti)
    query_set = {str(atom) for atom in (query or []) if str(atom)}
    here = {str(atom) for atom in (present or []) if str(atom)}
    kept: list[str] = []
    released: list[str] = []
    seen: set[str] = set()
    for atom in owned or []:
        name = str(atom)
        if not name or name in seen:
            continue
        seen.add(name)
        absent = name not in here
        zero = name in table and abs(table[name]) <= 1e-9
        drop = False
        if name not in query_set:
            if mode == RELEASE_ABSENT:
                drop = absent
            else:
                drop = absent or zero
        if drop:
            released.append(name)
        else:
            kept.append(name)
    if mode == RELEASE_ONE and not released:
        pool = [name for name in kept if name not in query_set]
        if pool:
            pool.sort(key=lambda name: (0 if name not in here else 1, table.get(name, 0.0), name))
            victim = pool[0]
            kept = [name for name in kept if name != victim]
            released.append(victim)
    return kept, released


def price_link(
    ordered,
    sti,
    credit,
    k,
    admit_free: bool,
    owned=None,
    release: str | None = None,
    query=None,
    present=None,
) -> dict:
    """Spend `credit` on new atoms. Does not mutate the credit the caller holds.

    Atoms in `owned` stay in the hold at no charge and count toward k, unless
    `release` drops them first. `bound` is `cap` when k stops admission,
    `fund` when the next new atom does not fit, and `none` when every new
    candidate was affordable. Free atoms are admitted only while the hold is
    inside k, and they are not added to `owned`.
    """
    table = _sti_map(sti)
    opening = float(credit)
    remainder = opening
    spent = 0.0
    cap = max(0, int(k))
    released: list[str] = []
    owned_in = list(owned or [])
    if release:
        owned_in, released = release_owned(owned_in, query, sti, present, release)
    retained: list[str] = []
    seen: set[str] = set()
    for atom in owned_in:
        name = str(atom)
        if not name or name in seen:
            continue
        seen.add(name)
        retained.append(name)
        if len(retained) >= cap:
            break
    held = list(retained)
    bought: list[str] = []
    suspended = False
    free_mode = False
    bound = "none"
    n_free = 0
    in_held = set(held)
    pending = [str(atom) for atom in (ordered or []) if str(atom) and str(atom) not in in_held]
    if len(held) >= cap and pending:
        bound = "cap"
    else:
        for name in pending:
            if name in in_held:
                continue
            cost = max(0.0, table.get(name, 0.0))
            if not free_mode:
                if len(held) >= cap:
                    bound = "cap"
                    break
                if cost > remainder + 1e-9:
                    suspended = True
                    bound = "fund"
                    if not admit_free:
                        break
                    free_mode = True
                else:
                    remainder -= cost
                    spent += cost
                    held.append(name)
                    in_held.add(name)
                    bought.append(name)
                    continue
            if len(held) >= cap:
                break
            held.append(name)
            in_held.add(name)
            n_free += 1
    return {
        "credit_open": opening,
        "spent": spent,
        "remainder": remainder,
        "held": held,
        "n_held": len(held),
        "bound": bound,
        "suspended": suspended,
        "forgotten": len(held) == 0,
        "n_free": n_free,
        "n_retained": len(retained),
        "n_bought": len(bought),
        "n_released": len(released),
        "released": released,
        "owned": list(retained) + list(bought),
    }


def wage_credit(n_atoms: int, wage: float = 200.0) -> float:
    """STI just added: wage on each stimulated atom."""
    try:
        n = int(n_atoms)
    except (TypeError, ValueError):
        n = 0
    if n < 0:
        n = 0
    return float(wage) * n


def importable_bank(snap: dict) -> list[str]:
    """Atoms the weighted link can see: STI table, focus, and edge endpoints."""
    found: list[str] = []
    seen: set[str] = set()

    def add(atom) -> None:
        name = str(atom)
        if not name or name in seen:
            return
        seen.add(name)
        found.append(name)

    for atom in (snap.get("sti") or {}):
        add(atom)
    for atom in snap.get("af") or []:
        add(atom)
    for row in snap.get("edges") or []:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            add(row[0])
            add(row[1])
    return found


def distracted_draw(bank, size: int, seed: int = 0, skip=None) -> list[str]:
    """One draw, seed 0 by default, of `size` bank atoms outside `skip`."""
    import random

    blocked = {str(a) for a in (skip or [])}
    pool = [str(a) for a in bank if str(a) and str(a) not in blocked]
    n = min(max(0, int(size)), len(pool))
    if n <= 0:
        return []
    return random.Random(int(seed)).sample(pool, n)


def fresh_fund(admit_free: bool, wage: float, k: int) -> dict:
    return {
        "admit_free": bool(admit_free),
        "wage": float(wage),
        "k": int(k),
        "remainder": None,
        "owned": [],
        "periods": [],
    }


def load_fund(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    return doc if isinstance(doc, dict) else None


def save_fund(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
