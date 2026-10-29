"""Binary PLN encoders for a Hebbian snapshot.

Inheritance is the encoder the bridge ladder runs. Implication is the same
two-atom shape: lib_pln syllogizes both. Similarity is that shape too, derived
by transitive similarity. A premise is still two legs.
A host that already has a question passes it on the snapshot. The two-atom
picker remains the fallback for a bank that was only stimulated.
"""

from __future__ import annotations

import os

LINK_TYPES = ("Inheritance", "Implication", "Similarity")
DEFAULT_LINK = "Inheritance"
ENV_NAME = "CAIRN_PLN_ENCODER"


def normalize(link) -> str:
    text = str(link or "").strip()
    if not text:
        return DEFAULT_LINK
    for name in LINK_TYPES:
        if text.lower() == name.lower():
            return name
    raise ValueError(
        f"unknown PLN encoder {link!r}; expected {' or '.join(LINK_TYPES)}"
    )


def from_env() -> str:
    raw = os.environ.get(ENV_NAME, "")
    if not str(raw).strip():
        return DEFAULT_LINK
    return normalize(raw)


def link_of(snap, override=None) -> str:
    """Encoder for this snapshot. An explicit override wins, then the snapshot."""
    if override:
        return normalize(override)
    if not isinstance(snap, dict):
        return DEFAULT_LINK
    query = snap.get("query") or {}
    term = query.get("term")
    if isinstance(term, (list, tuple)) and term:
        return normalize(term[0])
    for candidate in (query.get("link"), snap.get("link")):
        if candidate:
            return normalize(candidate)
    label_text = str(query.get("term_label") or "")
    head = label_text.split()[:1]
    if head and head[0] in LINK_TYPES:
        return head[0]
    return DEFAULT_LINK


def query_objects(snap) -> list[str]:
    """Two atoms of the question. A passed term supplies them when objects do not."""
    if not isinstance(snap, dict):
        return []
    query = snap.get("query") or {}
    objs = [str(x) for x in (query.get("objects") or []) if str(x)][:2]
    if len(objs) >= 2:
        return objs
    term = query.get("term")
    if isinstance(term, (list, tuple)) and len(term) >= 3:
        return [str(term[1]), str(term[2])]
    return objs


def label(link, left, right) -> str:
    return f"{normalize(link)} {left} {right}"


def term(link, left, right) -> str:
    return f"({normalize(link)} {left} {right})"


def objects_from_label(label_text) -> list[str]:
    parts = [part for part in str(label_text or "").split() if part]
    if parts and parts[0] in LINK_TYPES:
        return parts[1:]
    return parts


def table_atom(index, link, src, tgt, strength, conf, stamp) -> str:
    kind = normalize(link)
    return (
        f"(Table {index} {kind} (cons {src} (cons {tgt} ())) "
        f"(stv {strength} {conf}) ({stamp}))"
    )


def sentence_atom(link, src, tgt, strength, conf, stamp) -> str:
    kind = normalize(link)
    return (
        f"(Sentence (({kind} {src} {tgt}) (stv {strength} {conf})) ({stamp}))"
    )
