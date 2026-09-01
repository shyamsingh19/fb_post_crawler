# Facebook Post Crawler - Rental Listings Scraper

A Python-based web scraper that crawls Facebook groups for rental listing posts, extracts structured information (price, rooms, etc.), and stores the data in a SQLite database. Built with stealth capabilities to avoid detection.

## 💡 Motivation

I was searching for a vegetarian male flatmate replacement in Hyderabad. Facebook groups had thousands of posts, but filtering through them manually wasted hours of research time. This tool automates the tedious process of extracting rental prices, room counts, and other details from unstructured post text.

## ⚠️ Why I Left This Project

**The Fundamental Problem with Facebook Scraping:**

If Meta changes an internal HTML class name or GraphQL parameter on a Tuesday, your script breaks until you inspect the DOM and fix it manually.

This project was abandoned because:
- Meta frequently updates their internal HTML structure without warning
- GraphQL API parameters change unpredictably
- Maintenance becomes a never-ending game of "chase the changes"
- A single CSS class rename breaks the entire crawler
- No stable, documented API means constant firefighting

---

## Features

- **Stealth Web Crawling**: Uses Playwright with anti-detection measures
- **Rental Data Extraction**: Automatically extracts:
  - Post ID and URL
  - Author name and group information
  - Rental price (supports USD/INR currency detection)
  - Number of rooms (BHK format support)
  - Post timestamp and full text
- **Database Storage**: SQLite database with indexed queries for price and group filtering
- **Async Processing**: Efficient asynchronous request handling with httpx
- **Environment Configuration**: Easy setup with `.env` file
- **Comprehensive Logging**: Detailed debug and info logs for monitoring

## Project Structure

```
fb_post_crawler/
├── stealth_crawler_engine.py    # Main crawler and data processing engine
├── requirements.txt              # Python dependencies
├── tests/
│   └── featherless_test.py      # Test with Featherless AI integration
├── myenv/                        # Python virtual environment
└── README.md                     # This file
```

## Requirements

- Python 3.12+
- Virtual environment (myenv)

## Setup

### 1. Install Dependencies

```bash
cd fb_post_crawler
pip install -r requirements.txt
```

### 2. Create Environment File

Create a `.env` file in the project root with the following variables:

```env
# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Scraper API configuration
SCRAPER_API_KEY=your_scraper_api_key
SCRAPER_DATASET_ID=your_dataset_id

# OpenAI/Featherless API (for text processing)
CRAWLER_API_KEY=your_api_key
```

### 3. Activate Virtual Environment

```bash
source myenv/bin/activate
```

## Usage

### Basic Crawling

```python
from stealth_crawler_engine import StealthCrawlerEngine

crawler = StealthCrawlerEngine()
# Configure and run crawler
```

### Data Extraction

The crawler automatically extracts:

```python
from stealth_crawler_engine import TextParsingEngine, PostDTO

# Extract price from text
price = TextParsingEngine.extract_price("2BHK, ₹15,000/month")

# Extract rooms from text
rooms = TextParsingEngine.extract_rooms("Looking for flatmate in 2BHK")
```

### Database Queries

```python
from stealth_crawler_engine import DatabaseStorageManager

db = DatabaseStorageManager("facebook_crawled_data.db")

# Save post
db.save_post(post_dto)

# Query posts by price range
posts = db.get_posts_by_price_range(min_price, max_price)

# Query posts by group
posts = db.get_posts_by_group(group_url)
```

## Dependencies

- **beautifulsoup4**: HTML parsing
- **httpx**: Async HTTP requests
- **playwright**: Browser automation with stealth mode
- **pydantic**: Data validation
- **python-dotenv**: Environment variable management
- **openai**: AI-powered text processing

See `requirements.txt` for complete list and versions.

## Database Schema

### facebook_posts Table

| Column | Type | Notes |
|--------|------|-------|
| post_id | TEXT | Primary key, unique identifier |
| group_url | TEXT | Facebook group URL (indexed) |
| author_name | TEXT | Post author name |
| post_text | TEXT | Full post content |
| extracted_price | REAL | Extracted rental price (indexed) |
| extracted_rooms | REAL | Extracted number of rooms |
| post_url | TEXT | Direct link to the post |
| timestamp | TEXT | Post timestamp |
| scraped_at | DATETIME | Timestamp when scraped |

## Regular Expressions

### Price Pattern
Detects prices in formats:
- `$5,000`, `₹15,000`, `15000 USD`, etc.
- Range: ₹100 - ₹500,000

### Rooms Pattern
Detects room counts in formats:
- `2BHK`, `2 bedroom`, `2 bed`, `2.5 rooms`, etc.

## Features in Development

- [ ] Web UI for browsing crawled data
- [ ] Advanced filtering and search
- [ ] Export to CSV/JSON
- [ ] Scheduled recurring crawls
- [ ] Multi-group support

## Testing

Run tests with:

```bash
python -m pytest tests/
```

Or run the Featherless AI test:

```bash
python tests/featherless_test.py
```

## Logging

Logging level can be controlled via the `LOG_LEVEL` environment variable:

```bash
LOG_LEVEL=DEBUG python stealth_crawler_engine.py
```

Log messages include:
- `[database:init]` - Database initialization
- `[database:write]` - Data persistence operations
- Crawler activity and status updates

## Notes

- Database file (`facebook_crawled_data.db`) is created automatically on first run
- Posts are stored idempotently (duplicates are ignored or updated)
- Requires valid API credentials for scraper services
- Always respect Facebook's Terms of Service and robots.txt

## License

[Specify your license here]

## Contributing

[Contribution guidelines here]
