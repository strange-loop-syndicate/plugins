"""ClinicalTrials.gov source via the v2 REST API.

Queries the v2 /studies endpoint with a free-form `query_params` block from
config. Useful filters for EA/CU work: `query.term`, `filter.advanced` (with
`AREA[StudyType]EXPANDED_ACCESS`), `query.cond`. Returns one candidate per
study; raw_metadata captures the primary/overall investigators and key fields.

API reference: https://clinicaltrials.gov/data-api/api

Params shape:
    query_params         dict of v2 query parameters (passed through verbatim).
                         Common keys: query.term, query.cond, filter.advanced,
                         filter.overallStatus, pageSize.
    max_pages            int, cap on pagination (default 5).
    page_size            int, override pageSize (default 100, max 1000).
    only_expanded_access bool, when true, adds the EA studyType filter.
"""

from __future__ import annotations

import hashlib
from typing import Any

import requests

API_BASE = "https://clinicaltrials.gov/api/v2/studies"
USER_AGENT = "lead-ops/0.1 (+https://github.com/strange-loop-syndicate/lead-ops)"
DEFAULT_TIMEOUT = 60
EA_FILTER = "AREA[StudyType]EXPANDED_ACCESS"


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _extract_investigators(study: dict) -> list[dict[str, str]]:
    contacts = (study.get("protocolSection") or {}).get("contactsLocationsModule") or {}
    out: list[dict[str, str]] = []
    for kind in ("overallOfficials", "centralContacts"):
        for entry in contacts.get(kind) or []:
            name = entry.get("name") or ""
            if not name:
                continue
            out.append(
                {
                    "name": name,
                    "role": entry.get("role") or kind,
                    "affiliation": entry.get("affiliation") or "",
                }
            )
    return out


def _build_candidate(study: dict) -> dict[str, Any] | None:
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    nct_id = ident.get("nctId")
    if not nct_id:
        return None
    title = ident.get("officialTitle") or ident.get("briefTitle") or nct_id
    status_module = proto.get("statusModule") or {}
    design = proto.get("designModule") or {}
    return {
        "title": title,
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        "source_id": nct_id,
        "source_type": "clinicaltrials_gov",
        "raw_metadata": {
            "nct_id": nct_id,
            "study_type": design.get("studyType") or "",
            "status": status_module.get("overallStatus") or "",
            "start_date": (status_module.get("startDateStruct") or {}).get("date") or "",
            "completion_date": (
                status_module.get("completionDateStruct") or {}
            ).get("date")
            or "",
            "investigators": _extract_investigators(study),
            "sponsor": (
                (proto.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}
            ).get("name", ""),
        },
    }


def discover(scope: dict[str, Any], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Page through CT.gov studies matching `query_params`, return candidates."""
    qp = dict(params.get("query_params") or {})
    if params.get("only_expanded_access"):
        existing = qp.get("filter.advanced")
        qp["filter.advanced"] = (
            f"({existing}) AND {EA_FILTER}" if existing else EA_FILTER
        )
    qp["pageSize"] = int(params.get("page_size") or 100)
    qp.setdefault("format", "json")

    max_pages = int(params.get("max_pages") or 5)
    out: dict[str, dict[str, Any]] = {}

    for page in range(max_pages):
        resp = requests.get(
            API_BASE,
            params=qp,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        for study in body.get("studies") or []:
            cand = _build_candidate(study)
            if cand:
                out.setdefault(cand["url"], cand)
        token = body.get("nextPageToken")
        if not token:
            break
        qp["pageToken"] = token

    return list(out.values())
