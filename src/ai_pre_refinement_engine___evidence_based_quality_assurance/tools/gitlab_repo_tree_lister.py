from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import os

class GitLabRepoTreeRequest(BaseModel):
    """Input schema for GitLab Repository Tree Lister Tool."""
    project_id: int = Field(..., description="The GitLab project ID")
    path: str = Field(default="/", description="Path within the repository (default: '/')")
    ref: str = Field(default="main", description="Branch or tag name (default: 'main')")
    recursive: bool = Field(default=False, description="Whether to list recursively (default: False)")

class GitLabRepoTreeListerTool(BaseTool):
    """Tool for listing GitLab repository tree structure with pagination support."""

    name: str = "gitlab_repo_tree_lister"
    description: str = (
        "Lists repository tree structure from GitLab using REST API. "
        "Supports pagination, recursive listing, and returns comprehensive "
        "file/directory information including id, name, type, path, and mode."
    )
    args_schema: Type[BaseModel] = GitLabRepoTreeRequest

    def _run(self, project_id: int, path: str = "/", ref: str = "main", recursive: bool = False) -> str:
        """
        Lists GitLab repository tree structure with pagination support.
        
        Args:
            project_id: The GitLab project ID
            path: Path within the repository
            ref: Branch or tag name
            recursive: Whether to list recursively
            
        Returns:
            JSON string with repository tree information
        """
        try:
            # Get GitLab API key from environment
            api_key = os.getenv("GITLAB_API_KEY")
            if not api_key:
                return json.dumps({
                    "success": False,
                    "error": "GITLAB_API_KEY environment variable is required",
                    "tree_items": [],
                    "metadata": {
                        "total_items": 0,
                        "project_id": project_id,
                        "path": path,
                        "ref": ref
                    }
                })

            # Prepare headers
            headers = {
                "PRIVATE-TOKEN": api_key,
                "Content-Type": "application/json"
            }

            # Build API URL - using gitlab.com as default, can be customized
            base_url = os.getenv("GITLAB_BASE_URL", "https://gitlab.com")
            api_url = f"{base_url}/api/v4/projects/{project_id}/repository/tree"
            
            # Prepare parameters
            params = {
                "ref": ref,
                "per_page": 100,  # Maximum items per page
                "page": 1
            }
            
            # Add path if not root
            if path and path != "/":
                params["path"] = path.strip("/")
            
            # Add recursive parameter if requested
            if recursive:
                params["recursive"] = "true"

            all_items = []
            total_pages = 1
            current_page = 1

            # Handle pagination
            while current_page <= total_pages:
                params["page"] = current_page
                
                try:
                    response = requests.get(api_url, headers=headers, params=params, timeout=30)
                    
                    if response.status_code == 401:
                        return json.dumps({
                            "success": False,
                            "error": "Authentication failed. Check your GITLAB_API_KEY",
                            "tree_items": [],
                            "metadata": {
                                "total_items": 0,
                                "project_id": project_id,
                                "path": path,
                                "ref": ref
                            }
                        })
                    
                    elif response.status_code == 404:
                        return json.dumps({
                            "success": False,
                            "error": f"Project {project_id}, path '{path}', or ref '{ref}' not found",
                            "tree_items": [],
                            "metadata": {
                                "total_items": 0,
                                "project_id": project_id,
                                "path": path,
                                "ref": ref
                            }
                        })
                    
                    elif response.status_code != 200:
                        return json.dumps({
                            "success": False,
                            "error": f"GitLab API error: {response.status_code} - {response.text}",
                            "tree_items": [],
                            "metadata": {
                                "total_items": 0,
                                "project_id": project_id,
                                "path": path,
                                "ref": ref
                            }
                        })

                    # Parse response
                    items = response.json()
                    if not isinstance(items, list):
                        return json.dumps({
                            "success": False,
                            "error": "Unexpected response format from GitLab API",
                            "tree_items": [],
                            "metadata": {
                                "total_items": 0,
                                "project_id": project_id,
                                "path": path,
                                "ref": ref
                            }
                        })

                    # Process items and extract relevant information
                    for item in items:
                        processed_item = {
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "type": item.get("type"),  # 'blob' for files, 'tree' for directories
                            "path": item.get("path"),
                            "mode": item.get("mode"),
                            "web_url": item.get("web_url")
                        }
                        all_items.append(processed_item)

                    # Check for pagination headers
                    if "X-Total-Pages" in response.headers:
                        total_pages = int(response.headers["X-Total-Pages"])
                    else:
                        # If no pagination headers, we're done
                        break
                    
                    current_page += 1
                    
                    # Safety check to prevent infinite loops
                    if current_page > 1000:  # Max 1000 pages = 100,000 items
                        break

                except requests.exceptions.Timeout:
                    return json.dumps({
                        "success": False,
                        "error": "Request timeout. GitLab API is taking too long to respond",
                        "tree_items": all_items,
                        "metadata": {
                            "total_items": len(all_items),
                            "project_id": project_id,
                            "path": path,
                            "ref": ref
                        }
                    })
                
                except requests.exceptions.ConnectionError:
                    return json.dumps({
                        "success": False,
                        "error": "Connection error. Unable to reach GitLab API",
                        "tree_items": all_items,
                        "metadata": {
                            "total_items": len(all_items),
                            "project_id": project_id,
                            "path": path,
                            "ref": ref
                        }
                    })

            # Sort items by type (directories first) then by name
            all_items.sort(key=lambda x: (x["type"] != "tree", x["name"].lower()))

            return json.dumps({
                "success": True,
                "tree_items": all_items,
                "metadata": {
                    "total_items": len(all_items),
                    "project_id": project_id,
                    "path": path,
                    "ref": ref,
                    "recursive": recursive,
                    "pages_fetched": current_page - 1
                }
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "tree_items": [],
                "metadata": {
                    "total_items": 0,
                    "project_id": project_id,
                    "path": path,
                    "ref": ref
                }
            })