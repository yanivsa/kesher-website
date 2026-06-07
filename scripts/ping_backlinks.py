import urllib.request
import urllib.parse
import sys
import xmlrpc.client

# List of XML-RPC Ping Servers to notify search engines about new content
PING_SERVERS = [
    "http://rpc.pingomatic.com/",
    "http://rpc.reader.skygrid.com",
    "http://blogsearch.google.com/ping/RPC2",
    "http://ping.feedburner.com",
    "http://api.my.yahoo.com/RPC2",
    "http://api.my.yahoo.com/rss/ping",
    "http://ping.feedburner.com",
    "http://rpc.weblogs.com/RPC2"
]

def ping_engines(title, url):
    print(f"Starting ping for: {title} ({url})")
    
    # 1. Google Direct Ping HTTP Request
    google_ping_url = f"https://www.google.com/ping?sitemap={urllib.parse.quote(url)}"
    try:
        req = urllib.request.Request(
            google_ping_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print("Successfully sent direct HTTP ping to Google.")
    except Exception as e:
        print(f"Failed to ping Google directly: {e}")

    # 2. XML-RPC Pings
    for server in PING_SERVERS:
        try:
            print(f"Pinging XML-RPC server: {server} ... ", end="")
            rpc_server = xmlrpc.client.ServerProxy(server)
            # Weblogs ping format: ping(site_name, site_url)
            result = rpc_server.weblogUpdates.ping(title, url)
            print("Response:", result)
        except Exception as e:
            print("Failed")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ping_backlinks.py <Title_of_Article> <URL_of_Backlink>")
        print("Example: python ping_backlinks.py 'יועצת זוגית מומלצת באשדוד' 'https://medium.com/@shira_saharoni/my-article-url'")
        sys.exit(1)
        
    title = sys.argv[1]
    url = sys.argv[2]
    ping_engines(title, url)
