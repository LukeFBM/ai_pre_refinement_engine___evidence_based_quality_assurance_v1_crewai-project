from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import os
from datetime import datetime

class GitLabMRListRequest(BaseModel):
    """Input schema for GitLab MR List Tool."""
    project_id: str = Field(
        ..., 
        description="GitLab project ID (numeric) or namespace/project-name format"
    )
    state: str = Field(
        default="opened",
        description="MR state filter: opened, closed, merged, or all (default: opened)"
    )
    per_page: int = Field(
        default=20,
        description="Results per page, maximum 100 (default: 20)",
        ge=1,
        le=100
    )

class GitLabMRListTool(BaseTool):
    """Tool for listing GitLab merge requests in read-only mode with security filtering."""

    name: str = "gitlab_mr_list_tool"
    description: str = (
        "Lists merge requests from GitLab repositories in read-only mode. "
        "Fetches MR metadata including title, description, state, branches, "
        "author, and timestamps. Provides summary statistics and filters "
        "sensitive information for safe context gathering."
    )
    args_schema: Type[BaseModel] = GitLabMRListRequest

    def _run(self, project_id: str, state: str = "opened", per_page: int = 20) -> str:
        """
        Fetch merge requests from GitLab API with security filtering.
        
        Args:
            project_id: GitLab project ID or namespace/project-name
            state: MR state filter (opened/closed/merged/all)
            per_page: Results per page (1-100)
            
        Returns:
            JSON string with filtered MR data and summary statistics
        """
        try:
            # Get GitLab token from environment
            gitlab_token = os.getenv('GITLAB_API_TKN')
            if not gitlab_token:
                return "<UNTRUSTED_CONTENT>Error: GITLAB_API_TKN environment variable not set</UNTRUSTED_CONTENT>"

            # Validate state parameter
            valid_states = ['opened', 'closed', 'merged', 'all']
            if state not in valid_states:
                return f"<UNTRUSTED_CONTENT>Error: Invalid state '{state}'. Must be one of: {', '.join(valid_states)}</UNTRUSTED_CONTENT>"

            # Setup API headers
            headers = {
                'Authorization': f'Bearer {gitlab_token}',
                'Content-Type': 'application/json'
            }

            # URL encode project_id if it contains special characters
            if '/' in project_id:
                project_id = requests.utils.quote(project_id, safe='')

            # Base GitLab API URL
            base_url = "https://gitlab.com/api/v4"
            
            # Build API endpoint
            endpoint = f"{base_url}/projects/{project_id}/merge_requests"
            
            # Setup parameters
            params = {
                'per_page': min(per_page, 100),  # Enforce max limit
                'page': 1
            }
            
            # Add state filter if not 'all'
            if state != 'all':
                params['state'] = state

            all_mrs = []
            page = 1
            max_pages = 10  # Limit to ~200 MRs (20 per page * 10 pages max)
            
            while page <= max_pages:
                params['page'] = page
                
                # Make API request
                response = requests.get(endpoint, headers=headers, params=params, timeout=30)
                
                # Handle rate limiting
                if response.status_code == 429:
                    return "<UNTRUSTED_CONTENT>Error: GitLab API rate limit exceeded. Please try again later.</UNTRUSTED_CONTENT>"
                
                # Handle authentication errors
                if response.status_code == 401:
                    return "<UNTRUSTED_CONTENT>Error: Invalid GitLab token or insufficient permissions</UNTRUSTED_CONTENT>"
                
                # Handle project not found
                if response.status_code == 404:
                    return f"<UNTRUSTED_CONTENT>Error: Project '{project_id}' not found or not accessible</UNTRUSTED_CONTENT>"
                
                # Handle other errors
                if response.status_code != 200:
                    return f"<UNTRUSTED_CONTENT>Error: GitLab API returned status {response.status_code}</UNTRUSTED_CONTENT>"
                
                page_data = response.json()
                
                # Break if no more results
                if not page_data:
                    break
                
                all_mrs.extend(page_data)
                
                # Check if this is the last page
                total_pages = int(response.headers.get('X-Total-Pages', 1))
                if page >= total_pages or page >= max_pages:
                    break
                
                page += 1

            # Filter and sanitize MR data
            filtered_mrs = []
            for mr in all_mrs:
                try:
                    # Extract safe, non-sensitive information
                    filtered_mr = {
                        'id': mr.get('id'),
                        'iid': mr.get('iid'),
                        'title': self._sanitize_text(mr.get('title', '')),
                        'description': self._sanitize_text(mr.get('description', '')[:500]),  # Limit description length
                        'state': mr.get('state'),
                        'source_branch': self._sanitize_branch_name(mr.get('source_branch', '')),
                        'target_branch': self._sanitize_branch_name(mr.get('target_branch', '')),
                        'author': {
                            'name': self._sanitize_text(mr.get('author', {}).get('name', 'Unknown')),
                            'username': self._sanitize_text(mr.get('author', {}).get('username', 'unknown'))
                        },
                        'created_at': mr.get('created_at'),
                        'updated_at': mr.get('updated_at'),
                        'merge_status': mr.get('merge_status'),
                        'draft': mr.get('draft', False),
                        'work_in_progress': mr.get('work_in_progress', False)
                    }
                    filtered_mrs.append(filtered_mr)
                except Exception as e:
                    continue  # Skip problematic MRs

            # Generate summary statistics
            summary = self._generate_summary(filtered_mrs)
            
            # Prepare final result
            result = {
                'summary': summary,
                'merge_requests': filtered_mrs,
                'metadata': {
                    'total_fetched': len(filtered_mrs),
                    'max_results_reached': len(all_mrs) >= (max_pages * per_page),
                    'project_id': project_id,
                    'filter_state': state,
                    'fetched_at': datetime.utcnow().isoformat()
                }
            }

            return f"<UNTRUSTED_CONTENT>{json.dumps(result, indent=2, ensure_ascii=False)}</UNTRUSTED_CONTENT>"

        except requests.exceptions.Timeout:
            return "<UNTRUSTED_CONTENT>Error: Request timeout - GitLab API did not respond in time</UNTRUSTED_CONTENT>"
        except requests.exceptions.ConnectionError:
            return "<UNTRUSTED_CONTENT>Error: Connection error - Unable to reach GitLab API</UNTRUSTED_CONTENT>"
        except requests.exceptions.RequestException as e:
            return f"<UNTRUSTED_CONTENT>Error: Request failed - {str(e)}</UNTRUSTED_CONTENT>"
        except Exception as e:
            return f"<UNTRUSTED_CONTENT>Error: Unexpected error occurred - {str(e)}</UNTRUSTED_CONTENT>"

    def _sanitize_text(self, text: str) -> str:
        """Remove or mask potentially sensitive information from text."""
        if not isinstance(text, str):
            return str(text)
        
        # Remove common sensitive patterns
        import re
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Remove potential tokens/keys (sequences of alphanumeric characters longer than 20)
        text = re.sub(r'\b[A-Za-z0-9]{20,}\b', '[REDACTED]', text)
        
        # Remove URLs with tokens/secrets
        text = re.sub(r'https?://[^\s]*[?&](token|key|secret|password)=[^\s&]*', '[URL_WITH_CREDENTIALS]', text)
        
        # Limit length to prevent extremely long content
        if len(text) > 1000:
            text = text[:1000] + "... [TRUNCATED]"
        
        return text.strip()

    def _sanitize_branch_name(self, branch_name: str) -> str:
        """Sanitize branch names to remove potentially sensitive information."""
        if not isinstance(branch_name, str):
            return str(branch_name)
        
        # Remove common sensitive patterns from branch names
        import re
        
        # Remove tokens/hashes that might be in branch names
        branch_name = re.sub(r'\b[A-Za-z0-9]{20,}\b', '[HASH]', branch_name)
        
        return branch_name.strip()

    def _generate_summary(self, mrs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics for the MR list."""
        if not mrs:
            return {
                'total_mrs': 0,
                'state_distribution': {},
                'common_patterns': {}
            }

        # State distribution
        state_counts = {}
        author_counts = {}
        source_branch_patterns = {}
        target_branch_patterns = {}
        
        for mr in mrs:
            # Count states
            state = mr.get('state', 'unknown')
            state_counts[state] = state_counts.get(state, 0) + 1
            
            # Count authors
            author = mr.get('author', {}).get('username', 'unknown')
            author_counts[author] = author_counts.get(author, 0) + 1
            
            # Analyze branch patterns
            source_branch = mr.get('source_branch', '')
            target_branch = mr.get('target_branch', '')
            
            # Common source branch prefixes
            if '/' in source_branch:
                prefix = source_branch.split('/')[0]
                source_branch_patterns[prefix] = source_branch_patterns.get(prefix, 0) + 1
            
            # Target branches
            if target_branch:
                target_branch_patterns[target_branch] = target_branch_patterns.get(target_branch, 0) + 1

        # Get top contributors (limit for security)
        top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Get common target branches
        top_targets = sorted(target_branch_patterns.items(), key=lambda x: x[1], reverse=True)[:3]
        
        summary = {
            'total_mrs': len(mrs),
            'state_distribution': state_counts,
            'common_patterns': {
                'top_contributors': [{'username': author, 'mr_count': count} for author, count in top_authors],
                'common_target_branches': [{'branch': branch, 'count': count} for branch, count in top_targets],
                'source_branch_prefixes': dict(sorted(source_branch_patterns.items(), key=lambda x: x[1], reverse=True)[:5])
            }
        }
        
        return summary