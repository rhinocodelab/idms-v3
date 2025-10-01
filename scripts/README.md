# IDMS Database Scripts

This folder contains utility scripts for managing the IDMS database.

## Available Scripts

### 1. clean_database.py

Cleans the IDMS database by removing all data except the admin user.

**Purpose:**
- Removes all documents, logs, and user data
- Preserves the admin user account
- Useful for testing, demos, or starting fresh

**Usage:**

```bash
# From the project root directory
python scripts/clean_database.py
```

**What it does:**
- ✅ Preserves admin user (username: 'admin')
- ❌ Deletes all non-admin users
- ❌ Deletes all AI document classifications
- ❌ Deletes all GhostLayer documents
- ❌ Deletes all processing logs
- ❌ Deletes all system metrics
- ❌ Deletes all error logs
- ❌ Deletes all user sessions
- ❌ Deletes all configuration settings

**Safety Features:**
- Requires explicit confirmation before proceeding
- Shows detailed summary of what will be deleted
- Displays total records deleted after completion
- Optimizes database after cleanup (VACUUM)

**Example Output:**

```
==============================================================
⚠️  DATABASE CLEANUP WARNING ⚠️
==============================================================

This script will DELETE all data from the database except:
  ✓ Admin user (username: 'admin')

The following data will be PERMANENTLY DELETED:
  ✗ All non-admin users
  ✗ All AI document classifications
  ✗ All GhostLayer documents
  ✗ All processing logs
  ...

Are you sure you want to proceed? (yes/no): yes

🧹 Starting database cleanup...
  ✓ Cleared Processing logs: 150 records deleted
  ✓ Cleared AI document classifications: 45 records deleted
  ...

✅ DATABASE CLEANUP COMPLETED SUCCESSFULLY
```

**Admin Credentials:**
After cleanup, you can log in with:
- **Username:** admin
- **Password:** admin123
- **Email:** admin@idmsdemo.com

## Future Scripts

This folder can be expanded with additional utility scripts such as:
- Database backup scripts
- Data migration scripts
- User management scripts
- Analytics export scripts

