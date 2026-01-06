"""
Notion Service - Reference data only (read-heavy, low-frequency)
Transactional data is in SQLite
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import requests
from functools import lru_cache
from typing import Optional, List, Dict, Any

# Notion API configuration
NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')
NOTION_VERSION = "2022-06-28"

# Database IDs from environment
DB_STAFF = os.environ.get('NOTION_DB_STAFF', '')
DB_LEARNER = os.environ.get('NOTION_DB_LEARNER', '')
DB_MENTOR_GROUP = os.environ.get('NOTION_DB_MENTOR_GROUP', '')
DB_GRADE = os.environ.get('NOTION_DB_GRADE', '')
DB_VENUE = os.environ.get('NOTION_DB_VENUE', '')
DB_PERIOD = os.environ.get('NOTION_DB_PERIOD', '')
DB_DUTY_ZONE = os.environ.get('NOTION_DB_DUTY_ZONE', '')

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}


def _query_database(database_id: str, filter_obj: Optional[Dict] = None, sorts: Optional[List] = None) -> List[Dict]:
    """Query a Notion database with optional filter and sorts."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    
    payload = {}
    if filter_obj:
        payload["filter"] = filter_obj
    if sorts:
        payload["sorts"] = sorts
    
    all_results = []
    has_more = True
    start_cursor = None
    
    while has_more:
        if start_cursor:
            payload["start_cursor"] = start_cursor
        
        response = requests.post(url, headers=HEADERS, json=payload)
        
        if response.status_code != 200:
            print(f"Notion API error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    
    return all_results


def _get_page(page_id: str) -> Optional[Dict]:
    """Get a single Notion page by ID."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"Notion API error: {response.status_code} - {response.text}")
        return None
    
    return response.json()


def _extract_property(prop: Dict) -> Any:
    """Extract value from Notion property object."""
    prop_type = prop.get("type")
    
    if prop_type == "title":
        return prop["title"][0]["plain_text"] if prop["title"] else ""
    elif prop_type == "rich_text":
        return prop["rich_text"][0]["plain_text"] if prop["rich_text"] else ""
    elif prop_type == "number":
        return prop["number"]
    elif prop_type == "select":
        return prop["select"]["name"] if prop["select"] else None
    elif prop_type == "multi_select":
        return [item["name"] for item in prop["multi_select"]]
    elif prop_type == "checkbox":
        return prop["checkbox"]
    elif prop_type == "email":
        return prop["email"]
    elif prop_type == "phone_number":
        return prop["phone_number"]
    elif prop_type == "date":
        return prop["date"]["start"] if prop["date"] else None
    elif prop_type == "relation":
        return [rel["id"] for rel in prop["relation"]]
    elif prop_type == "formula":
        formula_type = prop["formula"]["type"]
        return prop["formula"].get(formula_type)
    elif prop_type == "rollup":
        rollup_type = prop["rollup"]["type"]
        return prop["rollup"].get(rollup_type)
    else:
        return None


def _parse_page(page: Dict, property_map: Dict[str, str]) -> Dict:
    """Parse Notion page into simple dict using property map."""
    result = {"id": page["id"]}
    props = page.get("properties", {})
    
    for notion_name, local_name in property_map.items():
        if notion_name in props:
            result[local_name] = _extract_property(props[notion_name])
        else:
            result[local_name] = None
    
    return result


# ============================================
# MENTOR GROUP FUNCTIONS
# ============================================

def get_mentor_groups() -> List[Dict]:
    """Get all mentor groups."""
    property_map = {
        "group_name": "group_name",
        "mentor_id": "mentor_id",
        "grade_id": "grade_id",
        "venue_id": "venue_id"
    }
    
    results = _query_database(
        os.environ.get('NOTION_DB_MENTOR_GROUP', ''),
        sorts=[{"property": "group_name", "direction": "ascending"}]
    )
    
    groups = []
    for page in results:
        parsed = _parse_page(page, property_map)
        # Handle relation (returns list, we want first item)
        if parsed.get("mentor_id") and isinstance(parsed["mentor_id"], list):
            parsed["mentor_id"] = parsed["mentor_id"][0] if parsed["mentor_id"] else None
        if parsed.get("grade_id") and isinstance(parsed["grade_id"], list):
            parsed["grade_id"] = parsed["grade_id"][0] if parsed["grade_id"] else None
        groups.append(parsed)
    
    return groups


def get_mentor_group_by_id(group_id: str) -> Optional[Dict]:
    """Get single mentor group by ID."""
    page = _get_page(group_id)
    if not page:
        return None
    
    property_map = {
        "group_name": "group_name",
        "mentor_id": "mentor_id",
        "grade_id": "grade_id",
        "venue_id": "venue_id"
    }
    
    parsed = _parse_page(page, property_map)
    if parsed.get("mentor_id") and isinstance(parsed["mentor_id"], list):
        parsed["mentor_id"] = parsed["mentor_id"][0] if parsed["mentor_id"] else None
    
    return parsed


# ============================================
# STAFF FUNCTIONS
# ============================================

def get_staff_by_id(staff_id: str) -> Optional[Dict]:
    """Get single staff member by ID."""
    page = _get_page(staff_id)
    if not page:
        return None
    
    property_map = {
        "title": "title",
        "first_name": "first_name",
        "surname": "surname",
        "display_name": "display_name",
        "email": "email",
        "phone": "phone",
        "staff_type": "staff_type",
        "can_substitute": "can_substitute",
        "can_do_duty": "can_do_duty",
        "is_active": "is_active"
    }
    
    return _parse_page(page, property_map)


def get_all_staff(active_only: bool = True) -> List[Dict]:
    """Get all staff members."""
    property_map = {
        "title": "title",
        "first_name": "first_name", 
        "surname": "surname",
        "display_name": "display_name",
        "email": "email",
        "staff_type": "staff_type",
        "can_substitute": "can_substitute",
        "can_do_duty": "can_do_duty",
        "is_active": "is_active"
    }
    
    filter_obj = None
    if active_only:
        filter_obj = {
            "property": "is_active",
            "checkbox": {"equals": True}
        }
    
    results = _query_database(os.environ.get('NOTION_DB_STAFF', ''), filter_obj)
    return [_parse_page(page, property_map) for page in results]


# ============================================
# LEARNER FUNCTIONS
# ============================================

def get_learner_by_id(learner_id: str) -> Optional[Dict]:
    """Get single learner by ID."""
    page = _get_page(learner_id)
    if not page:
        return None
    
    property_map = {
        "first_name": "first_name",
        "surname": "surname",
        "grade_id": "grade_id",
        "mentor_group_id": "mentor_group_id",
        "house_id": "house_id",
        "is_active": "is_active"
    }
    
    parsed = _parse_page(page, property_map)
    
    # Handle relations
    for field in ["grade_id", "mentor_group_id", "house_id"]:
        if parsed.get(field) and isinstance(parsed[field], list):
            parsed[field] = parsed[field][0] if parsed[field] else None
    
    return parsed


def get_learners_by_mentor_group(mentor_group_id: str) -> List[Dict]:
    """Get all learners in a mentor group."""
    property_map = {
        "first_name": "first_name",
        "surname": "surname",
        "grade_id": "grade_id",
        "mentor_group_id": "mentor_group_id",
        "is_active": "is_active"
    }
    
    filter_obj = {
        "and": [
            {
                "property": "mentor_group_id",
                "relation": {"contains": mentor_group_id}
            },
            {
                "property": "is_active",
                "checkbox": {"equals": True}
            }
        ]
    }
    
    results = _query_database(
        os.environ.get('NOTION_DB_LEARNER', ''),
        filter_obj,
        sorts=[{"property": "surname", "direction": "ascending"}]
    )
    
    learners = []
    for page in results:
        parsed = _parse_page(page, property_map)
        for field in ["grade_id", "mentor_group_id"]:
            if parsed.get(field) and isinstance(parsed[field], list):
                parsed[field] = parsed[field][0] if parsed[field] else None
        learners.append(parsed)
    
    return learners


# ============================================
# GRADE FUNCTIONS
# ============================================

def get_grade_by_id(grade_id: str) -> Optional[Dict]:
    """Get single grade by ID."""
    page = _get_page(grade_id)
    if not page:
        return None
    
    property_map = {
        "grade_name": "grade_name",
        "grade_code": "grade_code",
        "grade_number": "grade_number",
        "sort_order": "sort_order"
    }
    
    return _parse_page(page, property_map)


def get_all_grades() -> List[Dict]:
    """Get all grades sorted by sort_order."""
    property_map = {
        "grade_name": "grade_name",
        "grade_code": "grade_code", 
        "grade_number": "grade_number",
        "sort_order": "sort_order"
    }
    
    results = _query_database(
        os.environ.get('NOTION_DB_GRADE', ''),
        sorts=[{"property": "sort_order", "direction": "ascending"}]
    )
    
    return [_parse_page(page, property_map) for page in results]


# ============================================
# DUTY ZONE FUNCTIONS
# ============================================

def get_all_duty_zones() -> List[Dict]:
    """Get all duty zones."""
    property_map = {
        "zone_name": "zone_name",
        "zone_description": "zone_description",
        "zone_code": "zone_code",
        "sort_order": "sort_order",
        "is_active": "is_active"
    }
    
    filter_obj = {
        "property": "is_active",
        "checkbox": {"equals": True}
    }
    
    results = _query_database(
        os.environ.get('NOTION_DB_DUTY_ZONE', ''),
        filter_obj,
        sorts=[{"property": "sort_order", "direction": "ascending"}]
    )
    
    return [_parse_page(page, property_map) for page in results]


def get_duty_zone_by_id(zone_id: str) -> Optional[Dict]:
    """Get single duty zone by ID."""
    page = _get_page(zone_id)
    if not page:
        return None
    
    property_map = {
        "zone_name": "zone_name",
        "zone_description": "zone_description",
        "zone_code": "zone_code"
    }
    
    return _parse_page(page, property_map)


# ============================================
# PERIOD FUNCTIONS
# ============================================

def get_all_periods() -> List[Dict]:
    """Get all periods."""
    property_map = {
        "period_number": "period_number",
        "period_name": "period_name",
        "period_type": "period_type",
        "start_time": "start_time",
        "end_time": "end_time",
        "sort_order": "sort_order",
        "pattern_id": "pattern_id"
    }
    
    results = _query_database(
        os.environ.get('NOTION_DB_PERIOD', ''),
        sorts=[{"property": "sort_order", "direction": "ascending"}]
    )
    
    periods = []
    for page in results:
        parsed = _parse_page(page, property_map)
        if parsed.get("pattern_id") and isinstance(parsed["pattern_id"], list):
            parsed["pattern_id"] = parsed["pattern_id"][0] if parsed["pattern_id"] else None
        periods.append(parsed)
    
    return periods
