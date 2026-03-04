import urllib.request
import re

url = "https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-categorization"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8')
    
    # Strip HTML tags
    text = re.sub('<[^<]+>', ' ', html)
    text = re.sub('\s+', ' ', text)
    
    print("Document fetched. Searching for Utility vs Marketing guidelines...")
    
    # Find sections containing Utility and Marketing
    matches = re.finditer(r'(.{0,100})(Utility|Marketing|Categorization)(.{0,500})', text, re.IGNORECASE)
    
    for i, match in enumerate(matches):
        if i > 15: break
        print(f"\n--- Match {i+1} ---")
        print(match.group(0))
        
except Exception as e:
    print(f"Error: {e}")
