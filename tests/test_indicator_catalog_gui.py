"""Static completeness checks for the GUI indicator catalog (no browser)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui" / "src"


def test_indicator_catalog_covers_all_keys():
    chart_layers = (GUI / "chartLayers.ts").read_text(encoding="utf-8")
    catalog = (GUI / "indicatorCatalog.ts").read_text(encoding="utf-8")
    for key in (
        "htf_bias", "liquidity_sweep", "fvg_retest", "retest_confirmation", "smt", "structure",
        "liquidity", "fvgZones", "entry", "stop", "targets", "patterns",
        "rising_wedge", "falling_wedge", "ascending_triangle", "descending_triangle",
        "flag", "pennant", "double_top", "double_bottom",
    ):
        assert key in chart_layers
        assert f"{key}:" in catalog or f'"{key}"' in catalog or f"'{key}'" in catalog


def test_guide_and_search_ui_wired():
    app = (GUI / "App.tsx").read_text(encoding="utf-8")
    rail = (GUI / "WatchlistRail.tsx").read_text(encoding="utf-8")
    assert "IndicatorGuide" in app
    assert "openGuide" in app
    assert "guide-launch" in app
    assert "last_price" in rail
    assert "display_name" in rail
    assert (GUI / "IndicatorGuide.tsx").is_file()
