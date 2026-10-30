"""Canonical source of the shared result_status block (plugin 0.8.0, B9).

Each of the seven skill scripts carries a byte-identical copy of the text between the BEGIN and
END markers below; tools/sync_shared_blocks.py writes the copies and --check reports drift. Edit
here, never in a script. The block defines names only and imports nothing.
"""

from __future__ import annotations

# BEGIN shared result_status (do not edit here; source tools/shared/result_status.py)
# Output status taxonomy. Every result envelope carries result_status (envelope_status of its
# checks: the worst word among the checks the module performs) and checks: [{name, result_status,
# status (pass/fail/na), note[, unresolved_factor]}]. "not checked" rows never drive the envelope;
# they are listed, and the envelope reads "not checked" only when every row is. A positive banner
# word (PASS, OK, ISSUE, DELIVERABLE) is printed only when banner_allowed() is true: never under
# "manual check required" or "pointer only", nor under "screening" when a reconstructed factor in
# the chain is unresolved. Any ASSUMED input gives one "ASSUMED inputs" row (assumed_inputs_check)
# graded manual check required, so an unconfirmed input always holds the banner.

RESULT_STATUS = ("calculated", "screening", "manual check required", "pointer only", "not checked")
# severity for worst_of (ordering only): manual check required > pointer only > screening > not checked > calculated
RESULT_STATUS_SEVERITY = {"manual check required": 4, "pointer only": 3, "screening": 2, "not checked": 1,
                          "calculated": 0}
CHECK_STATUS = ("pass", "fail", "na")
ASSUMED_CHECK_NAME = "ASSUMED inputs"


def _rs_word(item):
    word = item.get("result_status") if isinstance(item, dict) else item
    if word not in RESULT_STATUS_SEVERITY:
        raise ValueError(f"result_status {word!r} is not one of {', '.join(RESULT_STATUS)}")
    return word


def worst_of(statuses):
    """The most severe result_status of words or check dicts; 'not checked' for an empty list."""
    words = [_rs_word(s) for s in statuses]
    return max(words, key=RESULT_STATUS_SEVERITY.__getitem__) if words else "not checked"


def envelope_status(checks):
    """The envelope word: the most severe word among the checks that are not 'not checked'.

    'not checked' rows (limits the module does not perform) never drive it; when every row is
    'not checked', or there are none, the envelope reads 'not checked'.
    """
    words = [w for w in (_rs_word(c) for c in checks) if w != "not checked"]
    return worst_of(words) if words else "not checked"


def make_check(name, result_status, status=None, note=None, unresolved_factor=False):
    """One checks[] entry. status is pass/fail/na (None means na); unresolved_factor only with screening."""
    _rs_word(result_status)
    status = "na" if status is None else status
    if status not in CHECK_STATUS:
        raise ValueError(f"check status {status!r} is not one of {', '.join(CHECK_STATUS)}")
    if unresolved_factor and result_status != "screening":
        raise ValueError("unresolved_factor marks a screening check only")
    check = {"name": name, "result_status": result_status, "status": status, "note": note}
    if unresolved_factor:
        check["unresolved_factor"] = True
    return check


def assumed_inputs_check(items):
    """The one 'ASSUMED inputs' row for every ASSUMED item (strings or {item[, note]} dicts), or None.

    Graded manual check required, so the envelope follows it and no positive banner prints; the
    note reads 'confirm before issue: <item>; <item>' (duplicates dropped, order kept).
    """
    texts = []
    for it in items or ():
        text = it.get("item") if isinstance(it, dict) else it
        text = str(text).strip() if text is not None else ""
        if text and text not in texts:
            texts.append(text)
    if not texts:
        return None
    return make_check(ASSUMED_CHECK_NAME, "manual check required", "na",
                      "confirm before issue: " + "; ".join(texts))


def not_performed(checks):
    """'not performed by this module: a; b' for the 'not checked' rows of checks, '' when there are none."""
    names = [c["name"] for c in checks if isinstance(c, dict) and c.get("result_status") == "not checked"]
    return "not performed by this module: " + "; ".join(names) if names else ""


def banner_allowed(result_status, unresolved_factor=False):
    """False for manual check required, pointer only, and screening with an unresolved factor."""
    word = _rs_word(result_status)
    if word in ("manual check required", "pointer only"):
        return False
    return not (word == "screening" and unresolved_factor)


def status_fields(checks):
    """{result_status: envelope_status, checks} to merge into an envelope (adds keys, changes none)."""
    checks = list(checks)
    return {"result_status": envelope_status(checks), "checks": checks}


def checks_banner_allowed(checks):
    """banner_allowed for the envelope word of checks, with any unresolved_factor among them."""
    checks = list(checks)
    return banner_allowed(envelope_status(checks), any(c.get("unresolved_factor") for c in checks))


def banner_word(ok_word, result_status, unresolved_factor=False):
    """ok_word (e.g. PASS) when the banner rule allows it, else the result_status in capitals."""
    return ok_word if banner_allowed(result_status, unresolved_factor) else _rs_word(result_status).upper()


def render_status_line(result_status, why):
    """The one line under every calc-sheet title: 'Result status: <word> - <why>' (ASCII ' - ')."""
    word = _rs_word(result_status)
    return f"Result status: {word} - {why}" if why else f"Result status: {word}"
# END shared result_status
