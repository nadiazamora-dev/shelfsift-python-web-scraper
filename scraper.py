from pathlib import Path
from urllib.parse import urljoin
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://books.toscrape.com/"
START_URL = urljoin(BASE_URL, "catalogue/page-1.html")

OUTPUT_DIR = Path("output")

#durante las pruebas puedo poner 2 o 3 para no recorrer todo el sitio
#cuando quiera el resultado final lo dejo en None
MAX_PAGES = 2

#dejo una pausa corta entre paginas para no mandar todo de una
REQUEST_DELAY = 0.10

#si una pagina demora demasiado prefiero cortar la peticion
REQUEST_TIMEOUT = 15


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


#uso una sola sesion para reutilizar la conexion mientras recorro el sitio
def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)

    return session


#concentro las peticiones aca para no repetir la misma logica en todos lados
def get_page(session, url):
    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    except requests.RequestException as error:
        print(f"no pude abrir esta pagina: {url}")
        print(f"motivo: {error}")

        return None


#el sitio guarda el rating como palabra, asi que lo paso a numero
def rating_to_number(value):
    rating_map = {
        "One": 1,
        "Two": 2,
        "Three": 3,
        "Four": 4,
        "Five": 5,
    }

    return rating_map.get(value)


#convierto cosas como £41.74 en un numero que despues pueda calcular
def clean_price(value):
    cleaned = (
        value
        .replace("£", "")
        .replace("Â", "")
        .strip()
    )

    return float(cleaned)


#intento sacar el numero real del stock cuando aparece entre parentesis
def get_stock_number(text):
    match = re.search(r"\((\d+)\s+available\)", text)

    if match:
        return int(match.group(1))

    return None


#aca saco los datos que solamente aparecen cuando entro a la pagina del libro
def get_book_details(session, product_url):
    soup = get_page(
        session,
        product_url
    )

    if soup is None:
        return {
            "category": None,
            "upc": None,
            "stock": None,
        }

    breadcrumb = soup.select(
        "ul.breadcrumb li"
    )

    category = None

    #normalmente el penultimo elemento del breadcrumb es la categoria
    if len(breadcrumb) >= 3:
        category = breadcrumb[-2].get_text(
            strip=True
        )

    product_info = {}

    #convierto la tabla de detalles en un diccionario para usarla mas facil
    for row in soup.select(
        "table.table.table-striped tr"
    ):
        key = row.select_one("th")
        value = row.select_one("td")

        if key and value:
            product_info[
                key.get_text(strip=True)
            ] = value.get_text(
                " ",
                strip=True
            )

    availability = product_info.get(
        "Availability",
        ""
    )

    return {
        "category": category,
        "upc": product_info.get("UPC"),
        "stock": get_stock_number(
            availability
        ),
    }


#saco primero lo que aparece directamente en cada tarjeta del catalogo
def parse_book_card(session, book):
    title_element = book.select_one(
        "h3 a"
    )

    price_element = book.select_one(
        ".price_color"
    )

    availability_element = book.select_one(
        ".availability"
    )

    rating_element = book.select_one(
        ".star-rating"
    )

    title = title_element.get(
        "title",
        ""
    ).strip()

    price = clean_price(
        price_element.get_text(
            strip=True
        )
    )

    availability = (
        availability_element
        .get_text(
            " ",
            strip=True
        )
    )

    rating_classes = (
        rating_element.get(
            "class",
            []
        )
    )

    rating_word = (
        rating_classes[1]
        if len(rating_classes) > 1
        else None
    )

    rating = rating_to_number(
        rating_word
    )

    relative_url = title_element.get(
        "href",
        ""
    )

    product_url = urljoin(
        BASE_URL + "catalogue/",
        relative_url
    )

    #como ya tengo la url del libro aprovecho de buscar sus datos extra
    details = get_book_details(
        session,
        product_url
    )

    return {
        "title": title,
        "category": details["category"],
        "price_gbp": price,
        "rating": rating,
        "availability": availability,
        "stock": details["stock"],
        "upc": details["upc"],
        "product_url": product_url,
    }


#esta es la parte que va avanzando por el catalogo hasta que no quede next
def scrape_catalog():
    session = create_session()

    collected_books = []

    current_url = START_URL
    page_number = 1

    while current_url:
        if (
            MAX_PAGES is not None
            and page_number > MAX_PAGES
        ):
            break

        print(
            f"revisando pagina {page_number}..."
        )

        soup = get_page(
            session,
            current_url
        )

        if soup is None:
            print(
                "pare aca porque no pude leer la pagina del catalogo"
            )
            break

        book_cards = soup.select(
            "article.product_pod"
        )

        for position, book in enumerate(
            book_cards,
            start=1
        ):
            book_data = parse_book_card(
                session,
                book
            )

            collected_books.append(
                book_data
            )

            print(
                f"  libro {position}/{len(book_cards)}: "
                f"{book_data['title'][:55]}"
            )

            time.sleep(
                REQUEST_DELAY
            )

        next_button = soup.select_one(
            "li.next a"
        )

        if next_button:
            current_url = urljoin(
                current_url,
                next_button.get("href")
            )

            page_number += 1

        else:
            current_url = None

    session.close()

    pages_scraped = (
        min(
            page_number,
            MAX_PAGES
        )
        if MAX_PAGES is not None
        else page_number
    )

    return collected_books, pages_scraped


#hago un resumen que me sirva para revisar el resultado sin abrir todo el csv
def build_summary(df, pages_scraped):
    cheapest = df.loc[
        df["price_gbp"].idxmin()
    ]

    most_expensive = df.loc[
        df["price_gbp"].idxmax()
    ]

    rating_counts = (
        df["rating"]
        .value_counts()
        .sort_index()
    )

    category_counts = (
        df["category"]
        .value_counts()
    )

    most_common_category = (
        category_counts.index[0]
        if not category_counts.empty
        else "sin datos"
    )

    rating_lines = []

    for rating, count in rating_counts.items():
        rating_lines.append(
            f"{int(rating)} estrellas: {count}"
        )

    ratings_text = "\n".join(
        rating_lines
    )

    return (
        "resumen - shelfsift\n"
        "===================\n"
        f"paginas recorridas: {pages_scraped}\n"
        f"libros encontrados: {len(df)}\n"
        f"precio promedio: £{df['price_gbp'].mean():.2f}\n"
        f"precio mediano: £{df['price_gbp'].median():.2f}\n"
        f"mas barato: {cheapest['title']} (£{cheapest['price_gbp']:.2f})\n"
        f"mas caro: {most_expensive['title']} (£{most_expensive['price_gbp']:.2f})\n"
        f"categoria mas repetida: {most_common_category}\n"
        "\n"
        "ratings encontrados:\n"
        f"{ratings_text}\n"
    )


def save_results(books, pages_scraped):
    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    df = pd.DataFrame(
        books
    )

    #lo ordeno primero por categoria y despues por precio
    #esta parte la puedo cambiar si despues quiero otro criterio
    df = df.sort_values(
        by=[
            "category",
            "price_gbp"
        ],
        ascending=[
            True,
            False
        ],
        na_position="last"
    )

    df.to_csv(
        OUTPUT_DIR / "books.csv",
        index=False,
        encoding="utf-8-sig"
    )

    summary = build_summary(
        df,
        pages_scraped
    )

    (
        OUTPUT_DIR / "summary.txt"
    ).write_text(
        summary,
        encoding="utf-8"
    )

    return df


def main():
    print("empezando shelfsift...")
    print()

    books, pages_scraped = (
        scrape_catalog()
    )

    if not books:
        print(
            "no encontre datos, asi que no genere archivos"
        )
        return

    df = save_results(
        books,
        pages_scraped
    )

    print()
    print(
        "listo, termine de recorrer lo que tenia configurado"
    )

    print(
        f"encontre {len(df)} libros"
    )

    print(
        "guarde books.csv y summary.txt dentro de output"
    )


if __name__ == "__main__":
    main()