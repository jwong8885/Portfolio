#!/usr/bin/env python3
"""Scrape coupon codes from simplycodes.com search/store pages.

Usage examples:
  python scrape_simplycodes.py --url "https://simplycodes.com/s/best-buy"
  python scrape_simplycodes.py --url "https://simplycodes.com" --max-pages 2

Notes:
- Respect the target site's Terms of Service and robots.txt.
- Add delays and keep request volume low.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from playwright.async_api import async_playwright, Page

CODE_RE = re.compile(r"\b[A-Z0-9]{4,20}\b")


@dataclass
class Coupon:
    code: str
    description: str
    store: str
    source_url: str


async def extract_coupons(page: Page, source_url: str) -> list[Coupon]:
    """Extract likely coupon codes and nearby context from the current page."""
    coupons: list[Coupon] = []

    # Try to capture code-like snippets from likely code containers.
    candidate_selectors = [
        '[data-testid*="code"]',
        '[class*="code"]',
        'button[aria-label*="code" i]',
        'button:has-text("Copy")',
        'button:has-text("Reveal")',
    ]

    seen: set[str] = set()
    for selector in candidate_selectors:
        loc = page.locator(selector)
        count = await loc.count()
        for i in range(count):
            text = (await loc.nth(i).inner_text()).strip().upper()
            for match in CODE_RE.findall(text):
                if match in seen:
                    continue
                seen.add(match)
                row_text = (await loc.nth(i).locator("xpath=ancestor::*[self::article or self::li or self::div][1]").inner_text())[:240]
                coupons.append(
                    Coupon(code=match, description=" ".join(row_text.split()), store="", source_url=source_url)
                )

    # Fallback: scan visible text for code-like tokens near the word "code".
    if not coupons:
        body = (await page.locator("body").inner_text()).upper()
        for line in body.splitlines():
            if "CODE" not in line:
                continue
            for match in CODE_RE.findall(line):
                if match not in seen:
                    seen.add(match)
                    coupons.append(Coupon(code=match, description=line.strip()[:240], store="", source_url=source_url))

    return coupons


def dedupe(coupons: Iterable[Coupon]) -> list[Coupon]:
    seen: set[tuple[str, str]] = set()
    out: list[Coupon] = []
    for c in coupons:
        key = (c.code, c.source_url)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


async def scrape(start_url: str, max_pages: int, delay_s: float) -> list[Coupon]:
    all_coupons: list[Coupon] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = start_url
        for _ in range(max_pages):
            await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            await page.wait_for_timeout(int(delay_s * 1000))

            all_coupons.extend(await extract_coupons(page, page.url))

            next_link = page.locator('a[rel="next"], a:has-text("Next")').first
            if await next_link.count() == 0:
                break
            href = await next_link.get_attribute("href")
            if not href:
                break
            if href.startswith("http"):
                url = href
            else:
                url = page.url.rstrip("/") + "/" + href.lstrip("/")

        await browser.close()
    return dedupe(all_coupons)


def write_csv(rows: list[Coupon], out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "description", "store", "source_url"])
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape coupon codes from simplycodes.com pages")
    parser.add_argument("--url", required=True, help="Starting page URL")
    parser.add_argument("--max-pages", type=int, default=1, help="Max pages to scrape")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay in seconds after each page load")
    parser.add_argument("--out", default="coupon_codes.csv", help="CSV output path")
    args = parser.parse_args()

    coupons = await scrape(args.url, args.max_pages, args.delay)
    write_csv(coupons, Path(args.out))
    print(f"Wrote {len(coupons)} coupon codes to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
