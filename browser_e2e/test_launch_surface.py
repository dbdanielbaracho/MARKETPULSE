from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

from browser_e2e.test_predibeacon_browser import _new_page


def test_home_has_unique_ids_and_named_interactive_controls(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            duplicate_ids = page.evaluate(
                """() => {
                  const ids = [...document.querySelectorAll('[id]')].map(el => el.id).filter(Boolean);
                  return [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
                }"""
            )
            assert duplicate_ids == []

            unnamed = page.evaluate(
                """() => [...document.querySelectorAll('a,button,input,select,textarea,[role="button"]')]
                  .filter(el => {
                    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.value || '').trim();
                    return !name;
                  })
                  .map(el => el.outerHTML.slice(0, 180))"""
            )
            assert unnamed == []
            assert not errors
        finally:
            context.close()
            browser.close()


def test_three_venue_choices_are_focusable_and_semantically_named(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            for venue, expected_name in (
                ("kalshi", "Kalshi"),
                ("all", "PrediBeacon"),
                ("polymarket", "Polymarket"),
            ):
                control = page.locator(f"[data-venue-link='{venue}']").first
                expect(control).to_be_visible()
                control.focus()
                assert control.evaluate("el => document.activeElement === el")
                accessible = (control.get_attribute("aria-label") or control.text_content() or "").strip()
                assert expected_name.casefold() in accessible.casefold(), (venue, accessible)
            assert not errors
        finally:
            context.close()
            browser.close()


def test_home_heading_structure_has_single_primary_heading(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            assert page.locator("h1").count() == 1
            expect(page.locator("h1")).to_be_visible()
            text = (page.locator("h1").text_content() or "").strip()
            assert text
            assert not errors
        finally:
            context.close()
            browser.close()


def test_all_visible_internal_home_links_have_safe_targets(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            hrefs = page.locator("a[href]").evaluate_all(
                "els => els.filter(el => getComputedStyle(el).display !== 'none').map(el => el.getAttribute('href'))"
            )
            unsafe = [
                href for href in hrefs
                if href and (href.lower().startswith("javascript:") or href.lower().startswith("data:"))
            ]
            assert unsafe == []
            internal = [href for href in hrefs if href and href.startswith("/")]
            assert internal
            for href in sorted(set(internal)):
                path = href.split("#", 1)[0]
                response = page.request.get(base_url + path, timeout=15_000)
                assert response.status < 500, (href, response.status)
            assert not errors
        finally:
            context.close()
            browser.close()
