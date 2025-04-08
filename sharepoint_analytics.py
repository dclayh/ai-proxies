import os
from datetime import datetime, timedelta
import pandas as pd
from azure.identity import InteractiveBrowserCredential
from msgraph import GraphServiceClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_graph_client():
    """Initialize and return a Graph client using interactive browser authentication."""
    credential = InteractiveBrowserCredential()
    return GraphServiceClient(credentials=credential)

def get_sites(graph_client):
    """Get all SharePoint sites the user has access to."""
    sites = []
    response = graph_client.get('/sites?search=*')

    while response:
        data = response.json()
        sites.extend(data.get('value', []))

        # Check if there are more pages
        if '@odata.nextLink' in data:
            response = graph_client.get(data['@odata.nextLink'])
        else:
            break

    return sites

def get_pages_for_site(graph_client, site_id):
    """Get all pages for a specific site."""
    pages = []
    response = graph_client.get(f'/sites/{site_id}/pages')

    while response:
        data = response.json()
        pages.extend(data.get('value', []))

        if '@odata.nextLink' in data:
            response = graph_client.get(data['@odata.nextLink'])
        else:
            break

    return pages

def get_page_analytics(graph_client, site_id, page_id):
    """Get analytics for a specific page for the last year."""
    # Get analytics for the last year
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    response = graph_client.get(
        f'/sites/{site_id}/pages/{page_id}/analytics',
        params={
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d')
        }
    )

    data = response.json()
    return data.get('pageViews', 0)

def main():
    # Initialize Graph client
    graph_client = get_graph_client()

    # Get all sites
    print("Fetching SharePoint sites...")
    sites = get_sites(graph_client)

    # Prepare data for DataFrame
    data = []

    # Process each site
    for site in sites:
        site_id = site['id']
        site_name = site['displayName']
        print(f"Processing site: {site_name}")

        # Get pages for the site
        pages = get_pages_for_site(graph_client, site_id)

        # Process each page
        for page in pages:
            page_id = page['id']
            page_name = page['name']
            page_url = page['webUrl']

            # Get page analytics
            page_views = get_page_analytics(graph_client, site_id, page_id)

            data.append({
                'Site Name': site_name,
                'Page Name': page_name,
                'URL': page_url,
                'Page Views (1 year)': page_views
            })
            print(data[-1])

    # Create DataFrame and save to CSV
    df = pd.DataFrame(data)
    output_file = 'sharepoint_analytics.csv'
    df.to_csv(output_file, index=False)
    print(f"\nAnalytics data has been saved to {output_file}")

if __name__ == '__main__':
    main()