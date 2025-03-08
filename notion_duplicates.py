import os
import time
from datetime import datetime
import httpx
from dotenv import load_dotenv
from notion_client import Client
from notion_client import errors as notion_errors

# Load environment variables
load_dotenv()

# Initialize Notion client
notion = Client(auth=os.getenv("NOTION_TOKEN"))

# Database ID from environment variables
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


def get_all_database_entries():
    """
    Fetch all pages from the Notion database.
    """
    results = []

    # Start with an empty cursor
    cursor = None

    while True:
        # Query the database, 100 items at a time
        if cursor:
            response = notion.databases.query(database_id=DATABASE_ID, page_size=100, start_cursor=cursor)
        else:
            try:
                response = notion.databases.query(database_id=DATABASE_ID, page_size=100)
            except notion_errors.APIResponseError:
                print("Error: HTTP status error. Check your database ID.")
                exit(1)

        # Add the results to our list
        results.extend(response["results"])

        # If there are no more results, break the loop
        if not response["has_more"]:
            break

        # Update the cursor for the next request
        cursor = response["next_cursor"]

        # To avoid rate limits
        time.sleep(0.3)

    return results


def get_url_from_page(page):
    """
    Extract the URL property from a page.
    """
    # Get the URL property
    # This assumes the URL property is named "URL" - adjust as needed
    properties = page.get("properties", {})
    url_property = properties.get("URL", {})

    # The structure of the URL property depends on its type in Notion
    # This handles URL-type properties
    if url_property.get("type") == "url":
        return url_property.get("url", "")

    # Also handle rich_text or title properties that might contain URLs
    elif url_property.get("type") in ["rich_text", "title"]:
        text_parts = url_property.get(url_property.get("type"), [])
        if text_parts:
            return "".join([part.get("plain_text", "") for part in text_parts])

    # Return empty string if URL not found
    return ""


def get_creation_time(page):
    """
    Extract the creation time from a page.
    """
    # Get the created_time property
    created_time = page.get("created_time", "")

    # Parse the created_time string into a datetime object
    if created_time:
        return datetime.fromisoformat(created_time.replace("Z", "+00:00"))

    # Return a very old date if created_time is not available
    return datetime.min


def find_and_remove_duplicates():
    """
    Find duplicates based on URL and remove them, keeping only the most recent one.
    """
    print("Fetching database entries...")
    pages = get_all_database_entries()

    print(f"Found {len(pages)} total entries.")

    # Group pages by URL
    url_groups = {}
    for page in pages:
        url = get_url_from_page(page)

        # Skip empty URLs
        if not url:
            continue

        if url in url_groups:
            url_groups[url].append(page)
        else:
            url_groups[url] = [page]

    # Find duplicates and keep only the most recent one
    pages_to_delete = []

    for url, url_pages in url_groups.items():
        if len(url_pages) > 1:
            # Sort by creation time, most recent first
            sorted_pages = sorted(url_pages, key=get_creation_time, reverse=True)

            # Keep the most recent one, mark others for deletion
            pages_to_delete.extend(sorted_pages[1:])

            print(f"Found {len(sorted_pages) - 1} duplicates for URL: {url}")

    # Delete the duplicates
    print(f"Deleting {len(pages_to_delete)} duplicate entries...")

    for page in pages_to_delete:
        try:
            notion.pages.update(page_id=page["id"], archived=True)
            print(f"Deleted page with ID: {page['id']}")
            # To avoid rate limits
            time.sleep(0.3)
        except Exception as e:
            print(f"Error deleting page {page['id']}: {e}")

    print("Duplicate removal complete.")


if __name__ == "__main__":
    # Check if required environment variables are set
    if not os.getenv("NOTION_TOKEN"):
        print("Error: NOTION_TOKEN environment variable is not set.")
        exit(1)

    if not os.getenv("NOTION_DATABASE_ID"):
        print("Error: NOTION_DATABASE_ID environment variable is not set.")
        exit(1)

    find_and_remove_duplicates()
