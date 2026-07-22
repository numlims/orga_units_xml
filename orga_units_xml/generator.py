from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import tr
import yaml
from lxml import etree as ET

from .templating import render_template_value

traction = tr.traction("num_test")
NS = "http://www.kairos-med.de"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ADDRESS_FIELDS: tuple[tuple[str, str], ...] = (
    ("city", "City"),
    ("country_descriptor", "Country"),
    ("email", "Email"),
    ("fax", "Fax"),
    ("mobile", "Mobile"),
    ("phone1", "Phone1"),
    ("phone2", "Phone2"),
    ("po_box", "PoBox"),
    ("street", "Street"),
    ("street_no", "StreetNo"),
    ("zip_code", "Zipcode"),
)


def _tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def _clean_text(value: Any, fallback: str = "") -> str:
    return str(fallback if value is None else value).strip()


def _add_text_element(parent: ET._Element, tag_name: str, value: Any) -> ET._Element:
    element = ET.SubElement(parent, _tag(tag_name))
    element.text = _clean_text(value)
    return element


def _extract_value(source: Any | None, field_names: tuple[str, ...]) -> Any:
    if source is None:
        return ""

    for field_name in field_names:
        if isinstance(source, dict):
            value = source.get(field_name)
        else:
            value = getattr(source, field_name, None)
        if value not in (None, ""):
            return value
    return ""


def _populate_address(address: ET._Element, source: Any | None) -> None:
    for source_field, xml_field in ADDRESS_FIELDS:
        value = _extract_value(source, (source_field,))
        clean_value = _clean_text(value)

        if not clean_value:
            continue
        _add_text_element(address, xml_field, clean_value)


def _add_org_unit_entry(parent_item: ET._Element, lang: str, name: str) -> None:
    entry = ET.SubElement(parent_item, _tag("OrganisationUnitEntries"))
    _add_text_element(entry, "Name", name)
    _add_text_element(entry, "Description", name)
    _add_text_element(entry, "Lang", lang)


def _add_org_unit_item(catalogue_data: ET._Element, ou: dict[str, Any]) -> None:
    item = ET.SubElement(catalogue_data, _tag("OrganisationUnitCatalogueItem"))

    code = _clean_text(ou["code"])
    name_de = _clean_text(ou.get("name_de") or code)
    name_en = _clean_text(ou.get("name_en") or name_de)

    _add_text_element(item, "Code", code)

    # Keep master-data payload minimal and schema-safe for OrganisationUnit import.
    # The validator error indicates NameMultilingualEntries is not allowed here.
    parent_code = ou.get("parent_code")
    if parent_code:
        _add_text_element(item, "ParentRef", parent_code)

    _add_org_unit_entry(item, "de", name_de)
    _add_org_unit_entry(item, "en", name_en)


def _parse_active_until(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    text = _clean_text(value)
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _validate_traction_user_is_active(
    traction_user: Any, requested_username: str
) -> None:
    username = _clean_text(getattr(traction_user, "username", requested_username))
    entitystatus = _clean_text(getattr(traction_user, "entitystatus", "")).upper()
    if entitystatus != "ACTIVE":
        raise ValueError(
            f"User '{username}' is invalid: entitystatus must be 'ACTIVE', got '{entitystatus or '<empty>'}'. please remove the user in YAML or ensure the user is active in the CentraXX."
        )

    active_until_raw = getattr(traction_user, "active_until", None)
    try:
        active_until = _parse_active_until(active_until_raw)
    except ValueError as exc:
        raise ValueError(
            f"User '{username}' is invalid: active_until '{active_until_raw}' is not a valid ISO datetime."
        ) from exc

    # In Traction, NULL/empty active_until means unlimited validity.
    if active_until is None:
        return

    now = datetime.now(tz=active_until.tzinfo)
    if active_until <= now:
        raise ValueError(
            f"User '{username}' is invalid: active_until '{active_until.isoformat()}' is expired. Please remove the user in YAML or ensure the user is active and has a valid active_until date in the CentraXX."
        )


def _get_required_active_traction_user(username: str) -> Any:
    user_details = traction.user(usernames=[username], verbose_all=True)
    if not user_details:
        raise ValueError(
            f"User '{username}' not found in CentraXX. Please correct the username in the YAML or ensure the user exists in the CentraXX."
        )

    traction_user = user_details[0]
    _validate_traction_user_is_active(traction_user, username)
    return traction_user


# assing only active users where entitystatus is ACTIVE and active_until date is not None or expired. If any user in traction doesn't exist, stop the process and raise an error.
def _assign_users_to_organisation_units(
    catalogue_data: ET._Element,
    all_organisation_unit_assignments: list[dict[str, Any]],
    organisation_units: list[dict[str, Any]],
) -> None:
    role_by_username: dict[str, str] = {}
    all_users = []
    for role in all_organisation_unit_assignments:
        role_name = _clean_text(role.get("role"))
        for user in role.get("users", []):
            username = _clean_text(user.get("username"))
            if username and username not in all_users:
                all_users.append(username)
            if username and username not in role_by_username:
                role_by_username[username] = role_name
    # if any user in traction doesn't exist, stop the process and raise an error
    for username in all_users:
        traction_user = _get_required_active_traction_user(username)
        participant = ET.SubElement(catalogue_data, _tag("Participant"))
        username_traction = _clean_text(getattr(traction_user, "username", username))
        if not username_traction:
            raise ValueError(f"User '{username_traction}' does not exist.")
        lastname_traction = _clean_text(
            getattr(traction_user, "lastname", "") or username_traction
        )

        _add_text_element(participant, "UserName", username_traction)
        _add_text_element(participant, "LastName", lastname_traction)

        # Emit an Address node even when no details are provided.
        address = ET.SubElement(participant, _tag("Address"))
        _populate_address(address, getattr(traction_user, "address", None))

        for org_unit in organisation_units:
            org = ET.SubElement(participant, _tag("OrganisationUnit"))
            _add_text_element(org, "OrganisationUnitRefs", org_unit["code"])
            _add_text_element(org, "RoleRef", role_by_username.get(username, ""))

        div_admin = str(bool(getattr(traction_user, "divisional_admin", True)))
        _add_text_element(participant, "DivisionalAdministrator", div_admin.lower())


def _append_unique(target: list[str], value: Any) -> None:
    clean_value = _clean_text(value)
    if clean_value and clean_value not in target:
        target.append(clean_value)


def _add_user_entry(
    user_entries: ET._Element,
    ref_tag_name: str,
    ref_value: str,
) -> None:
    user_entry = ET.SubElement(user_entries, _tag("UserEntry"))
    _add_text_element(user_entry, ref_tag_name, ref_value)


def _get_trial_field(trial: Any, field_name: str, fallback: Any = "") -> Any:
    if trial is None:
        return fallback

    if isinstance(trial, dict):
        return trial.get(field_name, fallback)

    return getattr(trial, field_name, fallback)


def _add_study_effect_data(
    root: ET._Element,
    study_permissions: dict[str, Any] | None = None,
    organisation_units: list[dict[str, Any]] | None = None,
) -> None:
    study_permissions = study_permissions or {}

    trial_code = _clean_text(study_permissions.get("study_code"))

    trial_details = traction.trial(trials=[trial_code]) if trial_code else []
    traction_trial = trial_details[0] if trial_details else None
    existing_users: list[str] = []
    existing_orgas: list[str] = []

    for username in _get_trial_field(traction_trial, "users", []):
        _append_unique(existing_users, username)

    for orga in _get_trial_field(traction_trial, "orgas", []):
        _append_unique(existing_orgas, orga)

    # append organisation units from YAML.
    for org_unit in organisation_units or []:
        _append_unique(existing_orgas, org_unit.get("code"))

    effect_data = ET.SubElement(root, _tag("EffectData"))
    flexi_study = ET.SubElement(effect_data, _tag("FlexiStudy"))

    profile_code = _clean_text(
        study_permissions.get("study_profile_ref") or "NUM-Studie"
    )
    _add_text_element(flexi_study, "StudyProfileRef", profile_code)

    xml_study_code = _clean_text(_get_trial_field(traction_trial, "code") or trial_code)

    if xml_study_code:
        _add_text_element(flexi_study, "Code", xml_study_code)

    study_name = _clean_text(_get_trial_field(traction_trial, "name") or xml_study_code)

    if study_name:
        _add_text_element(flexi_study, "Name", study_name)

    validated_users: list[str] = []
    for username in existing_users:
        traction_user = _get_required_active_traction_user(username)
        username_traction = _clean_text(getattr(traction_user, "username", username))
        if not username_traction:
            raise ValueError(f"User '{username}' does not exist.")
        _append_unique(validated_users, username_traction)

    if validated_users or existing_orgas:
        user_entries = ET.SubElement(flexi_study, _tag("UserEntries"))

        for username in validated_users:
            _add_user_entry(user_entries, "ParticipantRef", username)

        for orga in existing_orgas:
            _add_user_entry(user_entries, "OrganisationUnitRef", orga)


# storage location import (SampleLocationInstanceCatalogueItem, SubLocationInstance)


def _lookup_location(location_id: str) -> tuple[str, str]:
    location_details = (
        traction.location(locationids=[location_id]) if location_id else []
    )
    if not location_details:
        raise ValueError(f"Location '{location_id}' not found in CentraXX.")

    location_traction = location_details[0]
    return (
        _clean_text(getattr(location_traction, "location_id", location_id)),
        _clean_text(getattr(location_traction, "schema", "")),
    )


def _add_assigned_storage_sub_location(
    parent_location: ET._Element,
    sub_location: dict[str, Any],
    assigned_org_unit_ref: str,
) -> None:
    sub_location_instance = ET.SubElement(parent_location, _tag("SubLocationInstance"))
    _add_text_element(
        sub_location_instance, "AssignedOrganisationUnitRefs", assigned_org_unit_ref
    )

    location_id = _clean_text(sub_location.get("location_id"))
    location_schema_ref = _clean_text(sub_location.get("location_schema_ref"))
    if not location_schema_ref:
        _, location_schema_ref = _lookup_location(location_id)

    _add_text_element(sub_location_instance, "LocationID", location_id)
    _add_text_element(sub_location_instance, "LocationSchemaRef", location_schema_ref)
    _add_text_element(sub_location_instance, "LSecondID", assigned_org_unit_ref)
    _add_text_element(
        sub_location_instance,
        "InheritTemperature",
        str(sub_location.get("inherit_temperature", True)).lower(),
    )

    for inner_sub in sub_location.get("sub_locations", []):
        _add_assigned_storage_sub_location(
            sub_location_instance, inner_sub, assigned_org_unit_ref
        )


def _add_unassigned_storage_sub_location(
    parent_location: ET._Element,
    sub_location: dict[str, Any],
    assigned_org_unit_ref: str,
) -> None:
    sub_location_instance = ET.SubElement(parent_location, _tag("SubLocationInstance"))
    location_id = _clean_text(sub_location.get("location_id"))
    _, location_schema_ref = _lookup_location(location_id)

    _add_text_element(sub_location_instance, "LocationID", location_id)
    _add_text_element(sub_location_instance, "LocationSchemaRef", location_schema_ref)

    for inner_sub in sub_location.get("sub_locations", []):
        _add_assigned_storage_sub_location(
            sub_location_instance, inner_sub, assigned_org_unit_ref
        )


def _add_storage_location_items(
    catalogue_data: ET._Element,
    storage_locations_template: dict[str, Any],
    organisation_units: list[dict[str, Any]],
) -> None:
    root_location_yaml_import = _clean_text(
        storage_locations_template.get("root_location", {}).get("location_id")
    )
    root_location_id, root_location_schema = _lookup_location(root_location_yaml_import)

    sample_location_instance = ET.SubElement(
        catalogue_data, _tag("SampleLocationInstanceCatalogueItem")
    )
    _add_text_element(sample_location_instance, "LocationID", root_location_id)
    _add_text_element(
        sample_location_instance, "LocationSchemaRef", root_location_schema
    )
    for org_unit in organisation_units:
        rendered_template = render_template_value(storage_locations_template, org_unit)
        assigned_org_unit_ref = _clean_text(org_unit.get("code"))
        for sub_location in rendered_template.get("root_sub_locations", []):
            _add_unassigned_storage_sub_location(
                sample_location_instance, sub_location, assigned_org_unit_ref
            )


def _validate_input(data: dict[str, Any]) -> None:
    if "organisation_units" not in data:
        raise ValueError("Missing 'organisation_units' in YAML.")

    if "centers" not in data["organisation_units"]:
        raise ValueError("Missing 'organisation_units.centers' in YAML.")

    centers = data["organisation_units"]["centers"]
    if not isinstance(centers, list) or not centers:
        raise ValueError("'organisation_units.centers' must be a non-empty list.")

    required_fields = {"code", "name_de"}
    for i, center in enumerate(centers):
        missing = required_fields - set(center.keys())
        if missing:
            raise ValueError(f"Center index {i} is missing fields: {sorted(missing)}")
        if not str(center.get("parent_code", "")).strip():
            raise ValueError(f"Center index {i} must have non-empty 'parent_code'.")

    all_organisation_unit_assignments = data.get(
        "all_organisation_unit_assignments", []
    )
    if all_organisation_unit_assignments and not isinstance(
        all_organisation_unit_assignments, list
    ):
        raise ValueError(
            "'all_organisation_unit_assignments' must be a list if provided."
        )

    if "study" in data and not isinstance(data["study"], dict):
        raise ValueError("'study' must be a mapping/object if provided.")

    storage_template = data.get("storage_location_assignments_template")
    if storage_template is not None and not isinstance(storage_template, dict):
        raise ValueError(
            "'storage_location_assignments_template' must be a mapping/object if provided."
        )


def _build_exchange_root(metadata: dict[str, Any]) -> ET._Element:
    nsmap = {
        None: NS,
        "xsi": XSI_NS,
    }  # Default namespace and xsi prefix
    root = ET.Element(_tag("CentraXXDataExchange"), nsmap=nsmap)
    root.set(
        f"{{{XSI_NS}}}schemaLocation",
        f"{NS} ../CentraXXExchange.xsd",
    )
    _add_text_element(root, "Source", metadata.get("source", "XMLIMPORT"))
    return root


def build_xml_documents_from_yaml(yaml_path: Path) -> dict[str, ET._Element]:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Top-level YAML structure must be a mapping/object.")

    _validate_input(data)
    metadata = data.get("metadata", {})

    # Master data import (OrganisationUnitCatalogueItem)
    organisation_units_root = _build_exchange_root(metadata)
    master_catalogue_data = ET.SubElement(
        organisation_units_root, _tag("CatalogueData")
    )

    organisation_units = data["organisation_units"]["centers"]

    for center in organisation_units:
        _add_org_unit_item(master_catalogue_data, center)

    # User import (Participant with OU roles)
    users_root = _build_exchange_root(metadata)
    users_catalogue_data = ET.SubElement(users_root, _tag("CatalogueData"))

    all_organisation_unit_assignments = data.get(
        "all_organisation_unit_assignments", []
    )
    _assign_users_to_organisation_units(
        users_catalogue_data, all_organisation_unit_assignments, organisation_units
    )

    # Study import (EffectData/FlexiStudy)
    studies_root = _build_exchange_root(metadata)
    _add_study_effect_data(
        studies_root, data.get("study_permissions", {}), organisation_units
    )

    # Storage Location import (SampleLocationInstanceCatalogueItem, SubLocationInstance)
    storage_root = _build_exchange_root(metadata)
    storage_catalogue_data = ET.SubElement(storage_root, _tag("CatalogueData"))
    storage_locations = data.get("storage_location_assignments_template")
    if storage_locations:
        _add_storage_location_items(
            storage_catalogue_data, storage_locations, organisation_units
        )

    return {
        "1_organisation_units": organisation_units_root,
        "2_users": users_root,
        "3_studies": studies_root,
        "4_storage_locations": storage_root,
    }
