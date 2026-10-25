"""Compliance guard for Ask Reboot answers (README §25).

The rules are the REBOOT marketing dashboard's compliance rules
(reboot-dashboard/tabs/compliance/server_rules.json), copied to support/data/compliance_rules.json.
review() is the same check as the dashboard's server_review.review(), so a chatbot answer gets the same
verdict the compliance tab would give it. Every answer is checked on the server before the visitor sees it:

  PASS / COND / REVIEW  -> sent as written (REVIEW is logged for the admin)
  REVISE / BLOCK        -> OpenAI is asked once to rewrite without the flagged words;
                           if the rewrite still fails, a fixed safe answer is sent instead.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

RANK = {"PASS": 0, "COND": 1, "REVIEW": 2, "REVISE": 3, "BLOCK": 4}
STOP = ("REVISE", "BLOCK")  # verdicts that never reach the visitor
RULES_FILE = Path(__file__).parent / "data" / "compliance_rules.json"
CHANNEL = "cs"  # the dashboard's customer-care channel: same audience as the chatbot

SAFE_REPLY = {
    "en": ("Howdy! I can't speak to any health effects. Reboot is a general food product for adults 21+, "
           "and the product pages list what's inside. For health questions, please ask a doctor. "
           "For anything else, the Contact page (/contact/) is here to help."),
    "ko": ("건강 효과에 대해서는 말씀드릴 수 없어요. 리부트는 만 21세 이상 성인을 위한 일반식품이고, "
           "원재료는 제품 페이지에서 확인할 수 있어요. 건강 관련 질문은 의사와 상담해 주세요. "
           "그 밖의 궁금한 점은 문의 페이지(/contact/)에서 도와드릴게요."),
}


@lru_cache(maxsize=1)
def _data():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _rules():
    out = []
    for r in _data()["rules"]:
        out.append({
            **r,
            "_re": [re.compile(p, re.I) for p in r["regex"]],
            "_comp": [re.compile(p, re.I) for p in r["compensated"]],
            "_inc": [re.compile(p, re.I) for p in r.get("incentive", [])],
            "_allow": [re.compile(p, re.I) for p in r.get("allow", [])],
        })
    return out


def rules_info():
    """For the admin Chatbot page: which rule set is live."""
    data = _data()
    return dict(version=data.get("version", ""), count=len(data["rules"]),
                rules=[dict(code=r["code"], name=r["name"], verdict=r["byChannel"].get(CHANNEL, r["verdict"])) for r in data["rules"]])


def _mask(rule, src):
    for rx in rule["_allow"]:
        src = rx.sub(lambda m: " " * len(m.group(0)), src)
    return src


def review(text, channel=CHANNEL):
    """{verdict, codes, hits} — same result as the dashboard's server_review.review()."""
    src = str(text or "").replace("*", " ")
    verdict, codes, hits = "PASS", [], {}
    for r in _rules():
        masked = _mask(r, src)
        found = [m.group(0).strip() for rx in r["_re"] for m in rx.finditer(masked)]
        found += [k for k in r["ko"] if k in masked]
        compensated = any(rx.search(masked) for rx in r["_comp"])
        incentive = not compensated and any(rx.search(masked) for rx in r["_inc"])
        if not found and not compensated and not incentive:
            continue
        v = r["byChannel"].get(channel, r["verdict"])
        if incentive and RANK.get(r.get("incentiveVerdict"), -1) > RANK[v]:
            v = r["incentiveVerdict"]
        if compensated:
            v = "BLOCK"
        codes.append(r["code"])
        hits[r["code"]] = found[:5] or ["(compensation wording)" if compensated else "(incentive wording)"]
        if RANK[v] > RANK[verdict]:
            verdict = v
    return {"verdict": verdict, "codes": codes, "hits": hits}


def rewrite_note(result):
    words = sorted({w for found in result["hits"].values() for w in found})
    return ("Compliance check failed for your last draft answer (rules " + ", ".join(result["codes"]) + "). "
            "Rewrite the same answer for the customer without these words or any variant of them: " + "; ".join(words) + ". "
            "Do not mention hangovers or any health effect at all. Do not mention the rule check. "
            "If the question itself is about health effects, say kindly that you can't speak to health effects, "
            "describe what the product is, and suggest a doctor for health questions.")


def guarded(messages, ask, lang="en"):
    """Ask, check, rewrite once if needed, fall back to a safe answer.

    ask(messages, extra_system) -> (ok, text). Returns (ok, reply_or_error, log) where log describes what the guard did.
    """
    ok, reply = ask(messages, None)
    if not ok:
        return False, reply, None
    first = review(reply)
    log = dict(verdict=first["verdict"], codes=first["codes"], action="passed", flagged_reply="")
    if first["verdict"] not in STOP:
        return True, reply, log
    log["flagged_reply"] = reply
    ok2, second = ask(messages, rewrite_note(first))
    if ok2 and review(second)["verdict"] not in STOP:
        log["action"] = "rewritten"
        return True, second, log
    log["action"] = "blocked"
    return True, SAFE_REPLY.get(lang, SAFE_REPLY["en"]), log
