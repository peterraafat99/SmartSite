"""
SmartSite OSHA Knowledge Module.
Structured local safety reference database based on official OSHA Construction Standards (29 CFR 1926).
NOTE: This is an OSHA-aligned prototype demonstration, not a certified legal compliance system.
Detections and sensor alerts do not automatically constitute legal violations.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class OSHAReference:
    code: str
    title: str
    hazard_category: str
    summary: str
    required_measures: List[str]
    recommended_action: str
    official_url: str
    applicable_events: List[str]

OSHA_STANDARDS: Dict[str, OSHAReference] = {
    "29 CFR 1926.100": OSHAReference(
        code="29 CFR 1926.100",
        title="Head Protection",
        hazard_category="Head Protection",
        summary=(
            "Employees working in areas where there is a possible danger of head injury "
            "from impact, or from falling or flying objects, or from electrical shock and burns, "
            "shall be protected by protective helmets meeting ANSI Z89.1 standards."
        ),
        required_measures=[
            "Wear ANSI-compliant hard hats at all times in designated hard-hat areas.",
            "Inspect helmet shell and suspension system daily for cracks, dents, or wear.",
            "Replace helmets immediately if subjected to direct impact."
        ],
        recommended_action=(
            "Verify hard hat fit and condition. Halt work immediately in overhead hazard zones "
            "until compliant head protection is worn."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.100",
        applicable_events=["PPE_VIOLATION_NO_HELMET", "MISSING_PPE"]
    ),
    "29 CFR 1926 Subpart E": OSHAReference(
        code="29 CFR 1926 Subpart E",
        title="Personal Protective and Life Saving Equipment (General & Respiratory / Eye)",
        hazard_category="Personal Protective Equipment",
        summary=(
            "Mandates appropriate personal protective equipment (PPE) for eyes, face, head, "
            "extremities, and respiratory protection whenever hazards are present from processes, "
            "environmental hazards, airborne particulates, or chemical hazards."
        ),
        required_measures=[
            "High-visibility safety vests (ANSI/ISEA 107) must be worn around mobile equipment.",
            "Safety goggles (ANSI Z87.1) required for grinding, cutting, or high-dust operations.",
            "Protective footwear (ASTM F2413) and task-appropriate gloves must be utilized."
        ],
        recommended_action=(
            "Equip personnel with appropriate PPE before job briefing. Enforce zero-tolerance "
            "for missing mandatory gear in operational zones."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926SubpartE",
        applicable_events=["PPE_VIOLATION_NO_VEST", "PPE_VIOLATION_NO_BOOTS", "PPE_VIOLATION_NO_GLOVES", "PPE_VIOLATION_NO_GOGGLE", "IOT_DUST_ALERT", "IOT_GAS_ALERT"]
    ),
    "29 CFR 1926 Subpart M": OSHAReference(
        code="29 CFR 1926 Subpart M",
        title="Fall Protection (29 CFR 1926.501 - 503)",
        hazard_category="Fall Hazards",
        summary=(
            "Requires employers to provide fall protection systems (guardrails, safety nets, "
            "or personal fall arrest systems) for employees exposed to falls of 6 feet (1.8 m) "
            "or more above a lower level."
        ),
        required_measures=[
            "Guardrail systems with top rails at 42 inches (+/- 3 inches) and toeboards.",
            "Personal Fall Arrest Systems (PFAS) anchored to 5,000 lb rated anchor points.",
            "Cover all floor holes and openings securely with marked covers."
        ],
        recommended_action=(
            "Halt work at edge perimeter. Inspect 100% tie-off compliance and harness condition."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926SubpartM",
        applicable_events=["FALL_HAZARD", "UNPROTECTED_EDGE"]
    ),
    "29 CFR 1926 Subpart P": OSHAReference(
        code="29 CFR 1926 Subpart P",
        title="Excavations and Trench Safety (29 CFR 1926.651 - 652)",
        hazard_category="Restricted Zone / Trench Safety",
        summary=(
            "Requires protective systems (sloping, shoring, shielding) for trenches 5 feet (1.5 m) "
            "or deeper unless in stable rock. Mandates daily inspections by a designated Competent Person "
            "prior to worker entry."
        ),
        required_measures=[
            "Daily inspection by Competent Person before workers enter.",
            "Keep spoils and heavy equipment at least 2 feet back from trench edges.",
            "Provide safe ladders/ramps within 25 feet of lateral travel in trenches 4+ feet deep."
        ],
        recommended_action=(
            "Evacuate unauthorized personnel from trench perimeter immediately. Verify trench box "
            "or shoring certification before re-entry."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926SubpartP",
        applicable_events=["ZONE_INTRUSION", "EXCAVATION_BREACH"]
    ),
    "29 CFR 1926 Subpart CC": OSHAReference(
        code="29 CFR 1926 Subpart CC",
        title="Cranes and Derricks in Construction (29 CFR 1926.1424)",
        hazard_category="Crane Swing Radius & Struck-By",
        summary=(
            "Requires barriers or warning tape to prevent employees from entering hazardous areas "
            "within the swing radius of the rotating superstructure of cranes and derricks to prevent "
            "pinch-point and struck-by fatalities."
        ),
        required_measures=[
            "Erect physical barricades or boundary lines marking swing radius hazard area.",
            "Train employees never to enter swing radius while equipment is operational.",
            "Maintain dedicated spotter communications with crane operator."
        ],
        recommended_action=(
            "Sound horn / audible alert. Clear swing radius zone of personnel immediately."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926SubpartCC",
        applicable_events=["ZONE_INTRUSION", "CRANE_RADIUS_BREACH"]
    ),
    "29 CFR 1926.52": OSHAReference(
        code="29 CFR 1926.52",
        title="Occupational Noise Exposure",
        hazard_category="Acoustic Hazard",
        summary=(
            "Permissible noise exposure limits protection for construction workers. Protection against the "
            "effects of noise exposure shall be provided when the sound levels exceed an 8-hour time-weighted "
            "average of 90 dBA, with mandatory hearing conservation programs."
        ),
        required_measures=[
            "Provide hearing protection (earplugs/muffs with adequate NRR) in high-noise areas.",
            "Implement acoustic dampening or engineering controls on heavy machinery.",
            "Rotate personnel to prevent exceeding daily permissible noise dose."
        ],
        recommended_action=(
            "Distribute hearing protection immediately. Identify noise source and apply dampening."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.52",
        applicable_events=["IOT_NOISE_ALERT"]
    ),
    "29 CFR 1926.55": OSHAReference(
        code="29 CFR 1926.55",
        title="Gases, Vapors, Fumes, Dusts, and Mists",
        hazard_category="Environmental / Chemical Exposure",
        summary=(
            "Employees shall avoid exposure to inhalation, ingestion, skin absorption, or contact with "
            "any material or substance at a concentration above threshold limit values specified by ACGIH "
            "and OSHA permissible exposure limits."
        ),
        required_measures=[
            "Continuous atmospheric monitoring in confined spaces and basements.",
            "Forced mechanical ventilation where hazardous gases or dust accumulate.",
            "Appropriate NIOSH-certified respirators matching hazard type."
        ],
        recommended_action=(
            "Evacuate area to upwind safe zone. Activate ventilation fans and verify gas clearance."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.55",
        applicable_events=["IOT_GAS_ALERT", "IOT_DUST_ALERT"]
    ),
    "29 CFR 1926.20": OSHAReference(
        code="29 CFR 1926.20",
        title="General Safety and Health Provisions (Site Access & Competent Persons)",
        hazard_category="Perimeter Access & Identity Authorization",
        summary=(
            "Requires employer accident prevention responsibilities, regular site inspections by a "
            "Competent Person, and restriction of jobsite access exclusively to trained, authorized, "
            "and certified personnel."
        ),
        required_measures=[
            "Enforce strict perimeter control and positive identity verification at all ingress points.",
            "Verify OSHA safety training certification before permitting unescorted site entry.",
            "Maintain an active, verifiable site attendance and visitor roster."
        ],
        recommended_action=(
            "Lock turnstile gate immediately. Escort unverified personnel to security briefing trailer. "
            "Verify OSHA credentials before issuing site clearance badge."
        ),
        official_url="https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.20",
        applicable_events=["SECURITY_UNAUTHORIZED_ENTRY", "UNAUTHORIZED_ZONE_ENTRY"]
    )
}

PLANNED_MODULES = [
    {
        "name": "Fall Detection & Leading Edge Monitoring",
        "standard_ref": "29 CFR 1926 Subpart M",
        "status": "Planned Roadmap (Q3)",
        "description": (
            "Vision-based worker posture and tie-off verification at leading roof and scaffolding edges. "
            "Will detect worker proximity to unprotected falls and identify harness tether anchor status."
        ),
        "target_release": "v2.0"
    },
    {
        "name": "Fire & Smoke Early Detection",
        "standard_ref": "29 CFR 1926 Subpart F",
        "status": "Planned Roadmap (Q4)",
        "description": (
            "Thermal and optical fire/smoke plume detection for early warning during hot work, "
            "welding operations, and fuel storage containment zones."
        ),
        "target_release": "v2.0"
    }
]

def get_regulation_for_event(event_type: str) -> Optional[OSHAReference]:
    """Find the most relevant OSHA standard reference for an event type."""
    for ref in OSHA_STANDARDS.values():
        if event_type in ref.applicable_events:
            return ref
    # Fallback to general PPE
    return OSHA_STANDARDS.get("29 CFR 1926 Subpart E")

def list_all_regulations() -> List[OSHAReference]:
    """List all registered OSHA reference standards."""
    return list(OSHA_STANDARDS.values())
