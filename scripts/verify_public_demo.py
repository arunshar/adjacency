#!/usr/bin/env python3
"""Exercise the hosted Autopsy through a phone-sized browser viewport."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--screenshot", type=Path, required=True)
    args = parser.parse_args()
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(
            viewport={"width": 844, "height": 390},
            color_scheme="dark",
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

        page.screenshot(path=str(args.screenshot), full_page=True)
        print(f"public mobile interaction passed: {page.url}")
        print("observed: DEMO MODE, delta columns, G1 gate failure, cited media, audit payload")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
