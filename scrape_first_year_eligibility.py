#!/usr/bin/env python3
import argparse
import asyncio
import csv
import re
from pathlib import Path
from typing import Dict, List

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

OUTPUT_COLUMN = "First Year Eligible"

POSITIVE_PATTERNS = [
    r"\bfirst[- ]year\b",
    r"\byear\s*1\b",
    r"\bundergraduate\s+students\s+of\s+all\s+years\b",
    r"\ball\s+years\s+of\s+study\b",
    r"\bopen\s+to\s+all\s+students\b",
]

NEGATIVE_PATTERNS = [
    r"\bpenultimate\b",
    r"\bfinal\s+year\b",
    r"\bmust\s+be\s+in\s+(your\s+)?(second|2nd|third|3rd|fourth|4th)\s+year\b",
    r"\bnot\s+open\s+to\s+first[- ]year\b",
    r"\bminimum\s+of\s+(second|2nd)\s+year\b",
]


def classify_first_year_eligibility(text: str) -> str:
    lower_text = text.lower()

    if any(re.search(pattern, lower_text) for pattern in NEGATIVE_PATTERNS):
        return "FALSE"

    if any(re.search(pattern, lower_text) for pattern in POSITIVE_PATTERNS):
        return "TRUE"

    return "FALSE"


async def fetch_page_text(context, url: str, timeout_ms: int) -> str:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeoutError:
            pass

        body_text = await page.inner_text("body")
        title = await page.title()
        return f"{title}\n{body_text}"
    finally:
        await page.close()


async def process_rows(rows: List[Dict[str, str]], timeout_ms: int, headless: bool) -> List[Dict[str, str]]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(ignore_https_errors=True)

        try:
            for row in rows:
                link = (row.get("Link") or "").strip()
                if not link:
                    row[OUTPUT_COLUMN] = "FALSE"
                    continue

                try:
                    text = await fetch_page_text(context, link, timeout_ms)
                    row[OUTPUT_COLUMN] = classify_first_year_eligibility(text)
                except Exception:
                    row[OUTPUT_COLUMN] = "FALSE"
        finally:
            await context.close()
            await browser.close()

    return rows


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_fieldnames(existing_fieldnames: List[str]) -> List[str]:
    if OUTPUT_COLUMN in existing_fieldnames:
        return existing_fieldnames
    return [*existing_fieldnames, OUTPUT_COLUMN]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape internship links and add TRUE/FALSE first-year eligibility column."
    )
    parser.add_argument(
        "--input",
        default="internships.csv",
        help="Input CSV path (default: internships.csv)",
    )
    parser.add_argument(
        "--output",
        default="internships_with_first_year.csv",
        help="Output CSV path (default: internships_with_first_year.csv)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=20000,
        help="Per-page navigation timeout in milliseconds (default: 20000)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (default is headless)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    rows = read_csv(input_path)
    if not rows:
        raise ValueError("Input CSV contains no rows.")

    existing_fieldnames = list(rows[0].keys())
    fieldnames = build_fieldnames(existing_fieldnames)

    processed_rows = asyncio.run(
        process_rows(rows=rows, timeout_ms=args.timeout_ms, headless=not args.headed)
    )

    write_csv(output_path, processed_rows, fieldnames)


if __name__ == "__main__":
    main()
