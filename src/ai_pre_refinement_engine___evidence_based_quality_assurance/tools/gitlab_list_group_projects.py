from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, List, Dict, Any
import requests
import json


class GitLabListGroupProjectsInput(BaseModel):
    """Input schema for GitLab List Group Projects Tool."""
    group_id: Optional[int] = Field(None, description="The ID of the GitLab group")
    group_path: Optional[str] = Field(None, description="The path of the GitLab group")


class GitLabListGroupProjectsTool(BaseTool):
    """Tool for listing projects in a GitLab group."""

    name: str = "gitlab_list_group_projects"
    description: str = (
        "Lists all projects in a GitLab group. Accepts either group_id (integer) or group_path (string). "
        "Returns project information including ID, name, path, web_url, default_branch, and description. "
        "Automatically handles pagination to fetch all projects."
    )
    args_schema: Type[BaseModel] = GitLabListGroupProjectsInput

    def _run(self, group_id: Optional[int] = None, group_path: Optional[str] = None) -> str:
        """
        List projects in a GitLab group.
        
        Args:
            group_id: The ID of the GitLab group
            group_path: The path of the GitLab group
            
        Returns:
            JSON string containing list of project dictionaries
        """
        try:
            # Validate input parameters
            if not group_id and not group_path:
                return json.dumps({
                    "error": "Either group_id or group_path must be provided"
                })
            
            if group_id and group_path:
                return json.dumps({
                    "error": "Provide either group_id or group_path, not both"
                })
            
            # Get GitLab API key from environment
            import os
            gitlab_api_key = os.getenv('GITLAB_API_KEY')
            if not gitlab_api_key:
                return json.dumps({
                    "error": "GITLAB_API_KEY environment variable is required"
                })
            
            # Determine which parameter to use
            if group_id is not None:
                group_identifier = str(group_id)
            else:
                group_identifier = group_path
            
            # Base URL and headers
            base_url = "https://gitlab.com/api/v4"
            headers = {
                "Authorization": f"Bearer {gitlab_api_key}",
                "Content-Type": "application/json"
            }
            
            # Collect all projects with pagination
            all_projects = []
            page = 1
            per_page = 100
            
            while True:
                # Make API request
                url = f"{base_url}/groups/{group_identifier}/projects"
                params = {
                    "page": page,
                    "per_page": per_page,
                    "simple": "false"  # Get full project details
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                # Handle API errors
                if response.status_code == 401:
                    return json.dumps({
                        "error": "Authentication failed. Check your GITLAB_API_KEY"
                    })
                elif response.status_code == 404:
                    return json.dumps({
                        "error": f"Group not found: {group_identifier}"
                    })
                elif response.status_code != 200:
                    return json.dumps({
                        "error": f"GitLab API error: {response.status_code} - {response.text}"
                    })
                
                # Parse response
                try:
                    projects = response.json()
                except ValueError as e:
                    return json.dumps({
                        "error": f"Failed to parse API response: {str(e)}"
                    })
                
                # If no projects returned, we've reached the end
                if not projects:
                    break
                
                # Extract relevant project information
                for project in projects:
                    project_info = {
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "path": project.get("path"),
                        "web_url": project.get("web_url"),
                        "default_branch": project.get("default_branch"),
                        "description": project.get("description")
                    }
                    all_projects.append(project_info)
                
                # Check if we got a full page (if less than per_page, we're done)
                if len(projects) < per_page:
                    break

                page += 1

                # Safety limit to prevent runaway pagination
                if page > 10:
                    break
            
            # Return results
            result = {
                "success": True,
                "group_identifier": group_identifier,
                "total_projects": len(all_projects),
                "projects": all_projects
            }
            
            return json.dumps(result, indent=2)
            
        except requests.exceptions.Timeout:
            return json.dumps({
                "error": "Request timeout. GitLab API took too long to respond"
            })
        except requests.exceptions.ConnectionError:
            return json.dumps({
                "error": "Connection error. Unable to reach GitLab API"
            })
        except requests.exceptions.RequestException as e:
            return json.dumps({
                "error": f"Request error: {str(e)}"
            })
        except Exception as e:
            return json.dumps({
                "error": f"Unexpected error: {str(e)}"
            })