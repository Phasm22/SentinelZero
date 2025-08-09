"""
Settings-related API routes
"""
import json
import os
from flask import Blueprint, request, jsonify

def create_settings_blueprint(db):
    """Create and configure settings routes blueprint"""
    bp = Blueprint('settings', __name__)
    
    def snake_to_camel(snake_str):
        """Convert snake_case to camelCase"""
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])
    
    def camel_to_snake(camel_str):
        """Convert camelCase to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def normalize_settings_keys(settings_dict, to_camel=True):
        """Normalize all keys in a settings dictionary"""
        normalized = {}
        for key, value in settings_dict.items():
            if to_camel:
                new_key = snake_to_camel(key)
            else:
                new_key = camel_to_snake(key)
            normalized[new_key] = value
        return normalized
    
    @bp.route('/settings', methods=['GET'])
    def get_settings():
        """Get all application settings"""
        settings = {
            'networkSettings': {},
            'securitySettings': {},
            'notificationSettings': {},
            'scheduledScansSettings': {}
        }
        
        setting_files = {
            'networkSettings': 'network_settings.json',
            'securitySettings': 'security_settings.json',
            'notificationSettings': 'notification_settings.json',
            'scheduledScansSettings': 'scheduled_scans_settings.json'
        }
        
        for setting_type, filename in setting_files.items():
            try:
                if os.path.exists(filename):
                    with open(filename, 'r') as f:
                        file_content = json.load(f)
                        # Normalize keys to camelCase for frontend consistency
                        settings[setting_type] = normalize_settings_keys(file_content, to_camel=True)
                else:
                    print(f'[DEBUG] Settings file {filename} not found, using defaults')
            except Exception as e:
                print(f'[DEBUG] Error loading {filename}: {e}')

        # Derive Pushover configuration status from environment variables (runtime truth over file)
        try:
            pushover_token = os.environ.get('PUSHOVER_API_TOKEN')
            pushover_user = os.environ.get('PUSHOVER_USER_KEY')
            if pushover_token and pushover_user:
                # Ensure notificationSettings dict exists
                notif = settings.get('notificationSettings', {})
                notif['pushoverConfigured'] = True
                # If not explicitly enabled in file, do not auto-enable; only mark configured state
                settings['notificationSettings'] = notif
            else:
                # If missing credentials and key absent, ensure false so UI reflects reality
                notif = settings.get('notificationSettings', {})
                if 'pushoverConfigured' not in notif:
                    notif['pushoverConfigured'] = False
                settings['notificationSettings'] = notif
        except Exception as e:
            print(f'[DEBUG] Error deriving pushover configuration: {e}')
        
        return jsonify(settings)
    
    @bp.route('/settings', methods=['POST'])
    def update_settings():
        """Update application settings"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'No data provided'}), 400
            
            setting_files = {
                'networkSettings': 'network_settings.json',
                'securitySettings': 'security_settings.json', 
                'notificationSettings': 'notification_settings.json',
                'scheduledScansSettings': 'scheduled_scans_settings.json'
            }
            
            for setting_type, filename in setting_files.items():
                if setting_type in data:
                    settings_data = data[setting_type]
                    # Convert camelCase keys to snake_case for backend storage
                    normalized_data = normalize_settings_keys(settings_data, to_camel=False)
                    
                    try:
                        with open(filename, 'w') as f:
                            json.dump(normalized_data, f, indent=4)
                        print(f'[DEBUG] Successfully saved {filename}')
                    except Exception as e:
                        print(f'[DEBUG] Error saving {filename}: {e}')
                        return jsonify({
                            'status': 'error', 
                            'message': f'Error saving {setting_type}: {str(e)}'
                        }), 500
            
            return jsonify({'status': 'success', 'message': 'Settings updated successfully'})
            
        except Exception as e:
            print(f'[DEBUG] Error in update_settings: {e}')
            return jsonify({'status': 'error', 'message': f'Error updating settings: {str(e)}'}), 500
    
    return bp
