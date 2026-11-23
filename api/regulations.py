"""
OSHA 29 CFR 1926 Safety Regulations & Roadmap Router.
"""
from fastapi import APIRouter
from typing import List, Dict, Any

from safety.regulations import list_all_regulations, PLANNED_MODULES

router = APIRouter()

@router.get("")
def get_regulations() -> List[Dict[str, Any]]:
    """Returns official verified OSHA construction standards."""
    regs = list_all_regulations()
    return [
        {
            "code": r.code,
            "title": r.title,
            "hazard_category": r.hazard_category,
            "summary": r.summary,
            "required_measures": r.required_measures,
            "recommended_action": r.recommended_action,
            "official_url": r.official_url,
            "applicable_events": r.applicable_events
        }
        for r in regs
    ]

@router.get("/roadmap")
def get_roadmap() -> List[Dict[str, Any]]:
    """Returns planned future AI modules."""
    return PLANNED_MODULES
