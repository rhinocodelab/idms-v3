"""
IDMS Database Models and Schema
SQLite database for storing document processing information, user data, and system metrics
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)

class IDMSDatabase:
    def __init__(self, db_path: str = None):
        # Default to idms.db in the same directory as this file
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "idms.db")
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create all tables
        self.create_users_table(cursor)
        self.create_documents_table(cursor)
        self.create_processing_logs_table(cursor)
        self.create_document_categories_table(cursor)
        self.create_criticality_levels_table(cursor)
        self.create_filenet_uploads_table(cursor)
        self.create_system_metrics_table(cursor)
        self.create_user_sessions_table(cursor)
        self.create_error_logs_table(cursor)
        self.create_configuration_table(cursor)
        self.create_ghostlayer_documents_table(cursor)
        self.create_ai_document_classifications_table(cursor)
        self.create_user_ghostlayer_documents_table(cursor)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def migrate_database(self):
        """Migrate existing database to add new columns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if ghostlayer_documents table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ghostlayer_documents'")
            if cursor.fetchone():
                # Check if coordinates_json_path column exists
                cursor.execute("PRAGMA table_info(ghostlayer_documents)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'coordinates_json_path' not in columns:
                    cursor.execute("ALTER TABLE ghostlayer_documents ADD COLUMN coordinates_json_path TEXT")
                    logger.info("Added coordinates_json_path column to existing ghostlayer_documents table")
                else:
                    logger.info("coordinates_json_path column already exists in ghostlayer_documents table")
            
            # Check if users table exists and add module access columns
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(users)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'ai_classification_access' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN ai_classification_access BOOLEAN DEFAULT 1")
                    logger.info("Added ai_classification_access column to users table")
                else:
                    logger.info("ai_classification_access column already exists in users table")
                
                if 'ghostlayer_access' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN ghostlayer_access BOOLEAN DEFAULT 1")
                    logger.info("Added ghostlayer_access column to users table")
                else:
                    logger.info("ghostlayer_access column already exists in users table")
                
                # Add GhostLayer view permission columns
                if 'ghostlayer_view_original' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN ghostlayer_view_original BOOLEAN DEFAULT 1")
                    logger.info("Added ghostlayer_view_original column to users table")
                else:
                    logger.info("ghostlayer_view_original column already exists in users table")
                
                if 'ghostlayer_view_redacted' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN ghostlayer_view_redacted BOOLEAN DEFAULT 1")
                    logger.info("Added ghostlayer_view_redacted column to users table")
                else:
                    logger.info("ghostlayer_view_redacted column already exists in users table")
            
            conn.commit()
            logger.info("Database migration completed successfully")
            
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
        finally:
            conn.close()
    
    def create_users_table(self, cursor):
        """Users table - stores user information and roles"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL DEFAULT 'user', -- 'admin', 'manager', 'analyst', 'viewer'
                is_active BOOLEAN DEFAULT 1,
                is_mfa_enabled BOOLEAN DEFAULT 0,
                ai_classification_access BOOLEAN DEFAULT 1, -- Access to AI Document Classification
                ghostlayer_access BOOLEAN DEFAULT 1, -- Access to GhostLayer AI
                ghostlayer_view_original BOOLEAN DEFAULT 1, -- View original documents in GhostLayer
                ghostlayer_view_redacted BOOLEAN DEFAULT 1, -- View redacted documents in GhostLayer
                last_login DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER, -- ID of user who created this user
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        
        # Create default admin user if it doesn't exist
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            # Hash the default password 'admin123'
            import hashlib
            password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
            cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, email, role, created_by)
                VALUES ('admin', ?, 'System Administrator', 'admin@idmsdemo.com', 'admin', 1)
            """, (password_hash,))
            logger.info("Default admin user created")
        
        # Update existing admin user email to admin@idmsdemo.com
        cursor.execute("UPDATE users SET email = 'admin@idmsdemo.com' WHERE username = 'admin'")
        logger.info("Updated admin user email to admin@idmsdemo.com")
        
        # Add MFA columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_mfa_enabled BOOLEAN DEFAULT 0")
            logger.info("Added is_mfa_enabled column to users table")
        except sqlite3.OperationalError:
            # Column already exists, ignore the error
            pass
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN mfa_secret TEXT")
            logger.info("Added mfa_secret column to users table")
        except sqlite3.OperationalError:
            # Column already exists, ignore the error
            pass
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN mfa_setup_complete BOOLEAN DEFAULT 0")
            logger.info("Added mfa_setup_complete column to users table")
        except sqlite3.OperationalError:
            # Column already exists, ignore the error
            pass
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN has_changed_default_password BOOLEAN DEFAULT 0")
            logger.info("Added has_changed_default_password column to users table")
        except sqlite3.OperationalError:
            # Column already exists, ignore the error
            pass
    
    def create_documents_table(self, cursor):
        """Documents table - stores information about processed documents"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                mime_type TEXT,
                document_type TEXT NOT NULL,
                criticality_level TEXT NOT NULL,
                file_path TEXT,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processing_timestamp DATETIME,
                processing_duration REAL,
                ai_confidence_score REAL,
                tags TEXT, -- JSON array of tags
                summary TEXT,
                reasoning TEXT,
                is_archive BOOLEAN DEFAULT 0,
                parent_archive_id INTEGER,
                checksum TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_archive_id) REFERENCES documents(id)
            )
        """)
    
    def create_processing_logs_table(self, cursor):
        """Processing logs table - tracks all processing activities"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                processing_step TEXT NOT NULL,
                status TEXT NOT NULL, -- 'started', 'completed', 'failed'
                start_time DATETIME,
                end_time DATETIME,
                duration REAL,
                details TEXT, -- JSON object with step details
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        """)
    
    def create_document_categories_table(self, cursor):
        """Document categories table - tracks discovered document types"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL,
                description TEXT,
                first_discovered DATETIME DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 1,
                is_custom BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def create_criticality_levels_table(self, cursor):
        """Criticality levels table - manages security classification levels"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS criticality_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level_name TEXT UNIQUE NOT NULL,
                description TEXT,
                priority INTEGER NOT NULL, -- 1=Public, 5=Top Secret
                color_code TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def create_filenet_uploads_table(self, cursor):
        """FileNet uploads table - tracks FileNet upload attempts and results"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filenet_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                upload_type TEXT NOT NULL, -- 'classification', 'business'
                queue_id TEXT,
                upload_status TEXT NOT NULL, -- 'success', 'failed', 'pending'
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                completion_timestamp DATETIME,
                filenet_path TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        """)
    
    def create_system_metrics_table(self, cursor):
        """System metrics table - stores performance and usage statistics"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_unit TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                additional_data TEXT -- JSON object with extra metrics
            )
        """)
    
    def create_user_sessions_table(self, cursor):
        """User sessions table - tracks user interactions and sessions"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME,
                pages_visited TEXT, -- JSON array of visited pages
                actions_performed TEXT, -- JSON array of actions
                documents_uploaded INTEGER DEFAULT 0,
                total_file_size INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def create_error_logs_table(self, cursor):
        """Error logs table - tracks system errors and exceptions"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                context_data TEXT, -- JSON object with error context
                severity TEXT NOT NULL, -- 'low', 'medium', 'high', 'critical'
                resolved BOOLEAN DEFAULT 0,
                resolution_notes TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME
            )
        """)
    
    def create_configuration_table(self, cursor):
        """Configuration table - stores system configuration and settings"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                config_type TEXT NOT NULL, -- 'string', 'integer', 'boolean', 'json'
                description TEXT,
                is_sensitive BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def create_ghostlayer_documents_table(self, cursor):
        """GhostLayer AI documents table - stores documents processed by GhostLayer AI"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ghostlayer_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_name TEXT NOT NULL,
                document_type TEXT NOT NULL,
                document_format TEXT NOT NULL,
                document_size INTEGER NOT NULL,
                document_path TEXT NOT NULL,
                coordinates_json_path TEXT, -- Path to JSON file with text coordinates
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
                ai_analysis_result TEXT, -- JSON object with AI analysis results
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add coordinates_json_path column if it doesn't exist (for existing tables)
        try:
            # Check if column exists
            cursor.execute("PRAGMA table_info(ghostlayer_documents)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'coordinates_json_path' not in columns:
                cursor.execute("ALTER TABLE ghostlayer_documents ADD COLUMN coordinates_json_path TEXT")
                logger.info("Added coordinates_json_path column to ghostlayer_documents table")
            else:
                logger.info("coordinates_json_path column already exists")
        except Exception as e:
            logger.warning(f"Could not add coordinates_json_path column: {e}")

    def create_user_ghostlayer_documents_table(self, cursor):
        """User-specific GhostLayer documents table - stores user-uploaded GhostLayer documents"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_ghostlayer_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                uploaded_by TEXT NOT NULL,
                document_name TEXT NOT NULL,
                document_type TEXT NOT NULL,
                document_format TEXT NOT NULL,
                document_size INTEGER NOT NULL,
                document_path TEXT NOT NULL,
                coordinates_json_path TEXT,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processing_status TEXT DEFAULT 'pending',
                ai_analysis_result TEXT,
                filenet_upload_status TEXT DEFAULT 'pending',
                filenet_document_id TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_ghostlayer_user_id 
            ON user_ghostlayer_documents (user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_ghostlayer_status 
            ON user_ghostlayer_documents (processing_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_ghostlayer_uploaded_by 
            ON user_ghostlayer_documents (uploaded_by)
        """)

    def create_ai_document_classifications_table(self, cursor):
        """AI Document Classifications table - stores user-specific AI document classification uploads"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_document_classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                uploaded_by TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                mime_type TEXT,
                document_type TEXT NOT NULL,
                criticality_level TEXT NOT NULL,
                storage_type TEXT, -- Storage location (e.g., Local Folder)
                retention_period TEXT, -- Retention duration in years
                file_path TEXT NOT NULL,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processing_timestamp DATETIME,
                processing_duration REAL,
                ai_confidence_score REAL,
                tags TEXT, -- JSON array of tags
                summary TEXT,
                reasoning TEXT,
                is_archive BOOLEAN DEFAULT 0,
                parent_archive_id INTEGER,
                checksum TEXT,
                processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
                filenet_upload_status TEXT DEFAULT 'pending', -- 'pending', 'success', 'failed'
                filenet_document_id TEXT, -- FileNet document ID if uploaded
                error_message TEXT, -- Error details if processing failed
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (parent_archive_id) REFERENCES ai_document_classifications(id)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_doc_user_id 
            ON ai_document_classifications(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_doc_status 
            ON ai_document_classifications(processing_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_doc_upload_time 
            ON ai_document_classifications(upload_timestamp)
        """)
        
        # Add new columns if they don't exist (migration)
        try:
            cursor.execute("ALTER TABLE ai_document_classifications ADD COLUMN storage_type TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE ai_document_classifications ADD COLUMN retention_period TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Document Operations
    def insert_document(self, document_data: Dict) -> int:
        """Insert a new document record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO documents (
                filename, original_filename, file_size, file_type, mime_type,
                document_type, criticality_level, file_path, processing_timestamp,
                processing_duration, ai_confidence_score, tags, summary, reasoning,
                is_archive, parent_archive_id, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_data['filename'],
            document_data['original_filename'],
            document_data['file_size'],
            document_data['file_type'],
            document_data.get('mime_type'),
            document_data['document_type'],
            document_data['criticality_level'],
            document_data.get('file_path'),
            document_data.get('processing_timestamp'),
            document_data.get('processing_duration'),
            document_data.get('ai_confidence_score'),
            json.dumps(document_data.get('tags', [])),
            document_data.get('summary'),
            document_data.get('reasoning'),
            document_data.get('is_archive', 0),
            document_data.get('parent_archive_id'),
            document_data.get('checksum')
        ))
        
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Document inserted with ID: {document_id}")
        return document_id
    
    def get_documents(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get documents with pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM documents 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return documents
    
    def get_document_by_id(self, document_id: int) -> Optional[Dict]:
        """Get a specific document by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # Processing Logs Operations
    def insert_processing_log(self, log_data: Dict) -> int:
        """Insert a processing log entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO processing_logs (
                document_id, processing_step, status, start_time, end_time,
                duration, details, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_data['document_id'],
            log_data['processing_step'],
            log_data['status'],
            log_data.get('start_time'),
            log_data.get('end_time'),
            log_data.get('duration'),
            json.dumps(log_data.get('details', {})),
            log_data.get('error_message')
        ))
        
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    
    # FileNet Upload Operations
    def insert_filenet_upload(self, upload_data: Dict) -> int:
        """Insert a FileNet upload record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO filenet_uploads (
                document_id, upload_type, queue_id, upload_status,
                upload_timestamp, completion_timestamp, filenet_path,
                error_message, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            upload_data['document_id'],
            upload_data['upload_type'],
            upload_data.get('queue_id'),
            upload_data['upload_status'],
            upload_data.get('upload_timestamp'),
            upload_data.get('completion_timestamp'),
            upload_data.get('filenet_path'),
            upload_data.get('error_message'),
            upload_data.get('retry_count', 0)
        ))
        
        upload_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return upload_id
    
    # System Metrics Operations
    def insert_system_metric(self, metric_data: Dict) -> int:
        """Insert a system metric"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO system_metrics (
                metric_name, metric_value, metric_unit, additional_data
            ) VALUES (?, ?, ?, ?)
        """, (
            metric_data['metric_name'],
            metric_data['metric_value'],
            metric_data.get('metric_unit'),
            json.dumps(metric_data.get('additional_data', {}))
        ))
        
        metric_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return metric_id
    
    def get_system_stats(self) -> Dict:
        """Get system statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Document statistics
        cursor.execute("SELECT COUNT(*) FROM documents")
        total_documents = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE processing_timestamp IS NOT NULL")
        processed_documents = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(processing_duration) FROM documents WHERE processing_duration IS NOT NULL")
        avg_processing_time = cursor.fetchone()[0] or 0
        
        # FileNet upload statistics
        cursor.execute("SELECT COUNT(*) FROM filenet_uploads WHERE upload_status = 'success'")
        successful_uploads = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM filenet_uploads")
        total_uploads = cursor.fetchone()[0]
        
        success_rate = (successful_uploads / total_uploads * 100) if total_uploads > 0 else 0
        
        # Document categories
        cursor.execute("SELECT COUNT(*) FROM document_categories")
        total_categories = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_documents': total_documents,
            'processed_documents': processed_documents,
            'avg_processing_time': round(avg_processing_time, 2),
            'successful_uploads': successful_uploads,
            'total_uploads': total_uploads,
            'success_rate': round(success_rate, 1),
            'total_categories': total_categories
        }
    
    def get_analytics_data(self, user_id: int = None) -> Dict:
        """Get comprehensive analytics data for dashboard (includes AI + GhostLayer)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build WHERE clause for user filtering
        user_filter_ai = f"WHERE user_id = {user_id}" if user_id else ""
        user_filter_gl = f"WHERE user_id = {user_id}" if user_id else ""
        
        # Total documents processed today (AI + GhostLayer)
        cursor.execute(f"""
            SELECT COUNT(*) FROM ai_document_classifications 
            {user_filter_ai} {'AND' if user_id else 'WHERE'} DATE(upload_timestamp) = DATE('now')
        """)
        ai_today = cursor.fetchone()[0]
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            {user_filter_gl} {'AND' if user_id else 'WHERE'} DATE(upload_timestamp) = DATE('now')
        """)
        gl_today = cursor.fetchone()[0]
        
        processed_today = ai_today + gl_today
        
        # Total documents
        cursor.execute(f"""
            SELECT COUNT(*) FROM ai_document_classifications 
            {user_filter_ai}
        """)
        total_ai = cursor.fetchone()[0]
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            {user_filter_gl}
        """)
        total_gl = cursor.fetchone()[0]
        
        total_documents = total_ai + total_gl
        
        # Error rate calculation (AI + GhostLayer)
        cursor.execute(f"""
            SELECT COUNT(*) FROM ai_document_classifications 
            {user_filter_ai} {'AND' if user_id else 'WHERE'} processing_status = 'failed'
        """)
        ai_failed = cursor.fetchone()[0]
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            {user_filter_gl} {'AND' if user_id else 'WHERE'} processing_status = 'failed'
        """)
        gl_failed = cursor.fetchone()[0]
        
        total_failed = ai_failed + gl_failed
        error_rate = (total_failed / total_documents * 100) if total_documents > 0 else 0
        
        # Document types distribution (AI + GhostLayer combined)
        cursor.execute(f"""
            SELECT document_type, COUNT(*) as count 
            FROM ai_document_classifications 
            {user_filter_ai} {'AND' if user_id else 'WHERE'} document_type IS NOT NULL AND document_type != 'Unknown'
            GROUP BY document_type
        """)
        ai_types = cursor.fetchall()
        
        cursor.execute(f"""
            SELECT document_type, COUNT(*) as count 
            FROM user_ghostlayer_documents 
            {user_filter_gl} {'AND' if user_id else 'WHERE'} document_type IS NOT NULL AND document_type != 'Unknown'
            GROUP BY document_type
        """)
        gl_types = cursor.fetchall()
        
        # Combine document types
        type_counts = {}
        for row in ai_types + gl_types:
            type_counts[row[0]] = type_counts.get(row[0], 0) + row[1]
        
        document_types = [{'name': k, 'count': v} for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)]
        
        # Criticality levels distribution (AI only - GhostLayer doesn't have criticality)
        cursor.execute(f"""
            SELECT criticality_level, COUNT(*) as count 
            FROM ai_document_classifications 
            {user_filter_ai} {'AND' if user_id else 'WHERE'} criticality_level IS NOT NULL AND criticality_level != 'Unknown'
            GROUP BY criticality_level 
            ORDER BY count DESC
        """)
        criticality_levels = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Processing trends (last 30 days) - AI + GhostLayer combined
        cursor.execute(f"""
            SELECT DATE(upload_timestamp) as date, COUNT(*) as count
            FROM ai_document_classifications 
            {user_filter_ai} {'AND' if user_id else 'WHERE'} upload_timestamp >= datetime('now', '-30 days')
            GROUP BY DATE(upload_timestamp)
        """)
        ai_trends = cursor.fetchall()
        
        cursor.execute(f"""
            SELECT DATE(upload_timestamp) as date, COUNT(*) as count
            FROM user_ghostlayer_documents 
            {user_filter_gl} {'AND' if user_id else 'WHERE'} upload_timestamp >= datetime('now', '-30 days')
            GROUP BY DATE(upload_timestamp)
        """)
        gl_trends = cursor.fetchall()
        
        # Combine trends by date
        trend_counts = {}
        for row in ai_trends + gl_trends:
            trend_counts[row[0]] = trend_counts.get(row[0], 0) + row[1]
        
        processing_trends = [{'date': k, 'count': v} for k, v in sorted(trend_counts.items())]
        
        # File types distribution (AI + GhostLayer)
        cursor.execute(f"""
            SELECT file_type, COUNT(*) as count 
            FROM ai_document_classifications 
            {user_filter_ai} {'AND' if user_id else 'WHERE'} file_type IS NOT NULL AND file_type != ''
            GROUP BY file_type
        """)
        ai_file_types = cursor.fetchall()
        
        cursor.execute(f"""
            SELECT document_format, COUNT(*) as count 
            FROM user_ghostlayer_documents 
            {user_filter_gl} {'AND' if user_id else 'WHERE'} document_format IS NOT NULL AND document_format != ''
            GROUP BY document_format
        """)
        gl_file_types = cursor.fetchall()
        
        # Combine file types
        file_type_counts = {}
        for row in ai_file_types + gl_file_types:
            file_type_counts[row[0]] = file_type_counts.get(row[0], 0) + row[1]
        
        file_types = [{'name': k, 'count': v} for k, v in sorted(file_type_counts.items(), key=lambda x: x[1], reverse=True)]
        
        # GhostLayer specific stats
        cursor.execute(f"""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            {user_filter_gl}
        """)
        ghostlayer_count = cursor.fetchone()[0]
        
        # AI Classification specific stats
        cursor.execute(f"""
            SELECT COUNT(*) FROM ai_document_classifications 
            {user_filter_ai}
        """)
        ai_classification_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_documents': total_documents,
            'ai_documents': ai_classification_count,
            'ghostlayer_documents': ghostlayer_count,
            'processed_today': processed_today,
            'error_rate': round(error_rate, 1),
            'success_rate': round(100 - error_rate, 1),
            'document_types': document_types,
            'criticality_levels': criticality_levels,
            'processing_trends': processing_trends,
            'file_types': file_types
        }
    
    # Error Logging
    def insert_error_log(self, error_data: Dict) -> int:
        """Insert an error log entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO error_logs (
                error_type, error_message, stack_trace, context_data,
                severity, resolution_notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            error_data['error_type'],
            error_data['error_message'],
            error_data.get('stack_trace'),
            json.dumps(error_data.get('context_data', {})),
            error_data.get('severity', 'medium'),
            error_data.get('resolution_notes')
        ))
        
        error_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return error_id

    # Configuration Management
    def set_config(self, key: str, value: str, config_type: str = 'string', description: str = None):
        """Set a configuration value"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO configuration (
                config_key, config_value, config_type, description, updated_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (key, value, config_type, description))
        
        conn.commit()
        conn.close()
    
    def get_config(self, key: str) -> Optional[str]:
        """Get a configuration value"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT config_value FROM configuration WHERE config_key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None

    # GhostLayer Documents Operations
    def insert_ghostlayer_document(self, document_data: Dict) -> int:
        """Insert a new GhostLayer document record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ghostlayer_documents (
                document_name, document_type, document_format, document_size,
                document_path, coordinates_json_path, processing_status, ai_analysis_result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_data['document_name'],
            document_data['document_type'],
            document_data['document_format'],
            document_data['document_size'],
            document_data['document_path'],
            document_data.get('coordinates_json_path'),
            document_data.get('processing_status', 'pending'),
            json.dumps(document_data.get('ai_analysis_result', {}))
        ))
        
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"GhostLayer document inserted with ID: {document_id}")
        return document_id
    
    def insert_ai_document_classification(self, document_data: Dict) -> int:
        """Insert a new AI Document Classification record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ai_document_classifications (
                user_id, uploaded_by, filename, original_filename, file_size, file_type,
                mime_type, document_type, criticality_level, storage_type, retention_period,
                file_path, processing_timestamp, processing_duration, ai_confidence_score, 
                tags, summary, reasoning, is_archive, parent_archive_id, checksum, 
                processing_status, filenet_upload_status, filenet_document_id, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_data['user_id'],
            document_data['uploaded_by'],
            document_data['filename'],
            document_data['original_filename'],
            document_data['file_size'],
            document_data['file_type'],
            document_data.get('mime_type'),
            document_data['document_type'],
            document_data['criticality_level'],
            document_data.get('storage_type', 'Local Folder'),
            document_data.get('retention_period', '3'),
            document_data['file_path'],
            document_data.get('processing_timestamp'),
            document_data.get('processing_duration'),
            document_data.get('ai_confidence_score'),
            json.dumps(document_data.get('tags', [])),
            document_data.get('summary'),
            document_data.get('reasoning'),
            document_data.get('is_archive', 0),
            document_data.get('parent_archive_id'),
            document_data.get('checksum'),
            document_data.get('processing_status', 'pending'),
            document_data.get('filenet_upload_status', 'pending'),
            document_data.get('filenet_document_id'),
            document_data.get('error_message')
        ))
        
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"AI Document Classification inserted with ID: {document_id} for user: {document_data['user_id']}")
        return document_id
    
    def get_ai_document_classifications(self, user_id: int = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get AI Document Classifications with optional user filtering"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT * FROM ai_document_classifications 
                WHERE user_id = ?
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM ai_document_classifications 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return documents
    
    def get_ai_document_classification_by_id(self, document_id: int) -> Optional[Dict]:
        """Get a specific AI Document Classification by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM ai_document_classifications WHERE id = ?
        """, (document_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_ai_document_classification(self, document_id: int, update_data: Dict) -> bool:
        """Update an AI Document Classification record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build dynamic update query
        set_clauses = []
        values = []
        
        for key, value in update_data.items():
            if key in ['tags'] and isinstance(value, list):
                set_clauses.append(f"{key} = ?")
                values.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        if not set_clauses:
            conn.close()
            return False
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values.append(document_id)
        
        query = f"""
            UPDATE ai_document_classifications 
            SET {', '.join(set_clauses)}
            WHERE id = ?
        """
        
        try:
            cursor.execute(query, values)
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error updating AI document classification {document_id}: {e}")
            conn.close()
            return False
    
    def delete_ai_document_classification(self, document_id: int) -> bool:
        """Delete an AI Document Classification and its associated file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get document info before deletion to clean up file
            cursor.execute("""
                SELECT file_path FROM ai_document_classifications WHERE id = ?
            """, (document_id,))
            
            row = cursor.fetchone()
            file_path = row[0] if row else None
            
            # Delete from database
            cursor.execute("""
                DELETE FROM ai_document_classifications WHERE id = ?
            """, (document_id,))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            # Delete physical file if it exists
            if success and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {e}")
            
            return success
        except Exception as e:
            logger.error(f"Error deleting AI document classification {document_id}: {e}")
            conn.close()
            return False
    
    # User GhostLayer Documents Operations
    def insert_user_ghostlayer_document(self, document_data: Dict) -> int:
        """Insert a new user GhostLayer document record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_ghostlayer_documents (
                user_id, uploaded_by, document_name, document_type, document_format,
                document_size, document_path, coordinates_json_path, processing_status,
                ai_analysis_result, filenet_upload_status, filenet_document_id, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_data['user_id'],
            document_data['uploaded_by'],
            document_data['document_name'],
            document_data['document_type'],
            document_data['document_format'],
            document_data['document_size'],
            document_data['document_path'],
            document_data.get('coordinates_json_path'),
            document_data.get('processing_status', 'pending'),
            json.dumps(document_data.get('ai_analysis_result', {})),
            document_data.get('filenet_upload_status', 'pending'),
            document_data.get('filenet_document_id'),
            document_data.get('error_message')
        ))
        
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"User GhostLayer document inserted with ID: {document_id}")
        return document_id
    
    def get_user_ghostlayer_documents(self, user_id: int = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get user GhostLayer documents with optional user filtering and pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT * FROM user_ghostlayer_documents 
                WHERE user_id = ?
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM user_ghostlayer_documents 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return documents
    
    def get_user_ghostlayer_document_by_id(self, document_id: int) -> Optional[Dict]:
        """Get a specific user GhostLayer document by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_ghostlayer_documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_user_ghostlayer_document(self, document_id: int, update_data: Dict) -> bool:
        """Update user GhostLayer document record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Build dynamic update query
            set_clauses = []
            values = []
            
            for key, value in update_data.items():
                if key in ['document_type', 'coordinates_json_path', 'processing_status', 'ai_analysis_result', 'filenet_upload_status', 
                          'filenet_document_id', 'error_message']:
                    set_clauses.append(f"{key} = ?")
                    if key == 'ai_analysis_result' and isinstance(value, dict):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
            
            if not set_clauses:
                conn.close()
                return False
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(document_id)
            
            query = f"UPDATE user_ghostlayer_documents SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
            
            if cursor.rowcount > 0:
                logger.info(f"User GhostLayer document {document_id} updated successfully")
                return True
            else:
                logger.warning(f"User GhostLayer document {document_id} not found for update")
                return False
        except Exception as e:
            logger.error(f"Error updating user GhostLayer document {document_id}: {e}")
            conn.close()
            return False
    
    def delete_user_ghostlayer_document(self, document_id: int) -> bool:
        """Delete user GhostLayer document record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM user_ghostlayer_documents WHERE id = ?", (document_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"User GhostLayer document {document_id} deleted successfully")
                return True
            else:
                logger.warning(f"User GhostLayer document {document_id} not found for deletion")
                return False
        except Exception as e:
            logger.error(f"Error deleting user GhostLayer document {document_id}: {e}")
            conn.close()
            return False
        finally:
            conn.close()
    
    def get_ghostlayer_documents(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get GhostLayer documents with pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM ghostlayer_documents 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return documents
    
    def get_ghostlayer_document_by_id(self, document_id: int) -> Optional[Dict]:
        """Get a specific GhostLayer document by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ghostlayer_documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_ghostlayer_document_status(self, document_id: int, status: str, ai_result: Dict = None) -> bool:
        """Update GhostLayer document processing status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if ai_result:
                cursor.execute("""
                    UPDATE ghostlayer_documents 
                    SET processing_status = ?, ai_analysis_result = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, json.dumps(ai_result), document_id))
            else:
                cursor.execute("""
                    UPDATE ghostlayer_documents 
                    SET processing_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, document_id))
            
            conn.commit()
            conn.close()
            logger.info(f"GhostLayer document {document_id} status updated to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating GhostLayer document {document_id}: {e}")
            conn.close()
            return False
    
    def get_ghostlayer_stats(self) -> Dict:
        """Get GhostLayer documents statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total documents
        cursor.execute("SELECT COUNT(*) FROM ghostlayer_documents")
        total_documents = cursor.fetchone()[0]
        
        # Documents by status
        cursor.execute("""
            SELECT processing_status, COUNT(*) 
            FROM ghostlayer_documents 
            GROUP BY processing_status
        """)
        status_counts = dict(cursor.fetchall())
        
        # Documents by type
        cursor.execute("""
            SELECT document_type, COUNT(*) 
            FROM ghostlayer_documents 
            GROUP BY document_type
        """)
        type_counts = dict(cursor.fetchall())
        
        # Documents by format
        cursor.execute("""
            SELECT document_format, COUNT(*) 
            FROM ghostlayer_documents 
            GROUP BY document_format
        """)
        format_counts = dict(cursor.fetchall())
        
        # Total size
        cursor.execute("SELECT SUM(document_size) FROM ghostlayer_documents")
        total_size = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_documents': total_documents,
            'status_counts': status_counts,
            'type_counts': type_counts,
            'format_counts': format_counts,
            'total_size': total_size
        }
    
    def get_user_ghostlayer_stats(self) -> Dict:
        """Get comprehensive GhostLayer user statistics for admin dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total documents
        cursor.execute("SELECT COUNT(*) FROM user_ghostlayer_documents")
        total_documents = cursor.fetchone()[0]
        
        # Documents uploaded today
        cursor.execute("""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            WHERE DATE(upload_timestamp) = DATE('now')
        """)
        documents_today = cursor.fetchone()[0]
        
        # Documents uploaded this week
        cursor.execute("""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            WHERE DATE(upload_timestamp) >= DATE('now', '-7 days')
        """)
        documents_this_week = cursor.fetchone()[0]
        
        # Documents by status
        cursor.execute("""
            SELECT processing_status, COUNT(*) 
            FROM user_ghostlayer_documents 
            GROUP BY processing_status
        """)
        status_counts = dict(cursor.fetchall())
        
        # Documents by type
        cursor.execute("""
            SELECT document_type, COUNT(*) 
            FROM user_ghostlayer_documents 
            GROUP BY document_type
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        type_counts = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Documents by format
        cursor.execute("""
            SELECT document_format, COUNT(*) 
            FROM user_ghostlayer_documents 
            GROUP BY document_format
        """)
        format_counts = dict(cursor.fetchall())
        
        # Total size
        cursor.execute("SELECT SUM(document_size) FROM user_ghostlayer_documents")
        total_size = cursor.fetchone()[0] or 0
        
        # Documents by user (top 10 users)
        cursor.execute("""
            SELECT uploaded_by, COUNT(*) as doc_count, SUM(document_size) as total_size
            FROM user_ghostlayer_documents 
            GROUP BY uploaded_by
            ORDER BY doc_count DESC
            LIMIT 10
        """)
        user_stats = [
            {
                'username': row[0],
                'document_count': row[1],
                'total_size': row[2] or 0
            } for row in cursor.fetchall()
        ]
        
        # Recent uploads (last 10)
        cursor.execute("""
            SELECT id, uploaded_by, document_name, document_type, document_format, 
                   document_size, upload_timestamp, processing_status
            FROM user_ghostlayer_documents 
            ORDER BY upload_timestamp DESC
            LIMIT 10
        """)
        recent_uploads = [
            {
                'id': row[0],
                'uploaded_by': row[1],
                'document_name': row[2],
                'document_type': row[3],
                'document_format': row[4],
                'document_size': row[5],
                'upload_timestamp': row[6],
                'processing_status': row[7]
            } for row in cursor.fetchall()
        ]
        
        # Processing trends (last 30 days)
        cursor.execute("""
            SELECT DATE(upload_timestamp) as date, COUNT(*) as count
            FROM user_ghostlayer_documents 
            WHERE upload_timestamp >= DATE('now', '-30 days')
            GROUP BY DATE(upload_timestamp)
            ORDER BY date ASC
        """)
        processing_trends = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'total_documents': total_documents,
            'documents_today': documents_today,
            'documents_this_week': documents_this_week,
            'status_counts': status_counts,
            'type_counts': type_counts,
            'format_counts': format_counts,
            'total_size': total_size,
            'user_stats': user_stats,
            'recent_uploads': recent_uploads,
            'processing_trends': processing_trends
        }
    
    def delete_ghostlayer_document(self, document_id: int) -> bool:
        """Delete a GhostLayer document record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM ghostlayer_documents WHERE id = ?", (document_id,))
            conn.commit()
            conn.close()
            
            if cursor.rowcount > 0:
                logger.info(f"GhostLayer document {document_id} deleted successfully")
                return True
            else:
                logger.warning(f"GhostLayer document {document_id} not found for deletion")
                return False
        except Exception as e:
            logger.error(f"Error deleting GhostLayer document {document_id}: {e}")
            conn.close()
            return False

    # User Management Methods
    def authenticate_user(self, username_or_email: str, password: str) -> Optional[Dict]:
        """Authenticate user with username/email and password"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        logger.info(f"Authenticating user: {username_or_email}")
        logger.info(f"Password hash: {password_hash[:10]}...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, username, full_name, email, role, is_active, is_mfa_enabled, mfa_secret, mfa_setup_complete, has_changed_default_password, last_login, ai_classification_access, ghostlayer_access, ghostlayer_view_original, ghostlayer_view_redacted
                FROM users 
                WHERE (username = ? OR email = ?) AND password_hash = ? AND is_active = 1
            """, (username_or_email, username_or_email, password_hash))
            
            user = cursor.fetchone()
            if user:
                logger.info(f"User found: {user[1]} (ID: {user[0]})")
                # Update last login
                cursor.execute("""
                    UPDATE users SET last_login = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (user[0],))
                conn.commit()
                
                return {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[2],
                    'email': user[3],
                    'role': user[4],
                    'is_active': user[5],
                    'is_mfa_enabled': user[6],
                    'mfa_secret': user[7],
                    'mfa_setup_complete': user[8],
                    'has_changed_default_password': user[9],
                    'last_login': user[10],
                    'ai_classification_access': user[11],
                    'ghostlayer_access': user[12],
                    'ghostlayer_view_original': user[13],
                    'ghostlayer_view_redacted': user[14]
                }
            else:
                logger.warning(f"No user found for: {username_or_email}")
                # Let's check what users exist
                cursor.execute("SELECT username, email, is_active FROM users")
                all_users = cursor.fetchall()
                logger.info(f"Available users: {all_users}")
            return None
        except Exception as e:
            logger.error(f"Error authenticating user {username}: {e}")
            return None
        finally:
            conn.close()
    
    def create_user(self, username: str, password: str, full_name: str, 
                   email: str = None, role: str = 'analyst', is_active: bool = True, 
                   is_mfa_enabled: bool = False, ai_classification_access: bool = True,
                   ghostlayer_access: bool = True, ghostlayer_view_original: bool = True,
                   ghostlayer_view_redacted: bool = True, created_by: int = None) -> bool:
        """Create a new user"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Auto-append @idmsdemo.com if email doesn't contain @
        if email and '@' not in email:
            email = f"{email}@idmsdemo.com"
        elif not email:
            email = f"{username}@idmsdemo.com"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, email, role, is_active, is_mfa_enabled, ai_classification_access, ghostlayer_access, ghostlayer_view_original, ghostlayer_view_redacted, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, password_hash, full_name, email, role, is_active, is_mfa_enabled, ai_classification_access, ghostlayer_access, ghostlayer_view_original, ghostlayer_view_redacted, created_by))
            conn.commit()
            logger.info(f"User {username} created successfully with email {email}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Username {username} already exists")
            return False
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, username, full_name, email, role, is_active, 
                       is_mfa_enabled, mfa_setup_complete, has_changed_default_password, last_login, created_at, updated_at, ai_classification_access, ghostlayer_access, ghostlayer_view_original, ghostlayer_view_redacted
                FROM users 
                ORDER BY created_at DESC
            """)
            
            users = []
            for row in cursor.fetchall():
                users.append({
                    'id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'email': row[3],
                    'role': row[4],
                    'is_active': row[5],
                    'is_mfa_enabled': row[6],
                    'mfa_setup_complete': row[7],
                    'has_changed_default_password': row[8],
                    'last_login': row[9],
                    'created_at': row[10],
                    'updated_at': row[11],
                    'ai_classification_access': row[12],
                    'ghostlayer_access': row[13],
                    'ghostlayer_view_original': row[14],
                    'ghostlayer_view_redacted': row[15]
                })
            return users
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
        finally:
            conn.close()
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """Update user information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Build update query dynamically
            update_fields = []
            values = []
            
            for field, value in kwargs.items():
                if field == 'password':
                    import hashlib
                    value = hashlib.sha256(value.encode()).hexdigest()
                    field = 'password_hash'
                elif field in ['username', 'full_name', 'email', 'role', 'is_active', 'is_mfa_enabled', 'ai_classification_access', 'ghostlayer_access', 'ghostlayer_view_original', 'ghostlayer_view_redacted']:
                    pass
                else:
                    continue
                
                update_fields.append(f"{field} = ?")
                values.append(value)
            
            if not update_fields:
                return False
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)
            
            cursor.execute(f"""
                UPDATE users 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, values)
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user (soft delete by setting is_active = 0)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND id != 1
            """, (user_id,))  # Prevent deleting the default admin user
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def setup_mfa(self, user_id: int, mfa_secret: str) -> bool:
        """Setup MFA for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET mfa_secret = ?, mfa_setup_complete = 1, is_mfa_enabled = 1 
                WHERE id = ?
            """, (mfa_secret, user_id))
            conn.commit()
            logger.info(f"MFA setup completed for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting up MFA for user {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def disable_mfa(self, user_id: int) -> bool:
        """Disable MFA for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET is_mfa_enabled = 0, mfa_secret = NULL, mfa_setup_complete = 0 
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            logger.info(f"MFA disabled for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error disabling MFA for user {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_mfa_status(self, user_id: int) -> Optional[dict]:
        """Get MFA status for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT is_mfa_enabled, mfa_secret, mfa_setup_complete 
                FROM users WHERE id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'is_mfa_enabled': result[0],
                    'mfa_secret': result[1],
                    'mfa_setup_complete': result[2]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting MFA status for user {user_id}: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get user by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, username, full_name, email, role, is_active, is_mfa_enabled, 
                       mfa_secret, mfa_setup_complete, has_changed_default_password, last_login, created_at, ai_classification_access, ghostlayer_access, ghostlayer_view_original, ghostlayer_view_redacted
                FROM users WHERE id = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            if user:
                return {
                    'id': user[0],
                    'username': user[1],
                    'full_name': user[2],
                    'email': user[3],
                    'role': user[4],
                    'is_active': user[5],
                    'is_mfa_enabled': user[6],
                    'mfa_secret': user[7],
                    'mfa_setup_complete': user[8],
                    'has_changed_default_password': user[9],
                    'last_login': user[10],
                    'created_at': user[11],
                    'ai_classification_access': user[12],
                    'ghostlayer_access': user[13],
                    'ghostlayer_view_original': user[14],
                    'ghostlayer_view_redacted': user[15]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
        finally:
            conn.close()
    
    def update_password_changed(self, user_id: int, new_password: str = None) -> bool:
        """Mark that user has changed their default password and optionally update the password"""
        import hashlib
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if new_password:
                # Update both password and flag
                new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = ?, has_changed_default_password = 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (new_password_hash, user_id))
            else:
                # Only update the flag
                cursor.execute("""
                    UPDATE users 
                    SET has_changed_default_password = 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (user_id,))
            conn.commit()
            logger.info(f"Password change status updated for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating password change status for user {user_id}: {e}")
            return False
        finally:
            conn.close()

    def get_user_dashboard_stats(self, user_id: int) -> Dict:
        """Get personalized dashboard statistics for a specific user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total AI documents for user
        cursor.execute("""
            SELECT COUNT(*) FROM ai_document_classifications 
            WHERE user_id = ?
        """, (user_id,))
        total_ai_docs = cursor.fetchone()[0]
        
        # Total GhostLayer documents for user
        cursor.execute("""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            WHERE user_id = ?
        """, (user_id,))
        total_gl_docs = cursor.fetchone()[0]
        
        # Documents uploaded today (AI)
        cursor.execute("""
            SELECT COUNT(*) FROM ai_document_classifications 
            WHERE user_id = ? AND DATE(upload_timestamp) = DATE('now')
        """, (user_id,))
        ai_docs_today = cursor.fetchone()[0]
        
        # Documents uploaded today (GhostLayer)
        cursor.execute("""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            WHERE user_id = ? AND DATE(upload_timestamp) = DATE('now')
        """, (user_id,))
        gl_docs_today = cursor.fetchone()[0]
        
        # Documents uploaded this week (AI)
        cursor.execute("""
            SELECT COUNT(*) FROM ai_document_classifications 
            WHERE user_id = ? AND DATE(upload_timestamp) >= DATE('now', '-7 days')
        """, (user_id,))
        ai_docs_week = cursor.fetchone()[0]
        
        # Documents uploaded this week (GhostLayer)
        cursor.execute("""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            WHERE user_id = ? AND DATE(upload_timestamp) >= DATE('now', '-7 days')
        """, (user_id,))
        gl_docs_week = cursor.fetchone()[0]
        
        # User's success rate (AI documents)
        cursor.execute("""
            SELECT COUNT(*) FROM ai_document_classifications 
            WHERE user_id = ? AND processing_status = 'completed'
        """, (user_id,))
        successful_ai = cursor.fetchone()[0]
        
        # User's success rate (GhostLayer)
        cursor.execute("""
            SELECT COUNT(*) FROM user_ghostlayer_documents 
            WHERE user_id = ? AND processing_status = 'completed'
        """, (user_id,))
        successful_gl = cursor.fetchone()[0]
        
        total_docs = total_ai_docs + total_gl_docs
        total_successful = successful_ai + successful_gl
        success_rate = (total_successful / total_docs * 100) if total_docs > 0 else 0
        
        # User's storage (AI documents)
        cursor.execute("""
            SELECT SUM(file_size) FROM ai_document_classifications 
            WHERE user_id = ?
        """, (user_id,))
        ai_storage = cursor.fetchone()[0] or 0
        
        # User's storage (GhostLayer)
        cursor.execute("""
            SELECT SUM(document_size) FROM user_ghostlayer_documents 
            WHERE user_id = ?
        """, (user_id,))
        gl_storage = cursor.fetchone()[0] or 0
        
        # User's document types (AI)
        cursor.execute("""
            SELECT document_type, COUNT(*) 
            FROM ai_document_classifications 
            WHERE user_id = ?
            GROUP BY document_type
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """, (user_id,))
        ai_doc_types = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # User's document types (GhostLayer)
        cursor.execute("""
            SELECT document_type, COUNT(*) 
            FROM user_ghostlayer_documents 
            WHERE user_id = ?
            GROUP BY document_type
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """, (user_id,))
        gl_doc_types = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Combine and aggregate document types
        type_counts = {}
        for item in ai_doc_types + gl_doc_types:
            type_counts[item['name']] = type_counts.get(item['name'], 0) + item['count']
        
        combined_types = [{'name': k, 'count': v} for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)][:10]
        
        # User's recent uploads (combined AI + GhostLayer)
        recent_uploads = []
        
        # Get AI documents
        cursor.execute("""
            SELECT 'AI Classification' as source, original_filename as name, document_type, 
                   upload_timestamp, processing_status, criticality_level, file_size
            FROM ai_document_classifications 
            WHERE user_id = ?
            ORDER BY upload_timestamp DESC
            LIMIT 10
        """, (user_id,))
        ai_recent = cursor.fetchall()
        
        # Get GhostLayer documents
        cursor.execute("""
            SELECT 'GhostLayer AI' as source, document_name as name, document_type, 
                   upload_timestamp, processing_status, NULL as criticality, document_size
            FROM user_ghostlayer_documents 
            WHERE user_id = ?
            ORDER BY upload_timestamp DESC
            LIMIT 10
        """, (user_id,))
        gl_recent = cursor.fetchall()
        
        # Combine and sort by timestamp
        all_recent = list(ai_recent) + list(gl_recent)
        all_recent.sort(key=lambda x: x[3], reverse=True)
        
        recent_uploads = [
            {
                'source': row[0],
                'name': row[1],
                'type': row[2],
                'timestamp': row[3],
                'status': row[4],
                'criticality': row[5],
                'size': row[6]
            } for row in all_recent[:10]
        ]
        
        conn.close()
        
        return {
            'total_documents': total_docs,
            'total_ai_documents': total_ai_docs,
            'total_ghostlayer_documents': total_gl_docs,
            'documents_today': ai_docs_today + gl_docs_today,
            'ai_docs_today': ai_docs_today,
            'gl_docs_today': gl_docs_today,
            'documents_this_week': ai_docs_week + gl_docs_week,
            'success_rate': round(success_rate, 1),
            'total_storage': ai_storage + gl_storage,
            'ai_storage': ai_storage,
            'gl_storage': gl_storage,
            'document_types': combined_types,
            'recent_uploads': recent_uploads
        }

# Global database instance
db = IDMSDatabase()
# Run migration to add new columns to existing tables
db.migrate_database()
