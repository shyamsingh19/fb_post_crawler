# Facebook Post Crawler

Scrapes Facebook groups for rental listings and extracts structured data (price, rooms) into SQLite.

## 💡 Motivation

Searching for a vegetarian male flatmate in Hyderabad. Manually filtering thousands of Facebook posts was tedious, so I built this to automate data extraction.

## ⚠️ Why Abandoned

If Meta changes an internal HTML class name on a Tuesday, the script breaks until you manually fix it. **Use Meta's official APIs instead.**

## Setup

```bash
pip install -r requirements.txt
```

Configure `.env`:
```
LOG_LEVEL=INFO
SCRAPER_API_KEY=your_key
SCRAPER_DATASET_ID=your_id
CRAWLER_API_KEY=your_key
```

## What It Does

- Scrapes Facebook posts with Playwright (stealth mode)
- Extracts rental price and room count via regex
- Stores in SQLite with indexed queries

## Data Extraction

```python
from stealth_crawler_engine import TextParsingEngine, DatabaseStorageManager

# Extract price/rooms
price = TextParsingEngine.extract_price("2BHK, ₹15,000/month")
rooms = TextParsingEngine.extract_rooms("2BHK apartment")

# Save to database
db = DatabaseStorageManager()
db.save_post(post)
```

## Database Schema

**facebook_posts** table:
- `post_id` (PRIMARY KEY)
- `group_url`, `author_name`, `post_text`
- `extracted_price`, `extracted_rooms`
- `post_url`, `timestamp`, `scraped_at`

## Status

**⚠️ No longer maintained. Use at your own risk.**
