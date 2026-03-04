from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import os

class GitLabFileTreeInput(BaseModel):
    """Input schema for GitLab File Tree Tool."""
    project_id: str = Field(..., description="GitLab project ID or namespace/project-name")
    path: str = Field(default="", description="Specific directory path to list (optional)")
    recursive: bool = Field(default=False, description="Whether to list files recursively")

class GitLabFileTreeTool(BaseTool):
    """Tool for listing GitLab repository file structure."""

    name: str = "GitLab File Tree Tool"
    description: str = (
        "Lists the file structure of a GitLab repository using GitLab API v4. "
        "Returns information about files and directories including name, type, path, size, and mode. "
        "Filters out binary files and common non-code files for security. "
        "Usage: provide project_id (required), path (optional), and recursive (optional)."
    )
    args_schema: Type[BaseModel] = GitLabFileTreeInput

    def _run(self, project_id: str, path: str = "", recursive: bool = False) -> str:
        """
        Retrieve GitLab repository file tree structure.
        
        Args:
            project_id: GitLab project ID or namespace/project-name
            path: Specific directory path to list (default: "")
            recursive: Whether to list files recursively (default: False)
        
        Returns:
            JSON string with file/directory metadata wrapped in security tags
        """
        try:
            # Get GitLab API key from environment
            api_key = os.getenv('GITLAB_API_KEY')
            if not api_key:
                return "<UNTRUSTED_CONTENT>Error: GITLAB_API_KEY environment variable not set. Please configure your GitLab API key.</UNTRUSTED_CONTENT>"

            # GitLab API v4 base URL
            base_url = "https://gitlab.com/api/v4"
            
            # Prepare headers
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Accept': 'application/json'
            }

            # URL encode project_id if it contains special characters
            project_id_encoded = requests.utils.quote(project_id, safe='')
            
            all_items = []
            page = 1
            max_pages = 5  # Limit to 500 items total (100 per page)

            while page <= max_pages:
                # Build API URL
                url = f"{base_url}/projects/{project_id_encoded}/repository/tree"
                
                params = {
                    'per_page': 100,
                    'page': page,
                    'recursive': str(recursive).lower()
                }
                
                if path:
                    params['path'] = path

                # Make API request
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                if response.status_code == 401:
                    return "<UNTRUSTED_CONTENT>Error: Unauthorized. Please check your GitLab API key permissions.</UNTRUSTED_CONTENT>"
                elif response.status_code == 404:
                    return f"<UNTRUSTED_CONTENT>Error: Project '{project_id}' not found or path '{path}' does not exist.</UNTRUSTED_CONTENT>"
                elif response.status_code != 200:
                    return f"<UNTRUSTED_CONTENT>Error: GitLab API request failed with status {response.status_code}: {response.text}</UNTRUSTED_CONTENT>"

                data = response.json()
                
                if not data:  # No more items
                    break

                # Filter and process items
                filtered_items = self._filter_items(data)
                all_items.extend(filtered_items)

                # Check if we have more pages
                if len(data) < 100:  # Less than per_page means last page
                    break
                    
                page += 1

            # Format output
            result = {
                'project_id': project_id,
                'path': path,
                'recursive': recursive,
                'total_items': len(all_items),
                'items': all_items
            }

            return f"<UNTRUSTED_CONTENT>{json.dumps(result, indent=2, ensure_ascii=False)}</UNTRUSTED_CONTENT>"

        except requests.exceptions.Timeout:
            return "<UNTRUSTED_CONTENT>Error: Request timeout. GitLab API is not responding.</UNTRUSTED_CONTENT>"
        except requests.exceptions.ConnectionError:
            return "<UNTRUSTED_CONTENT>Error: Connection error. Unable to reach GitLab API.</UNTRUSTED_CONTENT>"
        except requests.exceptions.RequestException as e:
            return f"<UNTRUSTED_CONTENT>Error: Request failed - {str(e)}</UNTRUSTED_CONTENT>"
        except json.JSONDecodeError:
            return "<UNTRUSTED_CONTENT>Error: Invalid JSON response from GitLab API.</UNTRUSTED_CONTENT>"
        except Exception as e:
            return f"<UNTRUSTED_CONTENT>Error: Unexpected error occurred - {str(e)}</UNTRUSTED_CONTENT>"

    def _filter_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out binary files and common non-code files.
        
        Args:
            items: List of file/directory items from GitLab API
            
        Returns:
            Filtered list of items
        """
        # Files/directories to exclude
        excluded_names = {
            '.git', '.DS_Store', 'Thumbs.db', '.gitignore', '.gitmodules',
            '__pycache__', '.pyc', '.pyo', '.pyd', 'node_modules', '.npm',
            '.idea', '.vscode', '.vs', '.cache', '.tmp', '.temp',
            '.log', '.lock', '.pid', '.swp', '.swo', '~'
        }
        
        # Binary file extensions to exclude
        binary_extensions = {
            '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o', '.a',
            '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2', '.xz',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.ico',
            '.mp3', '.wav', '.mp4', '.avi', '.mov', '.wmv', '.flv',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.class', '.jar', '.war', '.ear'
        }

        filtered_items = []
        
        for item in items:
            name = item.get('name', '')
            item_type = item.get('type', '')
            
            # Skip if name matches excluded patterns
            if name in excluded_names:
                continue
                
            # Skip if it's a file with binary extension
            if item_type == 'blob' and any(name.lower().endswith(ext) for ext in binary_extensions):
                continue
                
            # Skip hidden files (starting with .) except common config files
            if name.startswith('.') and name not in {'.env.example', '.gitignore', '.editorconfig', '.eslintrc', '.prettierrc'}:
                continue

            # Create clean item structure
            clean_item = {
                'name': item.get('name', ''),
                'type': item.get('type', ''),  # 'blob' for file, 'tree' for directory
                'path': item.get('path', ''),
                'mode': item.get('mode', ''),
                'id': item.get('id', '')
            }
            
            # Add size if available (only for blobs/files)
            if 'size' in item and item_type == 'blob':
                clean_item['size'] = item['size']

            filtered_items.append(clean_item)

        return filtered_items