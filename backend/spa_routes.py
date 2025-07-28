# Add this route to serve React app for production
import os
from flask import send_from_directory

# Serve React App (add this near the end of app.py, before the main section)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    # If it's an API request, let Flask handle it normally
    if path.startswith('api/') or path in ['scan', 'clear-scan', 'clear-all-data']:
        # Let Flask's normal routing handle these
        pass
    else:
        # For all other routes, serve the React app
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

# Note: This should replace the existing @app.route('/') def index(): route
