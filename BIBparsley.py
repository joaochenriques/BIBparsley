from collections import OrderedDict
import re
from habanero import Crossref


def get_doi(article_title):
    cr = Crossref( timeout=100 ) 
    result = cr.works( 
        query_title=article_title, limit=1
    )  # Fetch the most relevant result

    if result["message"]["items"]:
        return result["message"]["items"][0].get("DOI", "DOI not found")
    return "DOI not found"


def get_exact_doi(article_title):
    cr = Crossref(timeout=100)
    results = cr.works(
        query_title=article_title, limit=10
    )  # Fetch multiple results for validation

    for item in results.get("message", {}).get("items", []):
        if "title" in item:
            found_title = (
                item["title"][0].strip().lower()
            )  # Normalize title for comparison
            if found_title == article_title.strip().lower():  # Exact match check
                return item.get("DOI")  # Return DOI if exact match found

    return None  # Return None if no exact match is found


def is_all_uppercase(s):
    """
    Checks if the string contains only uppercase alphabetic characters.
    Ignores spaces and non-alphabetical characters.
    """
    return s.isalpha() and s.isupper()


def abbreviate_name(name):
    """
    Abbreviates a name by keeping the first letter of each word followed by a period.
    If the name is in uppercase, it splits the letters and appends a period.
    """
    name_parts = (
        name.replace( ".", ". " ).split()
    )  # Split the name into parts (in case there are multiple words)

    joinname = ""
    # If name is uppercase, format as split letters with periods
    for part in name_parts:
        if is_all_uppercase(part):
            letters = [letter + "." for letter in part]
            joinname = " ".join(filter(None, [joinname, *letters]))
        else:
            if part.isalpha():
                part = part[0].upper() + "."
            joinname = " ".join(filter(None, [joinname, part]))

    return joinname


def split_authors(author_str):
    """
    Splits the author field into a list of names.
    Handles both "First Last" and "Last, First" formats.
    Converts all-uppercase names to initials with spaces after periods.
    """
    authors = re.split(r"\s+and\s+", author_str)  # Split authors by ' and '

    try:
        formatted_authors = []
        for author in authors:
            author = author.strip()

            if "," in author:  # "Last, First" format
                last, first = map(str.strip, author.split(",", 1))
                formatted_authors.append(f"{abbreviate_name(first)} {last}")
            elif " " in author:
                first, last = author.rsplit(" ", 1)
                formatted_authors.append(f"{abbreviate_name(first)} {last}")
            else:
                formatted_authors.append(f"{author}")

    except:
        print(f"ERROR on author: {author_str}")
        exit(1)

    return formatted_authors


def read_bibtex_entries(file_path):
    """Reads a BibTeX file and extracts entries into an OrderedDict."""
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    entries = OrderedDict()
    index = 0
    length = len(content)

    while index < length:
        if content[index] == "@":  # Found a new entry
            entry_start = index
            brace_count = 0
            while index < length:
                if content[index] == "{":
                    brace_count += 1
                elif content[index] == "}":
                    brace_count -= 1
                    if brace_count == 0:  # End of entry
                        entry_text = content[entry_start : index + 1]
                        process_bib_entry(entry_text, entries)
                        break
                index += 1
        index += 1

    return entries


def process_bib_entry(entry_text, entries):
    """Processes a single BibTeX entry and stores it in OrderedDict."""
    lines = entry_text.split("\n")
    header = lines[0].strip()

    if "{" not in header:
        return  # Invalid entry

    entry_type, entry_id = header.split("{", 1)
    entry_type = entry_type[1:].strip().lower()  # Remove '@'
    entry_id = entry_id.strip().rstrip(",")

    fields = OrderedDict()
    field_text = "\n".join(lines[1:]).strip()

    # Parse fields with proper brace handling
    field_dict = parse_fields(field_text)
    fields.update(field_dict)

    if entry_id in entries:
        print(f"Duplicate entry: {entry_id}")
        exit(1)

    entries[entry_id] = {"type": entry_type, "fields": fields}


def parse_fields(field_text):
    """Parses BibTeX fields, handling nested braces properly."""
    fields = OrderedDict()
    index = 0
    length = len(field_text)

    while index < length:
        # Find the next '=' (key-value separator)
        if field_text[index] == "=":
            key_start = field_text.rfind("\n", 0, index) + 1  # Start of the key
            key = field_text[key_start:index].strip().lower()

            # Move to value
            index += 1
            while index < length and field_text[index] in " \t\n":
                index += 1  # Skip whitespace

            value, index = extract_value(field_text, index)

            value = value.rstrip(",")

            if key in ["author", "editor"]:
                value = split_authors(value)
                value = " and ".join(value)
            elif key == "pages":
                n = value.count("-")
                if n > 1:
                    value = value.replace("-" * n, "-")

            fields[key.lower()] = value

        index += 1

    return fields


def extract_value(text, start_index):
    """Extracts a field value while properly handling nested braces and quotes."""
    index = start_index
    length = len(text)
    brace_level = 0
    in_quotes = False
    value = ""

    while index < length:
        char = text[index]

        if char == "{":
            brace_level += 1
            value += char
        elif char == "}":
            brace_level -= 1
            value += char
            if brace_level == 0:  # End of field
                return (
                    value[1:-1]
                    if value.startswith("{") and value.endswith("}")
                    else value,
                    index,
                )
        elif char == '"':
            in_quotes = not in_quotes
            value += char
        elif char == "," and brace_level == 0 and not in_quotes:
            return value, index  # End of value
        else:
            value += char

        index += 1

    return value, index


def entry2str(key, entry):
    str = f"@{entry['type']}{{{key},"
    for field, value in entry["fields"].items():
        str = "\n".join([str, f"\t{field} = {{{value}}},"])
    str = "\n".join([str, "}\n\n"])
    return str


def update_DOI(entry):

    bibtype = entry["type"]
    bibfields = entry["fields"]

    if not "doi" in entry:
        article_name = bibfields["title"]

        if bibtype == "article":
            doi = get_doi(article_name)
            if doi is not None:
                bibfields["doi"] = doi
        else:
            doi = get_exact_doi(article_name)
            if doi is not None:
                bibfields["doi"] = doi


def remove_dummy_fields(entry):

    bibtype = entry["type"]
    bibfields = entry["fields"]

    # remove generic unused fields
    for field in ["timestamp", "abstract", "keywords", "owner"]:
        if field in bibfields:
            del bibfields[field]

    # remove unwanted fields in articles
    if bibtype == "article":
        for field in ["issn", "url"]:
            if field in bibfields:
                del bibfields[field]
