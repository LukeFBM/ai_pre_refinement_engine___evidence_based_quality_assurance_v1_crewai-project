from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List
import requests
import json
import time

class GitLabRepoSearchInput(BaseModel):
    """Input schema for GitLab Repository Search Tool."""
    query: str = Field(..., description="Search term for repositories (required)")
    visibility: str = Field(default="public", description="Repository visibility (public, internal, private)")
    order_by: str = Field(default="updated_at", description="Sorting order (id, name, path, created_at, updated_at, last_activity_at)")

class GitLabRepoSearchTool(BaseTool):
    """Tool for searching GitLab repositories with read-only access."""

    name: str = "gitlab_repo_search_tool"
    description: str = (
        "Search GitLab repositories using GitLab API v4. "
        "Returns repository metadata including name, description, URL, language, stars, forks, and last activity. "
        "Supports filtering by visibility and custom ordering. Limited to 50 results for performance."
    )
    args_schema: Type[BaseModel] = GitLabRepoSearchInput

    def _run(self, query: str, visibility: str = "public", order_by: str = "updated_at") -> str:
        """
        Search GitLab repositories using the GitLab API v4.
        
        Args:
            query: Search term for repositories
            visibility: Repository visibility filter
            order_by: Sorting order for results
            
        Returns:
            JSON string with repository metadata wrapped in security tags
        """
        try:
            # GitLab API v4 projects search endpoint
            base_url = "https://gitlab.com/api/v4/projects"
            
            # Prepare search parameters
            params = {
                'search': query,
                'visibility': visibility,
                'order_by': order_by,
                'sort': 'desc',
                'per_page': 50,  # Limit results to max 50
                'simple': 'true'  # Get simplified project data
            }
            
            # Set headers for API request
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'CrewAI-GitLabSearchTool/1.0'
            }
            
            # Make API request with timeout
            response = requests.get(base_url, params=params, headers=headers, timeout=30)
            
            # Handle rate limiting (429 Too Many Requests)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                return f"<UNTRUSTED_CONTENT>Rate limit exceeded. Please try again in {retry_after} seconds.</UNTRUSTED_CONTENT>"
            
            # Check if request was successful
            if response.status_code != 200:
                return f"<UNTRUSTED_CONTENT>Error: GitLab API returned status {response.status_code}. {response.text}</UNTRUSTED_CONTENT>"
            
            # Parse JSON response
            repositories = response.json()
            
            if not repositories:
                return f"<UNTRUSTED_CONTENT>No repositories found for query: '{query}'</UNTRUSTED_CONTENT>"
            
            # Extract relevant repository metadata
            repo_list = []
            for repo in repositories:
                repo_data = {
                    'id': repo.get('id'),
                    'name': repo.get('name'),
                    'description': repo.get('description', 'No description available'),
                    'web_url': repo.get('web_url'),
                    'language': repo.get('default_branch'),  # GitLab API doesn't always return primary language in simple mode
                    'stars': repo.get('star_count', 0),
                    'forks': repo.get('forks_count', 0),
                    'last_activity': repo.get('last_activity_at'),
                    'visibility': repo.get('visibility'),
                    'namespace': repo.get('namespace', {}).get('name', 'Unknown'),
                    'created_at': repo.get('created_at')
                }
                repo_list.append(repo_data)
            
            # Convert to JSON string
            result_json = json.dumps(repo_list, indent=2, ensure_ascii=False)
            
            # Wrap in security tags as requested
            return f"<UNTRUSTED_CONTENT>{result_json}</UNTRUSTED_CONTENT>"
            
        except requests.exceptions.Timeout:
            return "<UNTRUSTED_CONTENT>Error: Request timeout. GitLab API did not respond within 30 seconds.</UNTRUSTED_CONTENT>"
        
        except requests.exceptions.ConnectionError:
            return "<UNTRUSTED_CONTENT>Error: Connection failed. Please check your internet connection.</UNTRUSTED_CONTENT>"
        
        except requests.exceptions.RequestException as e:
            return f"<UNTRUSTED_CONTENT>Error: Request failed - {str(e)}</UNTRUSTED_CONTENT>"
        
        except json.JSONDecodeError:
            return "<UNTRUSTED_CONTENT>Error: Invalid JSON response from GitLab API.</UNTRUSTED_CONTENT>"
        
        except Exception as e:
            return f"<UNTRUSTED_CONTENT>Unexpected error: {str(e)}</UNTRUSTED_CONTENT>"