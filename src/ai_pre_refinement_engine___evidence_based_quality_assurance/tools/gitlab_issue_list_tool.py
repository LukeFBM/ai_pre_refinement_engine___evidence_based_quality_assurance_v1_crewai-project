from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
import requests
import json
import os
from math import ceil

class GitLabIssueListInput(BaseModel):
    """Input schema for GitLab Issue List Tool."""
    project_id: str = Field(..., description="GitLab project ID or namespace/project-name")
    state: str = Field(default="opened", description="Issue state filter (opened/closed/all)")
    labels: Optional[str] = Field(default=None, description="Comma-separated label names to filter by")
    per_page: int = Field(default=20, description="Results per page (max 100)", le=100, ge=1)

class GitLabIssueListTool(BaseTool):
    """Tool for listing GitLab repository issues in read-only mode."""

    name: str = "GitLabIssueListTool"
    description: str = (
        "Lists issues from GitLab repositories in read-only mode. "
        "Supports filtering by state (opened/closed/all) and labels. "
        "Returns up to 200 issues with pagination support and summary statistics. "
        "Requires GITLAB_API_KEY environment variable for API access."
    )
    args_schema: Type[BaseModel] = GitLabIssueListInput

    def _run(self, project_id: str, state: str = "opened", labels: Optional[str] = None, per_page: int = 20) -> str:
        """
        List issues from a GitLab repository.
        
        Args:
            project_id: GitLab project ID or namespace/project-name
            state: Issue state filter (opened/closed/all)
            labels: Comma-separated label names to filter by
            per_page: Results per page (max 100)
            
        Returns:
            JSON string with issue data wrapped in security tags
        """
        try:
            # Get GitLab token from environment
            gitlab_token = os.getenv('GITLAB_API_KEY')
            if not gitlab_token:
                return "<UNTRUSTED_CONTENT>Error: GITLAB_API_KEY environment variable not set</UNTRUSTED_CONTENT>"

            # Validate state parameter
            valid_states = ['opened', 'closed', 'all']
            if state not in valid_states:
                return f"<UNTRUSTED_CONTENT>Error: Invalid state '{state}'. Must be one of: {', '.join(valid_states)}</UNTRUSTED_CONTENT>"

            # Prepare headers
            headers = {
                'Authorization': f'Bearer {gitlab_token}',
                'Content-Type': 'application/json'
            }

            # Build API URL and parameters
            base_url = 'https://gitlab.com/api/v4'
            url = f"{base_url}/projects/{requests.utils.quote(str(project_id), safe='')}/issues"
            
            params = {
                'state': state,
                'per_page': min(per_page, 100),  # Ensure max 100 per page
                'page': 1,
                'sort': 'updated_desc'
            }
            
            if labels:
                params['labels'] = labels

            all_issues = []
            max_total_issues = 200
            page = 1
            
            # Fetch issues with pagination (up to 200 total)
            while len(all_issues) < max_total_issues:
                params['page'] = page
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                # Handle rate limiting
                if response.status_code == 429:
                    return "<UNTRUSTED_CONTENT>Error: GitLab API rate limit exceeded. Please try again later.</UNTRUSTED_CONTENT>"
                
                # Handle authentication errors
                if response.status_code == 401:
                    return "<UNTRUSTED_CONTENT>Error: Invalid GitLab token or insufficient permissions</UNTRUSTED_CONTENT>"
                
                # Handle not found errors
                if response.status_code == 404:
                    return f"<UNTRUSTED_CONTENT>Error: Project '{project_id}' not found or not accessible</UNTRUSTED_CONTENT>"
                
                # Handle other HTTP errors
                if response.status_code != 200:
                    return f"<UNTRUSTED_CONTENT>Error: GitLab API returned status {response.status_code}: {response.text}</UNTRUSTED_CONTENT>"
                
                issues = response.json()
                if not issues:  # No more issues
                    break
                    
                all_issues.extend(issues)
                
                # Check if we've reached the limit or if this was the last page
                if len(issues) < per_page or len(all_issues) >= max_total_issues:
                    break
                    
                page += 1

            # Limit to max 200 issues
            all_issues = all_issues[:max_total_issues]

            # Process and filter issue data
            filtered_issues = []
            for issue in all_issues:
                try:
                    # Extract safe, non-sensitive information
                    safe_issue = {
                        'id': issue.get('id'),
                        'iid': issue.get('iid'),
                        'title': self._sanitize_text(issue.get('title', '')),
                        'description': self._sanitize_text(issue.get('description', '')[:500]) if issue.get('description') else '',
                        'state': issue.get('state'),
                        'labels': [self._sanitize_text(str(label)) for label in issue.get('labels', [])],
                        'author': {
                            'name': self._sanitize_text(issue.get('author', {}).get('name', 'Unknown')),
                            'username': self._sanitize_text(issue.get('author', {}).get('username', 'unknown'))
                        } if issue.get('author') else {'name': 'Unknown', 'username': 'unknown'},
                        'created_at': issue.get('created_at'),
                        'updated_at': issue.get('updated_at'),
                        'web_url': issue.get('web_url')
                    }
                    filtered_issues.append(safe_issue)
                except Exception as e:
                    # Skip malformed issues
                    continue

            # Generate summary statistics
            stats = self._generate_stats(filtered_issues)
            
            # Prepare final output
            result = {
                'project_id': project_id,
                'total_fetched': len(filtered_issues),
                'max_limit_reached': len(all_issues) >= max_total_issues,
                'summary_stats': stats,
                'issues': filtered_issues
            }

            return f"<UNTRUSTED_CONTENT>{json.dumps(result, indent=2, ensure_ascii=False)}</UNTRUSTED_CONTENT>"

        except requests.exceptions.Timeout:
            return "<UNTRUSTED_CONTENT>Error: Request timed out. GitLab API may be slow or unavailable.</UNTRUSTED_CONTENT>"
        except requests.exceptions.ConnectionError:
            return "<UNTRUSTED_CONTENT>Error: Could not connect to GitLab API. Check your internet connection.</UNTRUSTED_CONTENT>"
        except requests.exceptions.RequestException as e:
            return f"<UNTRUSTED_CONTENT>Error: Request failed - {str(e)}</UNTRUSTED_CONTENT>"
        except Exception as e:
            return f"<UNTRUSTED_CONTENT>Error: Unexpected error occurred - {str(e)}</UNTRUSTED_CONTENT>"

    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text by removing potentially sensitive information.
        
        Args:
            text: Input text to sanitize
            
        Returns:
            Sanitized text
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Basic sanitization - remove common sensitive patterns
        import re
        
        # Remove potential tokens, keys, passwords
        sensitive_patterns = [
            r'[a-zA-Z0-9]{20,}',  # Long alphanumeric strings that might be tokens
            r'password[s]?\s*[:=]\s*\S+',
            r'token[s]?\s*[:=]\s*\S+',
            r'key[s]?\s*[:=]\s*\S+',
            r'secret[s]?\s*[:=]\s*\S+',
        ]
        
        for pattern in sensitive_patterns:
            text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
        
        # Limit length to prevent extremely long descriptions
        return text[:1000] if len(text) > 1000 else text

    def _generate_stats(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for the issues.
        
        Args:
            issues: List of issue dictionaries
            
        Returns:
            Dictionary with summary statistics
        """
        if not issues:
            return {
                'total_issues': 0,
                'opened_count': 0,
                'closed_count': 0,
                'common_labels': []
            }

        opened_count = sum(1 for issue in issues if issue.get('state') == 'opened')
        closed_count = sum(1 for issue in issues if issue.get('state') == 'closed')
        
        # Count label frequency
        label_counts = {}
        for issue in issues:
            for label in issue.get('labels', []):
                label_counts[label] = label_counts.get(label, 0) + 1
        
        # Get top 10 most common labels
        common_labels = sorted(
            [(label, count) for label, count in label_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            'total_issues': len(issues),
            'opened_count': opened_count,
            'closed_count': closed_count,
            'common_labels': [{'label': label, 'count': count} for label, count in common_labels]
        }