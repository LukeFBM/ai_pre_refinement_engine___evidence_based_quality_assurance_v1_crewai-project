from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import os
import re
from urllib.parse import urlencode

class GitLabListMergeRequestsInput(BaseModel):
    """Input schema for GitLab List Merge Requests Tool."""
    project_id: int = Field(..., description="The GitLab project ID to list merge requests from")
    query: Optional[str] = Field(default="", description="Optional search/filter string. Supports filters like 'state:opened', 'author:username', 'assignee:username', 'label:bug', 'milestone:v1.0'")

class GitLabListMergeRequestsTool(BaseTool):
    """Tool for listing merge requests from GitLab projects with comprehensive filtering capabilities."""

    name: str = "gitlab_list_merge_requests"
    description: str = (
        "Lists merge requests from a GitLab project with advanced filtering options. "
        "Supports filtering by state (opened/closed/merged), author, assignee, label, and milestone. "
        "Handles pagination automatically and returns comprehensive merge request information including "
        "id, title, description, state, author, assignee, dates, URLs, and branch information. "
        "Use query parameter for filters like 'state:opened author:john label:bug'."
    )
    args_schema: Type[BaseModel] = GitLabListMergeRequestsInput

    def _parse_query_filters(self, query: str) -> Dict[str, Any]:
        """Parse query string to extract GitLab API filters."""
        filters = {}
        
        if not query:
            return filters
            
        # Define filter patterns
        filter_patterns = {
            r'state:(\w+)': 'state',
            r'author:([^\s]+)': 'author_username', 
            r'assignee:([^\s]+)': 'assignee_username',
            r'label:([^\s]+)': 'labels',
            r'milestone:([^\s]+)': 'milestone'
        }
        
        # Extract filters from query
        for pattern, param_name in filter_patterns.items():
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                if param_name == 'labels':
                    # Labels can be multiple, comma-separated
                    filters[param_name] = ','.join(matches)
                else:
                    # Take the last match for single-value filters
                    filters[param_name] = matches[-1]
        
        # Handle search terms (words not matching filter patterns)
        search_terms = re.sub(r'(?:state|author|assignee|label|milestone):[^\s]+', '', query, flags=re.IGNORECASE)
        search_terms = ' '.join(search_terms.split())
        if search_terms:
            filters['search'] = search_terms
            
        return filters

    def _get_merge_requests_page(self, base_url: str, headers: Dict[str, str], params: Dict[str, Any], page: int) -> tuple:
        """Get a single page of merge requests."""
        params['page'] = page
        params['per_page'] = 100  # Max per page
        
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            # Get pagination info from headers
            total_pages = int(response.headers.get('X-Total-Pages', 1))
            total_count = int(response.headers.get('X-Total', 0))
            
            return response.json(), total_pages, total_count, None
        except requests.exceptions.RequestException as e:
            return None, 0, 0, f"API request failed: {str(e)}"
        except ValueError as e:
            return None, 0, 0, f"Invalid JSON response: {str(e)}"

    def _format_merge_request(self, mr: Dict[str, Any]) -> Dict[str, Any]:
        """Format merge request data for output."""
        return {
            'id': mr.get('id'),
            'iid': mr.get('iid'),
            'title': mr.get('title'),
            'description': mr.get('description'),
            'state': mr.get('state'),
            'author': {
                'id': mr.get('author', {}).get('id'),
                'name': mr.get('author', {}).get('name'),
                'username': mr.get('author', {}).get('username')
            } if mr.get('author') else None,
            'assignee': {
                'id': mr.get('assignee', {}).get('id'),
                'name': mr.get('assignee', {}).get('name'),
                'username': mr.get('assignee', {}).get('username')
            } if mr.get('assignee') else None,
            'assignees': [
                {
                    'id': assignee.get('id'),
                    'name': assignee.get('name'),
                    'username': assignee.get('username')
                }
                for assignee in mr.get('assignees', [])
            ],
            'created_at': mr.get('created_at'),
            'updated_at': mr.get('updated_at'),
            'merged_at': mr.get('merged_at'),
            'web_url': mr.get('web_url'),
            'source_branch': mr.get('source_branch'),
            'target_branch': mr.get('target_branch'),
            'labels': mr.get('labels', []),
            'milestone': mr.get('milestone', {}).get('title') if mr.get('milestone') else None,
            'merge_status': mr.get('merge_status'),
            'has_conflicts': mr.get('has_conflicts'),
            'upvotes': mr.get('upvotes', 0),
            'downvotes': mr.get('downvotes', 0)
        }

    def _run(self, project_id: int, query: str = "") -> str:
        """Execute the GitLab list merge requests operation."""
        try:
            # Get GitLab API key from environment
            api_key = os.getenv('GITLAB_API_KEY')
            if not api_key:
                return json.dumps({
                    'success': False,
                    'error': 'GITLAB_API_KEY environment variable is required',
                    'merge_requests': [],
                    'metadata': {}
                })

            # Parse query filters
            filters = self._parse_query_filters(query)
            
            # Set up API request
            base_url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Prepare API parameters
            params = {
                'order_by': 'updated_at',
                'sort': 'desc'
            }
            params.update(filters)
            
            # Collect all merge requests with pagination
            all_merge_requests = []
            page = 1
            total_pages = 1
            total_count = 0
            
            while page <= total_pages:
                merge_requests_data, total_pages, total_count, error = self._get_merge_requests_page(
                    base_url, headers, params, page
                )
                
                if error:
                    return json.dumps({
                        'success': False,
                        'error': error,
                        'merge_requests': [],
                        'metadata': {}
                    })
                
                if merge_requests_data:
                    # Format merge requests
                    formatted_mrs = [self._format_merge_request(mr) for mr in merge_requests_data]
                    all_merge_requests.extend(formatted_mrs)
                
                page += 1
                
                # Safety break to prevent infinite loops
                if page > 5:  # Max 500 merge requests
                    break
            
            # Prepare metadata
            metadata = {
                'total_count': total_count,
                'returned_count': len(all_merge_requests),
                'project_id': project_id,
                'applied_filters': filters,
                'query': query
            }
            
            return json.dumps({
                'success': True,
                'merge_requests': all_merge_requests,
                'metadata': metadata
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'merge_requests': [],
                'metadata': {}
            })