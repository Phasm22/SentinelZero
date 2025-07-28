#!/usr/bin/env python3
"""
Migration script to transition from monolithic app.py to modular structure
"""
import os
import shutil
import sys

def backup_original():
    """Create backup of original app.py"""
    if os.path.exists('app.py') and not os.path.exists('app_monolithic_backup.py'):
        shutil.copy2('app.py', 'app_monolithic_backup.py')
        print('✅ Created backup: app_monolithic_backup.py')
    else:
        print('ℹ️  Backup already exists or app.py not found')

def switch_to_modular():
    """Switch to modular application structure"""
    if os.path.exists('app_modular.py'):
        # Backup current app.py if it exists
        backup_original()
        
        # Replace app.py with modular version
        shutil.copy2('app_modular.py', 'app.py')
        print('✅ Switched to modular app.py')
        
        print('\n📋 Migration Steps Completed:')
        print('   1. ✅ Backed up original app.py → app_monolithic_backup.py')
        print('   2. ✅ Replaced app.py with modular version')
        print('   3. ✅ Modular structure ready in src/ directory')
        
        print('\n🔧 Manual Steps Required:')
        print('   1. Install dependencies: pip install -r requirements.txt')
        print('   2. Test the application: python app.py')
        print('   3. Verify all functionality works')
        print('   4. Update any deployment scripts to use new structure')
        
        print('\n📁 New Structure:')
        print('   backend/')
        print('   ├── app.py (modular entry point)')
        print('   ├── app_monolithic_backup.py (original backup)')
        print('   └── src/')
        print('       ├── models/ (database models)')
        print('       ├── routes/ (API endpoints)')
        print('       ├── services/ (business logic)')
        print('       ├── utils/ (helper functions)')
        print('       └── config/ (configuration)')
        
    else:
        print('❌ Error: app_modular.py not found')
        return False
    
    return True

def switch_back_to_monolithic():
    """Revert to original monolithic structure"""
    if os.path.exists('app_monolithic_backup.py'):
        shutil.copy2('app_monolithic_backup.py', 'app.py')
        print('✅ Reverted to monolithic app.py')
        print('ℹ️  Modular files remain in src/ for future use')
    else:
        print('❌ Error: No backup found (app_monolithic_backup.py)')

def main():
    """Main migration interface"""
    if len(sys.argv) < 2:
        print('SentinelZero Migration Tool')
        print('============================')
        print('Usage:')
        print('  python migrate.py modular    - Switch to modular structure')
        print('  python migrate.py monolithic - Revert to monolithic structure')
        print('  python migrate.py backup     - Just create backup of current app.py')
        return
    
    command = sys.argv[1].lower()
    
    if command == 'modular':
        print('🔄 Migrating to modular structure...')
        if switch_to_modular():
            print('\n🎉 Migration to modular structure completed!')
            print('💡 Run "python app.py" to test the new modular application')
        
    elif command == 'monolithic':
        print('🔄 Reverting to monolithic structure...')
        switch_back_to_monolithic()
        print('\n🎉 Reverted to monolithic structure!')
        
    elif command == 'backup':
        print('💾 Creating backup...')
        backup_original()
        
    else:
        print(f'❌ Unknown command: {command}')
        print('Valid commands: modular, monolithic, backup')

if __name__ == '__main__':
    main()
