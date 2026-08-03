#!/usr/bin/env python3
"""Exercise the hosted Autopsy and verify its theme contrast in a real browser."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

RGB_PATTERN = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)")
EXPECTED_COLORS = {
    "light": {
        "badge_background": (236, 253, 245),
        "badge_text": (6, 95, 70),
        "banner_background": (255, 241, 242),
        "banner_text": (127, 29, 29),
        "heading_text": (127, 29, 29),
    },
    "dark": {
        "badge_background": (18, 55, 42),
        "badge_text": (167, 243, 208),
        "banner_background": (69, 10, 10),
        "banner_text": (254, 202, 202),
        "heading_text": (254, 202, 202),
    },
}


def _rgb(value: str) -> tuple[int, int, int]:
    match = RGB_PATTERN.fullmatch(value)
    if match is None:
        raise AssertionError(f"expected an opaque RGB color, got {value!r}")
    alpha = match.group(4)
    if alpha is not None and float(alpha) < 1:
        raise AssertionError(f"expected an opaque RGB color, got {value!r}")
    return tuple(int(channel) for channel in match.groups()[:3])


def _relative_luminance(color: tuple[int, int, int]) -> float:
    channels = []
    for value in color:
        channel = value / 255
        channels.append(
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def _verify_theme(page, color_scheme: str) -> dict[str, object]:
    observed = page.evaluate(
        """() => {
          const style = (selector) => {
            const computed = getComputedStyle(document.querySelector(selector));
            return {color: computed.color, background: computed.backgroundColor};
          };
          return {
            darkClass: document.body.classList.contains('dark'),
            badge: style('.mode-badge'),
            banner: style('div.block.gate-banner'),
            heading: style('.gate-banner h2')
          };
        }"""
    )
    if observed["darkClass"] != (color_scheme == "dark"):
        raise AssertionError(f"Gradio did not render the requested {color_scheme} theme")

    colors = {
        "badge_background": _rgb(observed["badge"]["background"]),
        "badge_text": _rgb(observed["badge"]["color"]),
        "banner_background": _rgb(observed["banner"]["background"]),
        "banner_text": _rgb(observed["banner"]["color"]),
        "heading_text": _rgb(observed["heading"]["color"]),
    }
    if colors != EXPECTED_COLORS[color_scheme]:
        raise AssertionError(
            f"{color_scheme} theme colors differ from the reviewed palette: {colors}"
        )

    badge_contrast = _contrast(colors["badge_text"], colors["badge_background"])
    banner_contrast = _contrast(colors["banner_text"], colors["banner_background"])
    heading_contrast = _contrast(colors["heading_text"], colors["banner_background"])
    for label, ratio in (
        ("badge", badge_contrast),
        ("banner", banner_contrast),
        ("heading", heading_contrast),
    ):
        if ratio < 4.5:
            raise AssertionError(f"{color_scheme} {label} contrast is only {ratio:.2f}:1")

    return {
        "color_scheme": color_scheme,
        "colors": {key: list(value) for key, value in colors.items()},
        "contrast": {
            "badge": round(badge_contrast, 2),
            "banner": round(banner_contrast, 2),
            "heading": round(heading_contrast, 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--color-scheme", choices=("light", "dark"), default="dark")
    parser.add_argument("--screenshot", type=Path, required=True)
    args = parser.parse_args()
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(
            viewport={"width": 844, "height": 390},
            color_scheme=args.color_scheme,
            device_scale_factor=2,
            has_touch=True,
            is_mobile=True,
        )
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
        page.get_by_text("DEMO MODE", exact=False).wait_for(timeout=30_000)
        page.get_by_role("button", name="Run Autopsy").click()
        gate = page.locator("#gate-fail-row")
        gate.wait_for(state="visible", timeout=30_000)
        gate.click()

        page.get_by_text("Collection of 127 scientific diagrams", exact=False).first.wait_for(
            timeout=30_000
        )
        page.get_by_text("display_only_rationale", exact=False).first.wait_for(timeout=30_000)
        page.wait_for_function(
            """() => Array.from(document.querySelectorAll('img[src]')).some(
                (image) => image.naturalWidth > 200 && image.naturalHeight > 100
            )""",
            timeout=30_000,
        )
        page.get_by_text("Cited media region", exact=False).first.scroll_into_view_if_needed()
        page.wait_for_timeout(1_000)

        for label in ("AGREE", "OVER_BLOCK", "UNDER_BLOCK", "Audit drawer"):
            page.get_by_text(label, exact=False).first.wait_for(timeout=30_000)

        theme_report = _verify_theme(page, args.color_scheme)
        page.screenshot(path=str(args.screenshot), full_page=True)
        print(f"public mobile interaction passed: {page.url}")
        print(f"theme contrast passed: {theme_report}")
        print("observed: DEMO MODE, delta columns, G1 gate failure, cited media, audit payload")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
