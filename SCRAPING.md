## Scraping coupon codes from simplycodes.com

This repository includes `scrape_simplycodes.py`, a Playwright-based scraper that extracts likely coupon code strings from a SimplyCodes page (and optional pagination).

### 1) Install dependencies

```bash
python -m pip install playwright
python -m playwright install chromium
```

### 2) Run the scraper

```bash
python scrape_simplycodes.py \
  --url "https://simplycodes.com/s/best-buy" \
  --max-pages 2 \
  --delay 2 \
  --out coupon_codes.csv
```

### Notes

- Respect the website's Terms of Service and `robots.txt`.
- Use low scrape rates (`--delay`) to avoid overloading the site.
- Some codes may be hidden behind interactions; this script only extracts visible/available text.
