import pytest
import json
import yaml
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from audit import load_resources, filter_resources, format_json, format_table, build_parser, main


SAMPLE = [
    {"id": "vm-001", "type": "VirtualMachine", "region": "eastus", "tags": {"env": "prod"}, "compliant": True},
    {"id": "sa-001", "type": "StorageAccount", "region": "westeurope", "tags": {"env": "dev"}, "compliant": False},
    {"id": "vm-002", "type": "VirtualMachine", "region": "westeurope", "tags": {}, "compliant": True},
    {"id": "pip-001", "type": "PublicIPAddress", "region": "eastus", "tags": {}, "compliant": False},
]


@pytest.fixture
def yaml_file(tmp_path):
    f = tmp_path / "resources.yaml"
    f.write_text(yaml.dump(SAMPLE))
    return str(f)


class TestLoadResources:
    def test_loads_yaml(self, yaml_file):
        resources = load_resources(yaml_file)
        assert len(resources) == 4

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_resources("/nonexistent.yaml")

    def test_invalid_yaml_structure(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: value\nnested: true")  # dict, pas une liste
        with pytest.raises(ValueError):
            load_resources(str(f))


class TestFilterResources:
    def test_no_filter_returns_all(self):
        assert len(filter_resources(SAMPLE)) == 4

    def test_filter_by_type(self):
        result = filter_resources(SAMPLE, resource_type="VirtualMachine")
        assert len(result) == 2

    def test_filter_by_type_case_insensitive(self):
        assert len(filter_resources(SAMPLE, resource_type="virtualmachine")) == 2

    def test_filter_by_region(self):
        assert len(filter_resources(SAMPLE, region="eastus")) == 2

    def test_filter_non_compliant(self):
        result = filter_resources(SAMPLE, non_compliant_only=True)
        assert len(result) == 2
        assert all(not r["compliant"] for r in result)

    def test_combined_filters(self):
        result = filter_resources(SAMPLE, resource_type="StorageAccount", non_compliant_only=True)
        assert len(result) == 1
        assert result[0]["id"] == "sa-001"


class TestFormatters:
    def test_format_json_parseable(self):
        output = format_json(SAMPLE[:2])
        parsed = json.loads(output)
        assert len(parsed) == 2

    def test_format_table_has_headers(self):
        output = format_table(SAMPLE[:1])
        assert "ID" in output
        assert "TYPE" in output
        assert "REGION" in output
        assert "COMPLIANT" in output

    def test_format_table_has_data(self):
        output = format_table(SAMPLE[:1])
        assert "vm-001" in output

    def test_format_empty_table_still_has_header(self):
        output = format_table([])
        assert "ID" in output


class TestCLI:
    def test_help_exits_0(self):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0

    def test_basic_run_exits_0(self, yaml_file):
        assert main(["--input", yaml_file]) == 0

    def test_json_output(self, yaml_file, capsys):
        main(["--input", yaml_file, "--output", "json"])
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 4

    def test_filter_via_cli(self, yaml_file, capsys):
        main(["--input", yaml_file, "--resource-type", "VirtualMachine", "--output", "json"])
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 2

    def test_file_not_found_returns_1(self):
        assert main(["--input", "/nonexistent.yaml"]) == 1

    def test_dry_run_exits_0(self, yaml_file):
        assert main(["--input", yaml_file, "--dry-run"]) == 0
