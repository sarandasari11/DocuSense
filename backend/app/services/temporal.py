import re
from typing import Optional, Tuple

class TemporalQueryAnalyzer:
    @staticmethod
    def extract_temporal_constraints(query: str) -> Tuple[str, Optional[int]]:
        """
        Analyze user query to detect target year or temporal scope.
        Returns: (cleaned_query, target_year)
        """
        # Look for 4-digit years between 1990 and 2099
        match = re.search(r'\b(19\d\d|20\d\d)\b', query)
        target_year = None
        if match:
            target_year = int(match.group(1))

        # Check for keywords like "latest", "current", "recent"
        if "latest" in query.lower() or "current" in query.lower():
            # target_year stays None to retrieve latest by default if year isn't explicitly pinned
            pass

        return query, target_year

temporal_analyzer = TemporalQueryAnalyzer()
