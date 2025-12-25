"""
CSV Manager
===========
Handles CSV file connections and schema extraction.
Loads CSV into in-memory SQLite for SQL querying.
"""

import os
import csv
import sqlite3
from typing import Dict, List, Any, Optional


class CSVManager:
    """
    Manager for CSV files.
    Loads CSV into in-memory SQLite database for SQL querying.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize CSV manager.
        
        Args:
            config: Configuration dict with 'path' key
        """
        self.csv_path = config.get("path", "")
        self.table_name: Optional[str] = None
        self.memory_db: Optional[sqlite3.Connection] = None
        self.is_connected = False
        self.original_headers: List[str] = []
        self.clean_headers: List[str] = []
    
    def connect(self) -> bool:
        """
        Load CSV into in-memory SQLite database.
        
        Returns:
            True if loaded successfully
        """
        try:
            if not os.path.exists(self.csv_path):
                return False
            
            # Create in-memory SQLite database
            self.memory_db = sqlite3.connect(":memory:")
            
            # Derive table name from filename
            self.table_name = os.path.splitext(os.path.basename(self.csv_path))[0]
            self.table_name = self._clean_name(self.table_name)
            
            # Read CSV and load into SQLite
            with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                self.original_headers = next(reader)
                self.clean_headers = [self._clean_name(h) for h in self.original_headers]
                
                # Detect column types from first few rows
                sample_rows = []
                for i, row in enumerate(reader):
                    if i < 100:  # Sample first 100 rows for type detection
                        sample_rows.append(row)
                    else:
                        break
                
                # Infer column types
                column_types = self._infer_column_types(sample_rows)
                
                # Create table with inferred types
                columns_def = ", ".join([
                    f'"{h}" {column_types.get(h, "TEXT")}' 
                    for h in self.clean_headers
                ])
                self.memory_db.execute(f'CREATE TABLE "{self.table_name}" ({columns_def})')
                
                # Insert sample rows
                placeholders = ", ".join(["?" for _ in self.clean_headers])
                for row in sample_rows:
                    if len(row) == len(self.clean_headers):
                        self.memory_db.execute(
                            f'INSERT INTO "{self.table_name}" VALUES ({placeholders})',
                            row
                        )
                
                # Continue inserting remaining rows
                f.seek(0)
                reader = csv.reader(f)
                next(reader)  # Skip header
                for i, row in enumerate(reader):
                    if i >= 100 and len(row) == len(self.clean_headers):
                        self.memory_db.execute(
                            f'INSERT INTO "{self.table_name}" VALUES ({placeholders})',
                            row
                        )
                
                self.memory_db.commit()
            
            self.is_connected = True
            return True
            
        except Exception as e:
            print(f"CSV connect error: {e}")
            self.is_connected = False
            return False
    
    def _clean_name(self, name: str) -> str:
        """Clean a name to be SQL-safe."""
        return name.strip().replace(" ", "_").replace("-", "_").replace(".", "_")
    
    def _infer_column_types(self, sample_rows: List[List[str]]) -> Dict[str, str]:
        """
        Infer column types from sample data.
        
        Args:
            sample_rows: List of sample rows
            
        Returns:
            Dict mapping column name to SQL type
        """
        types = {}
        
        for col_idx, col_name in enumerate(self.clean_headers):
            values = [row[col_idx] for row in sample_rows if col_idx < len(row) and row[col_idx]]
            
            if not values:
                types[col_name] = "TEXT"
                continue
            
            # Check if all values are numeric
            try:
                all_int = all(v.replace(",", "").replace("-", "").isdigit() for v in values)
                if all_int:
                    types[col_name] = "INTEGER"
                    continue
            except ValueError:
                pass
            
            # Check if all values are float
            try:
                for v in values:
                    float(v.replace(",", "").replace("$", "").replace("%", ""))
                types[col_name] = "REAL"
                continue
            except ValueError:
                pass
            
            types[col_name] = "TEXT"
        
        return types
    
    def disconnect(self) -> None:
        """Close in-memory database."""
        if self.memory_db:
            self.memory_db.close()
            self.memory_db = None
        self.is_connected = False
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test if CSV file can be read.
        
        Returns:
            Dict with success, message, tables
        """
        if not os.path.exists(self.csv_path):
            return {"success": False, "message": f"CSV file not found: {self.csv_path}"}
        
        if not self.csv_path.lower().endswith('.csv'):
            return {"success": False, "message": "File must have .csv extension"}
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                headers = next(reader)
                row_count = sum(1 for _ in reader)
            
            table_name = os.path.splitext(os.path.basename(self.csv_path))[0]
            
            return {
                "success": True,
                "message": f"CSV valid: {len(headers)} columns, {row_count} rows",
                "tables": [table_name]
            }
        except Exception as e:
            return {"success": False, "message": f"Error reading CSV: {str(e)}"}
    
    def get_tables(self) -> List[str]:
        """
        Get table name (derived from CSV filename).
        
        Returns:
            List with single table name
        """
        if not self.is_connected:
            self.connect()
        return [self.table_name] if self.table_name else []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get detailed schema for the CSV table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dict with columns, types, count
        """
        if not self.is_connected:
            self.connect()
        
        if not self.memory_db:
            return {}
        
        try:
            cursor = self.memory_db.cursor()
            
            # Get column info
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[1],
                    "type": row[2] or "TEXT",
                    "original_name": self.original_headers[row[0]] if row[0] < len(self.original_headers) else row[1],
                    "nullable": True,
                    "is_primary_key": False
                })
            
            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns),
                "row_count": row_count,
                "source_file": os.path.basename(self.csv_path),
                "primary_key": None,
                "foreign_keys": [],
                "indexes": []
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_full_schema(self) -> Dict[str, Any]:
        """
        Get complete schema for the CSV.
        
        Returns:
            Dict with tables list and detailed schema
        """
        tables = self.get_tables()
        schema = {}
        
        for table in tables:
            schema[table] = self.get_table_schema(table)
        
        return {
            "success": True,
            "tables": tables,
            "schema": schema,
            "table_count": len(tables)
        }
    
    def get_schema_for_llm(self) -> str:
        """
        Get formatted schema string for LLM consumption.
        
        Returns:
            Formatted schema string
        """
        schema = self.get_full_schema()
        parts = []
        
        for table_name, table_info in schema.get("schema", {}).items():
            cols = table_info.get("columns", [])
            col_list = ", ".join([f"{c['name']} ({c['type']})" for c in cols])
            parts.append(f"TABLE: {table_name}\nCOLUMNS: {col_list}\nROWS: {table_info.get('row_count', 0)}")
        
        return "\n\n".join(parts)
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute SQL query on in-memory database.
        
        Args:
            query: SQL query string
            
        Returns:
            Dict with success, columns, rows, row_count or error
        """
        if not self.is_connected:
            if not self.connect():
                return {"success": False, "error": "Failed to load CSV"}
        
        try:
            cursor = self.memory_db.cursor()
            cursor.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                self.memory_db.commit()
                return {
                    "success": True,
                    "message": "Query executed",
                    "row_count": cursor.rowcount
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_required_fields() -> List[Dict[str, str]]:
        """Get required connection fields."""
        return [
            {
                "name": "path",
                "label": "CSV File Path",
                "type": "text",
                "required": True,
                "placeholder": "C:\\data\\financial_data.csv"
            }
        ]
