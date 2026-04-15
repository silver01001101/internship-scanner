# internship-scanner

scans if internships can be applied to in 1st year

## Run locally

```bash
cd <repository-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python scrape_first_year_eligibility.py --input internships.csv --output internships_with_first_year.csv
```

This generates `internships_with_first_year.csv` with a `First Year Eligible` column set to `TRUE` or `FALSE`.
