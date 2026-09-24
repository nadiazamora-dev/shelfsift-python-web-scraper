# ShelfSift

ShelfSift is a small Python web scraping project I made to collect structured book data from multiple pages automatically.

The demo uses Books to Scrape, a public website made specifically for practicing web scraping.

## what it collects

- book title
- price
- availability
- rating
- product URL

## how it works

The script starts on the first catalogue page, collects the books it finds and keeps following the next page until there are no more pages left.

After that, it saves everything into a CSV file and creates a short summary of the results.

## output

The project generates:

`output/books.csv`

`output/summary.txt`

The CSV contains the structured book data.

The summary includes:

- total books found
- average price
- cheapest book
- most expensive book

## run it

Install the dependencies:

```bash
pip install -r requirements.txt
```

Then run:

```bash
python scraper.py
```

## built with

- Python
- requests
- BeautifulSoup
- pandas

The website used in this demo is a public scraping practice site.
