def build_aliases(pairs: list[tuple[str, list[str]]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for canon, alts in pairs:
        for a in [canon, *alts]:
            out[a.lower().strip()] = canon
    return out
