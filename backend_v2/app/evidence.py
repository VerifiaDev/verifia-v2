"""Content identity shared by verification cache and in-flight coordination."""
import hashlib
import json
from contextvars import ContextVar

current_claim_frame = ContextVar("verification_claim_frame", default=None)


def evidence_fingerprint(sources: list) -> str:
    # Hash exactly what the verifier sees, including provenance and publication clues.
    fields = ("id", "url", "text", "title", "domain", "published_date")
    evidence = [{**{k: s.get(k) for k in fields},
                 "fetch_method": s.get("fetch_method") or s.get("metadata", {}).get("fetch_method", "unknown")}
                for s in sources]
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()



def claim_frame_fingerprint() -> str:
    return hashlib.sha256(json.dumps(current_claim_frame.get(), ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()

# Mutable values belong to one claim; worker contexts share only that claim.
current_research = ContextVar("claim_research", default=None)
verifier_budget = ContextVar("claim_verifier_budget", default=None)
