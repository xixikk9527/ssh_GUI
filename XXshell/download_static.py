import urllib.request
import os
import ssl

# Ignore SSL errors for download script
ssl._create_default_https_context = ssl._create_unverified_context

files = {
    "xterm.js": "https://unpkg.com/xterm@5.3.0/lib/xterm.js",
    "xterm.css": "https://unpkg.com/xterm@5.3.0/css/xterm.css",
    "addon-fit.js": "https://unpkg.com/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"
}

os.makedirs("static", exist_ok=True)

for name, url in files.items():
    print(f"Downloading {name}...")
    try:
        # User-Agent is sometimes required
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(f"static/{name}", 'wb') as out_file:
            out_file.write(response.read())
        print("Success")
    except Exception as e:
        print(f"Failed to download {name}: {e}")
