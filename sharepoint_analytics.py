import os
from datetime import datetime, timedelta
import pandas as pd
from azure.identity import InteractiveBrowserCredential
from msgraph import GraphServiceClient
from msgraph.generated.sites.sites_request_builder import SitesRequestBuilder
from msgraph.generated.models.site import Site
from msgraph.generated.models.page import Page
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
    
    # Use the proper method to get sites
    sites_request = graph_client.sites.get()
    sites_response = graph_client.execute(sites_request)
    
    # Process the response
    if sites_response and sites_response.value:
        sites.extend(sites_response.value)
        
        # Handle pagination if needed
        while sites_response.odata_next_link:
            next_request = graph_client.sites.with_url(sites_response.odata_next_link).get()
            sites_response = graph_client.execute(next_request)
            if sites_response and sites_response.value:
                sites.extend(sites_response.value)
    
    return sites

def get_pages_for_site(graph_client, site_id):
    """Get all pages for a specific site."""
    pages = []
    
    # Use the proper method to get pages for a site
    pages_request = graph_client.sites.by_site_id(site_id).pages.get()
    pages_response = graph_client.execute(pages_request)
    
    # Process the response
    if pages_response and pages_response.value:
        pages.extend(pages_response.value)
        
        # Handle pagination if needed
        while pages_response.odata_next_link:
            next_request = graph_client.sites.by_site_id(site_id).pages.with_url(pages_response.odata_next_link).get()
            pages_response = graph_client.execute(next_request)
            if pages_response and pages_response.value:
                pages.extend(pages_response.value)
    
    return pages

def get_page_analytics(graph_client, site_id, page_id):
    """Get analytics for a specific page for the last year."""
    # Get analytics for the last year
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    # Format dates for the API
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Use the proper method to get page analytics
    analytics_request = graph_client.sites.by_site_id(site_id).pages.by_page_id(page_id).analytics.get()
    analytics_response = graph_client.execute(analytics_request)
    
    # Extract page views from the response
    if analytics_response:
        return analytics_response.page_views or 0
    
    return 0

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
        site_id = site.id
        site_name = site.display_name
        print(f"Processing site: {site_name}")
        
        # Get pages for the site
        pages = get_pages_for_site(graph_client, site_id)
        
        # Process each page
        for page in pages:
            page_id = page.id
            page_name = page.name
            page_url = page.web_url
            
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