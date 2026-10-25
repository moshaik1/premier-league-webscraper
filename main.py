# StringIO wraps a string so pandas can read it as if it were a file
from io import StringIO
# re is Python's regular expression module, used to find and remove text patterns
import re

# BeautifulSoup turns raw HTML into a tree of tags we can search
from bs4 import BeautifulSoup
# pandas handles tables of data (DataFrames) and saving them to CSV
import pandas as pd
# requests downloads web pages
import requests

# The season to scrape. Note the en dash (–), not a hyphen (-), to match Wikipedia's page names
SEASON = "2026–27"
# Build the page address by putting the season into the URL with an f-string
URL = f"https://en.wikipedia.org/wiki/{SEASON}_Premier_League"

# Wikipedia asks scrapers to identify themselves, so we send a User-Agent header with each request
HEADERS = {"User-Agent": "premier-league-webscraper/0.1 (personal learning project)"}


def get_headers(table):
    """Return the text of each header cell in a table's first row."""
    # The first <tr> (table row) in the table is the header row
    first_row = table.find("tr")
    # For every <th> (header cell) in that row, get its visible text with surrounding spaces removed
    return [th.get_text(strip=True) for th in first_row.find_all("th")]


def get_full_headers(table):
    """Like get_headers, but use the full name from <abbr title="..."> when there is one."""
    # Grab the header row, the same as in get_headers
    first_row = table.find("tr")
    # Start an empty list that will hold one column name per header cell
    full_names = []
    # Go through each header cell one at a time
    for th in first_row.find_all("th"):
        # Look inside this cell for an <abbr> tag, e.g. <abbr title="Played">Pld</abbr>
        abbr = th.find("abbr")
        # Only use the abbr if it exists AND has a title attribute
        if abbr and abbr.get("title"):
            # Add the full name from the title attribute, e.g. "Played"
            full_names.append(abbr.get("title"))
        # Otherwise this cell has no abbreviation (e.g. "Team")
        else:
            # so add its visible text instead, which keeps every column in the right place
            full_names.append(th.get_text(strip=True))
    # Hand the finished list of names back to whoever called the function
    return full_names


def find_table_with_headers(soup, required):
    """Find the first wikitable whose header row contains every name in `required`."""
    # Loop over every table on the page that has the class "wikitable"
    for table in soup.find_all("table", class_="wikitable"):
        # Get this table's short column names, e.g. ['Pos', 'Team', 'Pld', ...]
        headers = get_headers(table)
        # all() is True only if every required name appears in this table's headers
        if all(name in headers for name in required):
            # Found it, so return this table and stop looking
            return table
    # The loop finished without a match, so tell the caller nothing was found
    return None


def remove_citations(text):
    """Turn 'Goals[107][108]' into 'Goals' by stripping the [number] footnotes."""
    # \[\d+\] matches "[", one or more digits, then "]". Replace every match with "" and trim spaces
    return re.sub(r"\[\d+\]", "", text).strip()


# --- 1. Download and parse the season page ---
# Download the Wikipedia page, sending our User-Agent header along with the request
response = requests.get(URL, headers=HEADERS)
# If the request failed (e.g. 404 or 403), stop here with a clear error message
response.raise_for_status()
# Parse the downloaded HTML text into a searchable BeautifulSoup tree
soup = BeautifulSoup(response.text, "html.parser")
# Print the page's <title> as a quick check that we got the page we expected
print(f"Loaded: {soup.title.get_text()}")

# --- 2. League table, parsed by hand with BeautifulSoup ---
# Find the standings table by its column names instead of its position on the page
standings_table = find_table_with_headers(soup, ["Pos", "Team", "Pts"])
# If no table matched, there's nothing to scrape
if standings_table is None:
    # so exit the script with a message explaining why
    raise SystemExit("Couldn't find the league table - the page layout may have changed")

# Get the full column names and keep the first 10 (Position .. Points), dropping 'Qualification or relegation'
columns = get_full_headers(standings_table)[:10]
# Empty list that will hold one dictionary per team
standings = []
# Loop through every row in the table. [1:] skips row 0, the header row
for row in standings_table.find_all("tr")[1:]:
    # Get every cell in the row. The team name is a <th>, so we search for both <th> and <td>
    cells = row.find_all(["th", "td"])
    # Take the text of the first 10 cells so every row lines up with the 10 column names
    values = [cell.get_text(strip=True) for cell in cells[:10]]
    # zip pairs each name with its value, and dict turns the pairs into {'Position': '1', 'Team': 'Arsenal', ...}
    team = dict(zip(columns, values))

    # cells[1] is the team cell. Find the <a> link inside it (points to the club's Wikipedia page)
    link = cells[1].find("a")
    # Save the link's URL, or None if the cell has no link
    team["Link"] = link.get("href") if link else None
    # Add this team's dictionary to the list
    standings.append(team)

# Turn the list of dictionaries into a DataFrame. The dictionary keys become the column names
standings_df = pd.DataFrame(standings)
# Show the table in the console
print(standings_df)
# Save to CSV. index=False skips pandas' row numbers, utf-8-sig makes Excel show accents correctly
standings_df.to_csv("standings.csv", index=False, encoding="utf-8-sig")

# --- 3. Top scorers, parsed with pandas.read_html ---
# Find the top scorers table by its column names
scorers_table = find_table_with_headers(soup, ["Rank", "Player", "Club"])
# Only continue if the table was found
if scorers_table is not None:
    # Convert the table tag to an HTML string, wrap it for pandas, and parse it. read_html returns a list, so take [0]
    scorers_df = pd.read_html(StringIO(str(scorers_table)))[0]
    # Clean every column name, ex "Goals[107][108]" becomes "Goals"
    scorers_df.columns = [remove_citations(col) for col in scorers_df.columns]
    # Show the first 10 rows in the console
    print(scorers_df.head(10))
    # Save to CSV, using the same settings as the standings file
    scorers_df.to_csv("top_scorers.csv", index=False, encoding="utf-8-sig")
# If the table wasn't found
else:
    # tell the user instead of crashing
    print("No top scorers table found")
