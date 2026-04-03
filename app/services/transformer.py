from datetime import date, datetime


def parse_ctgov_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %Y", "%Y-%m"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def transform_ctgov_study(raw: dict) -> dict:
    proto = raw.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    desc = proto.get("descriptionModule", {})
    cond_mod = proto.get("conditionsModule", {})
    arms = proto.get("armsInterventionsModule", {})
    elig = proto.get("eligibilityModule", {})
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    outcomes_mod = proto.get("outcomesModule", {})
    contacts_mod = proto.get("contactsLocationsModule", {})

    conditions = cond_mod.get("conditions", [])
    interventions = [
        {"type": i.get("type"), "name": i.get("name")}
        for i in arms.get("interventions", [])
    ]
    primary_outcomes = [
        {"measure": o.get("measure"), "time_frame": o.get("timeFrame")}
        for o in outcomes_mod.get("primaryOutcomes", [])
    ]
    locations = [
        {"facility": loc.get("facility"), "city": loc.get("city"),
         "state": loc.get("state"), "country": loc.get("country")}
        for loc in contacts_mod.get("locations", [])
    ]

    phases = design.get("phases", [])
    phase = ", ".join(phases) if phases else "N/A"

    last_update_struct = status_mod.get("lastUpdatePostDateStruct", {})

    return {
        "registry_id": ident.get("nctId"),
        "registry_source": "clinicaltrials.gov",
        "brief_title": ident.get("briefTitle"),
        "official_title": ident.get("officialTitle"),
        "status": status_mod.get("overallStatus"),
        "phase": phase,
        "study_type": design.get("studyType"),
        "brief_summary": desc.get("briefSummary"),
        "conditions": conditions,
        "interventions": interventions,
        "primary_outcome": primary_outcomes,
        "eligibility_criteria": elig.get("eligibilityCriteria"),
        "locations": locations,
        "sponsor": sponsor_mod.get("leadSponsor", {}).get("name"),
        "enrollment_count": design.get("enrollmentInfo", {}).get("count"),
        "start_date": parse_ctgov_date(
            status_mod.get("startDateStruct", {}).get("date")
        ),
        "completion_date": parse_ctgov_date(
            status_mod.get("completionDateStruct", {}).get("date")
        ),
        "last_updated": parse_ctgov_date(last_update_struct.get("date")),
        "raw_json": raw,
    }
