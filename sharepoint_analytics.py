import os
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from azure.identity import InteractiveBrowserCredential
from msgraph import GraphServiceClient
from dotenv import load_dotenv
from msgraph.generated.sites.sites_request_builder import SitesRequestBuilder
from msgraph.generated.models.site import Site
from kiota_abstractions.base_request_configuration import RequestConfiguration

# Load environment variables
load_dotenv()

def get_graph_client():
    """Initialize and return a Graph client using interactive browser authentication."""
    credential = InteractiveBrowserCredential()
    return GraphServiceClient(credentials=credential)

async def get_sites(graph_client):
    """Get all SharePoint sites the user has access to."""
    sites = []

    try:
        print("Trying to get all sites using a query...")
        try:
            # Use a query to get all sites with the correct parameter name
            # Create request configuration with search parameter
            request_config = RequestConfiguration(query_parameters=SitesRequestBuilder.SitesRequestBuilderGetQueryParameters(
                search="e"
            ))

            # Get sites with the request configuration
            sites_response = await graph_client.sites.get(request_configuration=request_config)

            # Process the response
            if sites_response and sites_response.value:
                print(f"Found {len(sites_response.value)} sites")
                for site in sites_response.value:
                    if not any(s.id == site.id for s in sites):
                        sites.append(site)
                        print(f"Site: {site.display_name} (ID: {site.id})")

                # Handle pagination if needed
                while sites_response.odata_next_link:
                    print("Fetching next page of sites...")
                    next_request = graph_client.sites.with_url(sites_response.odata_next_link)
                    sites_response = await next_request.get()
                    if sites_response and sites_response.value:
                        for site in sites_response.value:
                            if not any(s.id == site.id for s in sites):
                                sites.append(site)
                                print(f"Site: {site.display_name} (ID: {site.id})")
            else:
                print("No sites found in the response")
        except Exception as e:
            print(f"Error getting all sites: {e}")
            print("This might indicate permission issues. Required permissions: Sites.Read.All")


    except Exception as e:
        print(f"Error in get_sites: {e}")

    print(f"Total sites found: {len(sites)}")
    return sites

async def get_pages_for_site(graph_client, site_id):
    """Get all pages for a specific site."""
    pages = []

    try:
        print(f"Getting pages for site ID: {site_id}")

        # Try to get pages using the site ID
        pages_response = await graph_client.sites.by_site_id(site_id).pages.get()

        # Process the response
        if pages_response and pages_response.value:
            print(f"Found {len(pages_response.value)} pages")
            pages.extend(pages_response.value)

            # Handle pagination if needed
            while pages_response.odata_next_link:
                print("Fetching next page of pages...")
                next_request = graph_client.sites.by_site_id(site_id).pages.with_url(pages_response.odata_next_link)
                pages_response = await next_request.get()
                if pages_response and pages_response.value:
                    pages.extend(pages_response.value)
                    print(f"Added {len(pages_response.value)} more pages")
        else:
            print("No pages found in the response")

        # If no pages found, try to get lists and then items
        if not pages:
            print("Trying to get lists and items instead...")
            lists_response = await graph_client.sites.by_site_id(site_id).lists.get()

            if lists_response and lists_response.value:
                print(f"Found {len(lists_response.value)} lists")

                for list_item in lists_response.value:
                    print(f"Getting items from list: {list_item.display_name}")
                    try:
                        items_response = await graph_client.sites.by_site_id(site_id).lists.by_list_id(list_item.id).items.get()

                        if items_response and items_response.value:
                            print(f"Found {len(items_response.value)} items in list {list_item.display_name}")

                            # Create page-like objects from items
                            for item in items_response.value:
                                if hasattr(item, 'web_url') and item.web_url:
                                    pages.append(item)
                    except Exception as e:
                        print(f"Error getting items from list {list_item.display_name}: {e}")
            else:
                print("No lists found")
    except Exception as e:
        print(f"Error getting pages for site {site_id}: {e}")

    print(f"Total pages found for site {site_id}: {len(pages)}")
    return pages

async def get_page_analytics(graph_client, site_id, page_id):
    """Get analytics for a specific page for the last year."""
    # Get analytics for the last year
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    # Format dates for the API
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    try:
        print(f"Getting analytics for page ID: {page_id}")
        # Use the proper method to get page analytics
        analytics_response = await graph_client.sites.by_site_id(site_id).pages.by_page_id(page_id).analytics.get()

        # Extract page views from the response
        if analytics_response:
            page_views = analytics_response.page_views or 0
            print(f"Page views: {page_views}")
            return page_views
        else:
            print("No analytics data found")
    except Exception as e:
        print(f"Error getting analytics for page {page_id}: {e}")

    return 0

async def main():
    # Initialize Graph client
    graph_client = get_graph_client()

    # Get all sites
    print("Fetching SharePoint sites...")
    sites = await get_sites(graph_client)

    if not sites:
        print("No sites found. Exiting.")
        return

    # Prepare data for DataFrame
    data = []

    # Process each site
    for site in sites:
        site_id = site.id
        site_name = site.display_name
        print(f"Processing site: {site_name}")

        # Get pages for the site
        pages = await get_pages_for_site(graph_client, site_id)

        if not pages:
            print(f"No pages found for site {site_name}. Skipping.")
            continue

        # Process each page
        for page in pages:
            try:
                page_id = page.id
                page_name = getattr(page, 'name', 'Unknown')
                page_url = getattr(page, 'web_url', 'Unknown')

                # Get page analytics
                page_views = await get_page_analytics(graph_client, site_id, page_id)

                data.append({
                    'Site Name': site_name,
                    'Page Name': page_name,
                    'URL': page_url,
                    'Page Views (1 year)': page_views
                })
                print(data[-1])
            except Exception as e:
                print(f"Error processing page: {e}")

    if not data:
        print("No data collected. Exiting.")
        return

    # Create DataFrame and save to CSV
    df = pd.DataFrame(data)
    output_file = 'sharepoint_analytics.csv'
    df.to_csv(output_file, index=False)
    print(f"\nAnalytics data has been saved to {output_file}")

if __name__ == '__main__':
    asyncio.run(main())