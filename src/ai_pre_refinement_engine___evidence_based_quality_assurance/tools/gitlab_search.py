from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import os

class GitLabSearchInput(BaseModel):
    """Input schema for GitLab Search Tool."""
    scope: str = Field(
        description="Search scope: 'global', 'group', or 'project'",
        pattern="^(global|group|project)$"
    )
    query: str = Field(description="Search query string")
    search_type: str = Field(
        description="Type of content to search: 'code', 'issues', 'merge_requests', 'commits', 'blobs', 'wiki_blobs', 'milestones', 'projects', or 'users'",
        pattern="^(code|issues|merge_requests|commits|blobs|wiki_blobs|milestones|projects|users)$"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="GitLab project ID (required when scope is 'project')"
    )
    group_id: Optional[str] = Field(
        default=None, 
        description="GitLab group ID (required when scope is 'group')"
    )

class GitLabSearchTool(BaseTool):
    """Tool for searching GitLab repositories, issues, merge requests and other content using GitLab REST API."""

    name: str = "gitlab_search"
    description: str = (
        "Search GitLab content across different scopes (global, group, project) for various types including "
        "code, issues, merge requests, commits, blobs, wiki pages, milestones, projects, and users. "
        "Handles pagination and returns comprehensive results with metadata. Requires GITLAB_API_KEY environment variable."
    )
    args_schema: Type[BaseModel] = GitLabSearchInput

    def _run(
        self, 
        scope: str, 
        query: str, 
        search_type: str, 
        project_id: Optional[str] = None, 
        group_id: Optional[str] = None
    ) -> str:
        try:
            # Get API key from environment
            api_key = os.getenv('GITLAB_API_KEY')
            if not api_key:
                return json.dumps({
                    "success": False,
                    "error": "GITLAB_API_KEY environment variable not found",
                    "results": []
                })

            # Set up headers
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # Determine base URL - defaulting to gitlab.com
            base_url = os.getenv('GITLAB_BASE_URL', 'https://gitlab.com')
            
            # Build API endpoint based on scope
            if scope == "global":
                endpoint = f"{base_url}/api/v4/search"
            elif scope == "group":
                if not group_id:
                    return json.dumps({
                        "success": False,
                        "error": "group_id is required when scope is 'group'",
                        "results": []
                    })
                endpoint = f"{base_url}/api/v4/groups/{group_id}/search"
            elif scope == "project":
                if not project_id:
                    return json.dumps({
                        "success": False,
                        "error": "project_id is required when scope is 'project'",
                        "results": []
                    })
                endpoint = f"{base_url}/api/v4/projects/{project_id}/search"
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid scope: {scope}. Must be 'global', 'group', or 'project'",
                    "results": []
                })

            # Prepare query parameters
            params = {
                'scope': search_type,
                'search': query,
                'per_page': 100,  # Maximum per page
                'page': 1
            }

            all_results = []
            page = 1
            total_pages = 1
            
            # Handle pagination
            while page <= total_pages:
                params['page'] = page
                
                try:
                    response = requests.get(endpoint, headers=headers, params=params, timeout=30)
                    
                    if response.status_code == 401:
                        return json.dumps({
                            "success": False,
                            "error": "Authentication failed. Check your GITLAB_API_KEY",
                            "results": []
                        })
                    elif response.status_code == 403:
                        return json.dumps({
                            "success": False,
                            "error": "Access forbidden. Check permissions for the specified scope",
                            "results": []
                        })
                    elif response.status_code == 404:
                        return json.dumps({
                            "success": False,
                            "error": f"Resource not found. Check if {scope} ID exists and is accessible",
                            "results": []
                        })
                    elif response.status_code == 422:
                        return json.dumps({
                            "success": False,
                            "error": f"Search type '{search_type}' may not be available for scope '{scope}'. Try a different search type.",
                            "results": [],
                            "fallback_info": {
                                "available_types": ["code", "issues", "merge_requests", "commits"],
                                "note": "Some search types are only available in certain scopes"
                            }
                        })
                    elif response.status_code != 200:
                        return json.dumps({
                            "success": False,
                            "error": f"GitLab API error: {response.status_code} - {response.text}",
                            "results": []
                        })

                    # Parse response
                    results = response.json()
                    
                    # Add results to our collection
                    all_results.extend(results)
                    
                    # Check pagination headers
                    total_pages = int(response.headers.get('X-Total-Pages', 1))
                    current_page = int(response.headers.get('X-Page', page))
                    
                    # Break if we've processed all pages or if no more results
                    if current_page >= total_pages or len(results) == 0:
                        break
                        
                    page += 1
                    
                except requests.exceptions.Timeout:
                    return json.dumps({
                        "success": False,
                        "error": "Request timeout. GitLab API may be slow or unavailable",
                        "results": all_results if all_results else []
                    })
                except requests.exceptions.ConnectionError:
                    return json.dumps({
                        "success": False,
                        "error": "Connection error. Check your internet connection and GitLab URL",
                        "results": all_results if all_results else []
                    })

            # Process results to add relevant metadata
            processed_results = []
            for result in all_results:
                processed_result = {
                    "id": result.get("id"),
                    "title": result.get("title") or result.get("filename") or result.get("name"),
                    "description": result.get("description"),
                    "web_url": result.get("web_url"),
                    "created_at": result.get("created_at"),
                    "updated_at": result.get("updated_at"),
                }
                
                # Add type-specific metadata
                if search_type in ["code", "blobs", "wiki_blobs"]:
                    processed_result.update({
                        "filename": result.get("filename"),
                        "path": result.get("path"),
                        "ref": result.get("ref", "main"),
                        "project_id": result.get("project_id")
                    })
                elif search_type == "issues":
                    processed_result.update({
                        "state": result.get("state"),
                        "labels": result.get("labels", []),
                        "assignees": result.get("assignees", []),
                        "milestone": result.get("milestone"),
                        "project_id": result.get("project_id")
                    })
                elif search_type == "merge_requests":
                    processed_result.update({
                        "state": result.get("state"),
                        "source_branch": result.get("source_branch"),
                        "target_branch": result.get("target_branch"),
                        "author": result.get("author"),
                        "project_id": result.get("project_id")
                    })
                elif search_type == "commits":
                    processed_result.update({
                        "sha": result.get("id"),
                        "short_id": result.get("short_id"),
                        "author_name": result.get("author_name"),
                        "author_email": result.get("author_email"),
                        "message": result.get("message"),
                        "project_id": result.get("project_id")
                    })
                elif search_type == "projects":
                    processed_result.update({
                        "path": result.get("path"),
                        "path_with_namespace": result.get("path_with_namespace"),
                        "visibility": result.get("visibility"),
                        "default_branch": result.get("default_branch"),
                        "namespace": result.get("namespace")
                    })
                elif search_type == "users":
                    processed_result.update({
                        "username": result.get("username"),
                        "name": result.get("name"),
                        "avatar_url": result.get("avatar_url"),
                        "state": result.get("state")
                    })

                processed_results.append(processed_result)

            return json.dumps({
                "success": True,
                "query": query,
                "scope": scope,
                "search_type": search_type,
                "total_results": len(processed_results),
                "results": processed_results,
                "metadata": {
                    "project_id": project_id,
                    "group_id": group_id,
                    "pages_fetched": page - 1 if page > 1 else 1
                }
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "results": []
            })