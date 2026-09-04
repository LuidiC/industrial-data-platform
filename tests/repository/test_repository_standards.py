from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
RULES_FILE = DOCS / "data-quality" / "rules.yaml"
CONTRACT_ROOT = DOCS / "data-contracts"
CONTRACT_TEMPLATE_FILE = CONTRACT_ROOT / "contract-template.yaml"
CONTRACT_FILES = sorted(
    path for path in CONTRACT_ROOT.rglob("*.yaml") if path != CONTRACT_TEMPLATE_FILE
)
YAML_FILES = sorted(DOCS.rglob("*.yaml"))

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DQ_ID_PATTERN = re.compile(r"^DQ-[A-Z][A-Z0-9]{1,9}-\d{3}$")
CONTRACT_KEYS = {"dataset", "version", "description", "logical_owner", "fields"}
FIELD_KEYS = {"name", "type", "required", "unique", "description", "example"}
RULE_KEYS = {"id", "domain", "description", "severity", "disposition"}


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=lambda path: str(path.relative_to(ROOT)))
def test_yaml_files_are_valid_and_non_empty(yaml_file: Path) -> None:
    assert load_yaml(yaml_file) is not None


def test_at_least_one_concrete_contract_is_discoverable() -> None:
    assert CONTRACT_FILES


@pytest.mark.parametrize(
    "contract_file", CONTRACT_FILES, ids=lambda path: str(path.relative_to(ROOT))
)
def test_contracts_follow_minimum_structure(contract_file: Path) -> None:
    contract = load_yaml(contract_file)

    assert isinstance(contract, dict)
    assert CONTRACT_KEYS <= contract.keys()
    assert SEMVER_PATTERN.fullmatch(str(contract["version"]))
    assert isinstance(contract["fields"], list) and contract["fields"]

    field_names: list[str] = []
    for field in contract["fields"]:
        assert isinstance(field, dict)
        assert FIELD_KEYS <= field.keys()
        assert isinstance(field["name"], str) and field["name"]
        assert isinstance(field["required"], bool)
        assert isinstance(field["unique"], bool)
        field_names.append(field["name"])

        related_rules = field.get("related_dq_rules", [])
        assert isinstance(related_rules, list)
        assert all(DQ_ID_PATTERN.fullmatch(rule_id) for rule_id in related_rules)

    assert len(field_names) == len(set(field_names))


def test_data_quality_rule_catalog_follows_convention() -> None:
    catalog = load_yaml(RULES_FILE)

    assert isinstance(catalog, dict)
    assert SEMVER_PATTERN.fullmatch(str(catalog["catalog_version"]))
    assert isinstance(catalog.get("rules"), list) and catalog["rules"]

    rule_ids: list[str] = []
    for rule in catalog["rules"]:
        assert isinstance(rule, dict)
        assert RULE_KEYS <= rule.keys()
        assert DQ_ID_PATTERN.fullmatch(rule["id"])
        assert rule["severity"] in {"error", "warning"}
        assert rule["disposition"] in {"quarantine", "observe"}
        rule_ids.append(rule["id"])

    assert len(rule_ids) == len(set(rule_ids))


def test_contract_data_quality_references_exist_in_catalog() -> None:
    catalog = load_yaml(RULES_FILE)
    known_rule_ids = {rule["id"] for rule in catalog["rules"]}

    for contract_file in CONTRACT_FILES:
        contract = load_yaml(contract_file)
        referenced_rule_ids = {
            rule_id for field in contract["fields"] for rule_id in field.get("related_dq_rules", [])
        }
        assert referenced_rule_ids <= known_rule_ids
