"""Storage and file management utilities."""

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


def ensure_directory(path: str) -> Path:
    """Ensure directory exists, create if it doesn't.
    
    Args:
        path: Directory path to ensure
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_benchmark_path(session_id: str, model_key: str = None) -> Path:
    """Get benchmark output directory path.
    
    Args:
        session_id: Benchmark session ID
        model_key: Model key (optional)
        
    Returns:
        Path to benchmark directory
    """
    base_path = Path("outputs") / session_id
    if model_key:
        base_path = base_path / model_key
    return ensure_directory(str(base_path))


def safe_json_load(file_path: str, default: Any = None) -> Any:
    """Safely load JSON file with error handling.
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid
        
    Returns:
        Loaded JSON data or default value
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        print(f"Error loading JSON from {file_path}: {e}")
        return default


def safe_json_save(data: Any, file_path: str, indent: int = 2) -> bool:
    """Safely save data to JSON file with error handling.
    
    Args:
        data: Data to save
        file_path: Path to JSON file
        indent: JSON indentation level
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except (IOError, TypeError) as e:
        print(f"Error saving JSON to {file_path}: {e}")
        return False


class BenchmarkStorage:
    """Storage manager for benchmark results."""
    
    def __init__(self, base_path: str = "outputs"):
        """Initialize benchmark storage.
        
        Args:
            base_path: Base directory for storing benchmark data
        """
        self.base_path = Path(base_path)
        ensure_directory(str(self.base_path))
    
    def create_session_directory(self, session_id: str, model_key: str) -> Path:
        """Create directory structure for benchmark session.
        
        Args:
            session_id: Benchmark session ID
            model_key: Model key
            
        Returns:
            Path to session directory
        """
        session_path = self.base_path / session_id / model_key
        ensure_directory(str(session_path))
        return session_path
    
    def save_benchmark_results(self, session_id: str, model_key: str, 
                              results: Dict[str, Any]) -> bool:
        """Save benchmark results to files.
        
        Args:
            session_id: Benchmark session ID
            model_key: Model key
            results: Benchmark results data
            
        Returns:
            True if successful
        """
        session_path = self.create_session_directory(session_id, model_key)
        
        # Save different result components
        success = True
        
        # Main results
        if 'results' in results:
            success &= safe_json_save(
                results['results'],
                str(session_path / 'benchmark_results.json')
            )
        
        # Summary data
        if 'summary' in results:
            success &= safe_json_save(
                results['summary'],
                str(session_path / 'benchmark_summary.json')
            )
        
        # Percentile data
        if 'percentiles' in results:
            success &= safe_json_save(
                results['percentiles'],
                str(session_path / 'benchmark_percentile.json')
            )
        
        # Test arguments
        if 'args' in results:
            success &= safe_json_save(
                results['args'],
                str(session_path / 'benchmark_args.json')
            )
        
        return success
    
    def load_benchmark_results(self, session_id: str, model_key: str) -> Dict[str, Any]:
        """Load benchmark results from files.
        
        Args:
            session_id: Benchmark session ID
            model_key: Model key
            
        Returns:
            Dictionary containing benchmark results
        """
        session_path = self.base_path / session_id / model_key
        
        if not session_path.exists():
            return {}
        
        results = {}
        
        # Load different components
        file_mappings = {
            'results': 'benchmark_results.json',
            'summary': 'benchmark_summary.json',
            'percentiles': 'benchmark_percentile.json',
            'args': 'benchmark_args.json'
        }
        
        for key, filename in file_mappings.items():
            file_path = session_path / filename
            if file_path.exists():
                results[key] = safe_json_load(str(file_path), {})
        
        return results
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all benchmark sessions.
        
        Returns:
            List of session information dictionaries
        """
        sessions = []
        
        if not self.base_path.exists():
            return sessions
        
        for session_dir in self.base_path.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_info = {
                'session_id': session_dir.name,
                'models': [],
                'created_at': datetime.fromtimestamp(session_dir.stat().st_ctime).isoformat()
            }
            
            # List models in session
            for model_dir in session_dir.iterdir():
                if model_dir.is_dir():
                    session_info['models'].append(model_dir.name)
            
            sessions.append(session_info)
        
        return sorted(sessions, key=lambda x: x['created_at'], reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a benchmark session and all its data.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if successful
        """
        session_path = self.base_path / session_id
        
        if not session_path.exists():
            return False
        
        try:
            shutil.rmtree(session_path)
            return True
        except OSError as e:
            print(f"Error deleting session {session_id}: {e}")
            return False


class DatabaseManager:
    """SQLite database manager for application data."""
    
    def __init__(self, db_path: str = "data/app.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
    
    def _init_tables(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Model deployment status table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_key TEXT NOT NULL,
                    deployment_tag TEXT,
                    status TEXT NOT NULL,
                    instance_type TEXT,
                    engine_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deployment_endpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_key TEXT UNIQUE NOT NULL,
                    deployment_id TEXT,
                    deployment_method TEXT NOT NULL,
                    model_name TEXT,
                    endpoint_url TEXT NOT NULL,
                    metadata TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Benchmark sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    model_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    test_params TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def update_deployment_status(self, model_key: str, status: str, 
                               deployment_tag: str = None, **kwargs) -> None:
        """Update model deployment status.
        
        Args:
            model_key: Model identifier
            status: Deployment status
            deployment_tag: Deployment tag (optional)
            **kwargs: Additional status fields
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if record exists
            cursor.execute(
                "SELECT id FROM model_deployments WHERE model_key = ?",
                (model_key,)
            )
            
            if cursor.fetchone():
                # Update existing record
                cursor.execute("""
                    UPDATE model_deployments 
                    SET status = ?, deployment_tag = ?, instance_type = ?, 
                        engine_type = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE model_key = ?
                """, (
                    status, deployment_tag, 
                    kwargs.get('instance_type'),
                    kwargs.get('engine_type'),
                    model_key
                ))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO model_deployments 
                    (model_key, status, deployment_tag, instance_type, engine_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    model_key, status, deployment_tag,
                    kwargs.get('instance_type'),
                    kwargs.get('engine_type')
                ))

            conn.commit()

    def upsert_deployment_endpoint(
        self,
        model_key: str,
        deployment_method: str,
        endpoint_url: str,
        *,
        deployment_id: str = None,
        model_name: str = None,
        metadata: Dict[str, Any] | None = None,
        status: str = 'active'
    ) -> None:
        """Insert or update a deployment endpoint record."""
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO deployment_endpoints (model_key, deployment_id, deployment_method, model_name, endpoint_url, metadata, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_key) DO UPDATE SET
                    deployment_id=excluded.deployment_id,
                    deployment_method=excluded.deployment_method,
                    model_name=excluded.model_name,
                    endpoint_url=excluded.endpoint_url,
                    metadata=excluded.metadata,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    model_key,
                    deployment_id,
                    deployment_method,
                    model_name,
                    endpoint_url,
                    metadata_json,
                    status,
                ),
            )

            conn.commit()

    def list_deployment_endpoints(
        self,
        *,
        deployment_method: str | None = None,
        status: str | None = 'active'
    ) -> List[Dict[str, Any]]:
        """Return deployment endpoint records filtered by method/status."""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM deployment_endpoints"
            params = []
            clauses = []

            if deployment_method:
                clauses.append("deployment_method = ?")
                params.append(deployment_method)
            if status:
                clauses.append("status = ?")
                params.append(status)

            if clauses:
                query += " WHERE " + " AND ".join(clauses)

            query += " ORDER BY updated_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

        records: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            metadata_raw = data.get('metadata')
            if metadata_raw:
                try:
                    data['metadata'] = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    data['metadata'] = {'raw': metadata_raw}
            else:
                data['metadata'] = {}
            records.append(data)

        return records
    
    def get_deployment_status(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Get model deployment status.
        
        Args:
            model_key: Model identifier
            
        Returns:
            Deployment status dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM model_deployments 
                WHERE model_key = ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (model_key,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
