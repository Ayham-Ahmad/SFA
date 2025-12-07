import re

class OutputGuard:
    """
    Sanitizes output to prevent leakage of internal technical details (SQL, schemas, IDs).
    """

    # Patterns that look like SQL or database errors
    SQL_PATTERNS = [
        r"(?i)SELECT\s+.*?\s+FROM",
        r"(?i)INSERT\s+INTO",
        r"(?i)UPDATE\s+.*?\s+SET",
        r"(?i)DELETE\s+FROM",
        r"(?i)DROP\s+TABLE",
        r"(?i)sqlite_sequence",
        r"(?i)traceback",
        r"(?i)Traceback \(most recent call last\)",
    ]

    # Sensitive keywords to mask
    SENSITIVE_KEYWORDS = [
        "adsh", "cik", "sic", "blob"
    ]

    @staticmethod
    def sanitize(content: str) -> str:
        if not content:
            return ""

        # SPLIT STRATEGY: Isolate graph data
        parts = content.split("graph_data||")
        text_part = parts[0]
        graph_part = parts[1] if len(parts) > 1 else ""
        
        # Sanitize ONLY the text part
        sanitized_text = text_part

        # 1. Block raw SQL blocks entirely if they are just raw queries
        for pattern in OutputGuard.SQL_PATTERNS:
            if re.search(pattern, synchronized_content := sanitized_text):
               sanitized_text = re.sub(pattern, "[INTERNAL_DATA_PROCESSING]", sanitized_text)

        # 2. Mask sensitive IDs
        for keyword in OutputGuard.SENSITIVE_KEYWORDS:
            sanitized_text = re.sub(r'(?i)\b' + keyword + r'\b', "***", sanitized_text)

        # 3. Last safety net for raw structure
        if sanitized_text.strip().startswith("[(") and sanitized_text.strip().endswith(")]"):
            sanitized_text = "Data retrieved successfully but cannot be displayed in raw format."
            
        # Reassemble
        if graph_part:
            # Note: We append the closing || if it was there? 
            # Actually, the split removes 'graph_data||'.
            # The prompt says: graph_data||{...}||
            # If we split by 'graph_data||', part[1] is '{...}||'.
            # So we just rejoin.
            return sanitized_text + "graph_data||" + graph_part
        else:
            return sanitized_text

    @staticmethod
    def validate(content: str) -> bool:
        """
        Returns True if content is safe to show, False using stricter rules.
        """
        # If it explicitly contains a leakage signal
        if "NO_DATA_FOUND_SIGNAL" in content:
            return True 

        # EXCEPTION: Allow graph_data block even if it looks like code
        if "graph_data||" in content:
            return True

        # If it contains a massive amount of SQL
        if content.count("SELECT") > 2 and content.count("FROM") > 2:
            return False
            
        return True

def sanitize_content(content: str) -> str:
    """Helper wrapper for OutputGuard.sanitize"""
    return OutputGuard.sanitize(content)
