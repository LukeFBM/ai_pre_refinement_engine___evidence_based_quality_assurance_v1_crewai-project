from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, Dict, Any, List
import requests
import json
import re
import os
from urllib.parse import urlencode

class GitLabListIssuesInput(BaseModel):
    """Input schema for GitLab List Issues Tool."""
    project_id: int = Field(..., description="The GitLab project ID")
    query: Optional[str] = Field(None, description="Optional search/filter string (e.g., 'state:opened author:username label:bug')")

class GitLabListIssuesTool(BaseTool):
    """Tool for listing issues from a GitLab project with comprehensive filtering and pagination support."""

    name: str = "gitlab_list_issues"
    description: str = (
        "Lists issues from a GitLab project with advanced filtering capabilities. "
        "Supports filtering by state (opened/closed), author, assignee, label, milestone, and type. "
        "Query format: 'state:opened author:username assignee:user label:bug milestone:v1.0 type:issue'. "
        "Returns comprehensive issue information with pagination support."
    )
    args_schema: Type[BaseModel] = GitLabListIssuesInput

    def _parse_query_filters(self, query: str) -> Dict[str, Any]:
        """Parse the query string to extract GitLab API filters."""
        filters = {}
        
        if not query:
            return filters
        
        # Define filter patterns
        filter_patterns = {
            'state': r'state:(\w+)',
            'author_username': r'author:([^\s]+)',
            'assignee_username': r'assignee:([^\s]+)',
            'labels': r'label:([^\s,]+)',
            'milestone': r'milestone:([^\s]+)',
            'issue_type': r'type:(\w+)',
            'search': r'search:([^\s]+)',
            'scope': r'scope:(\w+)'
        }
        
        # Extract filters using regex
        for filter_name, pattern in filter_patterns.items():
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                if filter_name == 'labels':
                    # Handle multiple labels
                    filters[filter_name] = ','.join(matches)
                else:
                    # Take the last match for single-value filters
                    filters[filter_name] = matches[-1]
        
        # Handle free text search (anything not matching specific patterns)
        search_text = re.sub(r'\w+:[^\s]+', '', query).strip()
        if search_text and 'search' not in filters:
            filters['search'] = search_text
        
        return filters

    def _build_api_params(self, filters: Dict[str, Any], page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        """Build API parameters from filters."""
        params = {
            'page': page,
            'per_page': per_page,
            'order_by': 'updated_at',
            'sort': 'desc'
        }
        
        # Map filters to GitLab API parameters
        if 'state' in filters:
            params['state'] = filters['state']
        if 'author_username' in filters:
            params['author_username'] = filters['author_username']
        if 'assignee_username' in filters:
            params['assignee_username'] = filters['assignee_username']
        if 'labels' in filters:
            params['labels'] = filters['labels']
        if 'milestone' in filters:
            params['milestone'] = filters['milestone']
        if 'issue_type' in filters:
            params['issue_type'] = filters['issue_type']
        if 'search' in filters:
            params['search'] = filters['search']
        if 'scope' in filters:
            params['scope'] = filters['scope']
        
        return params

    def _format_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Format issue data for consistent output."""
        return {
            'id': issue.get('id'),
            'iid': issue.get('iid'),
            'title': issue.get('title', ''),
            'description': issue.get('description', ''),
            'state': issue.get('state', ''),
            'author': {
                'id': issue.get('author', {}).get('id'),
                'name': issue.get('author', {}).get('name'),
                'username': issue.get('author', {}).get('username')
            } if issue.get('author') else None,
            'assignee': {
                'id': issue.get('assignee', {}).get('id'),
                'name': issue.get('assignee', {}).get('name'),
                'username': issue.get('assignee', {}).get('username')
            } if issue.get('assignee') else None,
            'assignees': [
                {
                    'id': assignee.get('id'),
                    'name': assignee.get('name'),
                    'username': assignee.get('username')
                } for assignee in issue.get('assignees', [])
            ],
            'created_at': issue.get('created_at'),
            'updated_at': issue.get('updated_at'),
            'closed_at': issue.get('closed_at'),
            'web_url': issue.get('web_url'),
            'labels': issue.get('labels', []),
            'milestone': {
                'id': issue.get('milestone', {}).get('id'),
                'title': issue.get('milestone', {}).get('title'),
                'description': issue.get('milestone', {}).get('description'),
                'state': issue.get('milestone', {}).get('state'),
                'web_url': issue.get('milestone', {}).get('web_url')
            } if issue.get('milestone') else None,
            'issue_type': issue.get('issue_type', 'issue'),
            'severity': issue.get('severity'),
            'priority': issue.get('priority'),
            'confidential': issue.get('confidential', False),
            'discussion_locked': issue.get('discussion_locked', False),
            'upvotes': issue.get('upvotes', 0),
            'downvotes': issue.get('downvotes', 0),
            'user_notes_count': issue.get('user_notes_count', 0),
            'due_date': issue.get('due_date'),
            'time_stats': issue.get('time_stats', {}),
            'has_tasks': issue.get('has_tasks', False),
            'task_status': issue.get('task_status'),
            '_links': issue.get('_links', {})
        }

    def _run(self, project_id: int, query: Optional[str] = None) -> str:
        """Execute the GitLab list issues operation."""
        try:
            # Get API key from environment
            api_key = os.getenv('GITLAB_API_KEY')
            if not api_key:
                return json.dumps({
                    'success': False,
                    'error': 'GITLAB_API_KEY environment variable is required',
                    'issues': [],
                    'metadata': {}
                })

            # Parse query filters
            filters = self._parse_query_filters(query or '')
            
            # Setup headers
            headers = {
                'PRIVATE-TOKEN': api_key,
                'Content-Type': 'application/json'
            }

            # Initialize pagination variables
            all_issues = []
            page = 1
            per_page = 100
            total_pages = 1

            # Fetch all pages
            while page <= total_pages:
                # Build API parameters
                params = self._build_api_params(filters, page, per_page)
                
                # Make API request
                url = f"https://gitlab.com/api/v4/projects/{project_id}/issues"
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    issues = response.json()
                    all_issues.extend(issues)
                    
                    # Get pagination info from headers
                    total_pages = int(response.headers.get('X-Total-Pages', 1))
                    total_count = int(response.headers.get('X-Total', len(issues)))
                    
                    # If no more issues, break
                    if len(issues) < per_page:
                        break
                        
                    page += 1
                    
                elif response.status_code == 404:
                    return json.dumps({
                        'success': False,
                        'error': f'Project with ID {project_id} not found or access denied',
                        'issues': [],
                        'metadata': {
                            'project_id': project_id,
                            'applied_filters': filters,
                            'total_count': 0,
                            'page_count': 0
                        }
                    })
                elif response.status_code == 401:
                    return json.dumps({
                        'success': False,
                        'error': 'Invalid or expired GitLab API key',
                        'issues': [],
                        'metadata': {}
                    })
                elif response.status_code == 403:
                    return json.dumps({
                        'success': False,
                        'error': f'Access denied to project {project_id}. Check project visibility and permissions.',
                        'issues': [],
                        'metadata': {}
                    })
                else:
                    return json.dumps({
                        'success': False,
                        'error': f'GitLab API error: {response.status_code} - {response.text}',
                        'issues': [],
                        'metadata': {}
                    })

            # Format issues
            formatted_issues = [self._format_issue(issue) for issue in all_issues]
            
            # Build metadata
            metadata = {
                'project_id': project_id,
                'applied_filters': filters,
                'original_query': query,
                'total_count': len(formatted_issues),
                'page_count': total_pages,
                'per_page': per_page,
                'api_endpoint': f'/api/v4/projects/{project_id}/issues'
            }

            return json.dumps({
                'success': True,
                'issues': formatted_issues,
                'metadata': metadata
            }, indent=2)

        except requests.exceptions.Timeout:
            return json.dumps({
                'success': False,
                'error': 'Request timeout - GitLab API took too long to respond',
                'issues': [],
                'metadata': {}
            })
        except requests.exceptions.ConnectionError:
            return json.dumps({
                'success': False,
                'error': 'Connection error - Unable to reach GitLab API',
                'issues': [],
                'metadata': {}
            })
        except Exception as e:
            return json.dumps({
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'issues': [],
                'metadata': {}
            })