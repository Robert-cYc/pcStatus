from collections import namedtuple

from temperature import (
    TemperatureReader,
    parse_acpi_output,
    parse_lhm_tree,
    pick_psutil_temp,
)

Entry = namedtuple("Entry", "label current high critical")


def test_pick_psutil_temp_prefers_package_label() -> None:
    sensors = {
        "coretemp": [Entry("Core 0", 50.0, None, None), Entry("Package id 0", 62.0, None, None)],
        "nvme": [Entry("Composite", 90.0, None, None)],
    }
    assert pick_psutil_temp(sensors) == 62.0


def test_pick_psutil_temp_falls_back_to_any_chip() -> None:
    sensors = {"nvme": [Entry("Composite", 41.0, None, None)]}
    assert pick_psutil_temp(sensors) == 41.0


def test_pick_psutil_temp_empty() -> None:
    assert pick_psutil_temp({}) is None


def test_parse_lhm_tree_prefers_cpu_package() -> None:
    tree = {
        "Text": "Sensor",
        "Children": [{
            "Text": "PC",
            "Children": [
                {"Text": "GPU Core", "Value": "80.0 °C", "Children": []},
                {"Text": "Core #1", "Value": "55,0 °C", "Children": []},
                {"Text": "CPU Package", "Value": "61.0 °C", "Children": []},
            ],
        }],
    }
    assert parse_lhm_tree(tree) == 61.0


def test_parse_lhm_tree_ignores_gpu_and_non_temp() -> None:
    tree = {"Text": "root", "Children": [
        {"Text": "GPU Core", "Value": "80.0 °C", "Children": []},
        {"Text": "CPU Total", "Value": "12.0 %", "Children": []},
    ]}
    assert parse_lhm_tree(tree) is None


def test_parse_acpi_output_converts_tenths_of_kelvin() -> None:
    # 3231 -> 323.1 K -> 49.95 C
    assert round(parse_acpi_output("3231\r\n3000\r\n") or 0, 1) == 50.0


def test_parse_acpi_output_invalid() -> None:
    assert parse_acpi_output("") is None
    assert parse_acpi_output("not a number") is None


def test_reader_returns_none_without_sources() -> None:
    reader = TemperatureReader(lhm_url="")
    reader._psutil_supported = False
    reader._acpi_supported = False
    assert reader.read() is None
