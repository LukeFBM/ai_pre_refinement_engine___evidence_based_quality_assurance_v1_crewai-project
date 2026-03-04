from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any
import requests
import json
import os
import base64
from urllib.parse import quote_plus

class GitLabGetFileInput(BaseModel):
    """Input schema for GitLab Get File Tool."""
    project_id: int = Field(
        ..., 
        description="GitLab project ID (numeric ID of the project)"
    )
    file_path: str = Field(
        ..., 
        description="Path to the file in the repository (e.g., 'src/main.py' or 'README.md')"
    )
    ref: str = Field(
        default="main", 
        description="Git reference (branch, tag, or commit SHA). Defaults to 'main'"
    )

class GitLabGetFileTool(BaseTool):
    """Tool for retrieving file content and metadata from GitLab repositories via REST API."""

    name: str = "gitlab_get_file"
    description: str = (
        "Retrieves file content and metadata from GitLab repositories using the REST API. "
        "Supports both text and binary files with proper base64 decoding, URL encoding of paths, "
        "and comprehensive error handling. Returns file content, size, encoding, SHA256 hash, "
        "and commit information with configurable file size limits for security."
    )
    args_schema: Type[BaseModel] = GitLabGetFileInput

    # Init parameters
    gitlab_url: str = Field(
        default="https://gitlab.com",
        description="Base URL of the GitLab instance"
    )
    max_file_size_mb: int = Field(
        default=50,
        description="Maximum file size in MB to retrieve"
    )

    def __init__(self, gitlab_url: str = "https://gitlab.com", max_file_size_mb: int = 50, **kwargs):
        super().__init__(**kwargs)
        self.gitlab_url = gitlab_url.rstrip('/')
        self.max_file_size_mb = max_file_size_mb

    def _run(self, project_id: int, file_path: str, ref: str = "main") -> str:
        """
        Retrieve file content and metadata from GitLab repository.
        
        Args:
            project_id: GitLab project ID
            file_path: Path to file in repository
            ref: Git reference (branch, tag, or commit)
            
        Returns:
            JSON string with file content and metadata
        """
        try:
            # Get GitLab API key from environment
            api_key = os.getenv('GITLAB_API_KEY')
            if not api_key:
                return json.dumps({
                    "success": False,
                    "error": "GITLAB_API_KEY environment variable not set",
                    "error_type": "authentication_error"
                })

            # URL encode the file path to handle special characters and spaces
            encoded_file_path = quote_plus(file_path)
            
            # Construct API endpoint
            api_url = f"{self.gitlab_url}/api/v4/projects/{project_id}/repository/files/{encoded_file_path}"
            
            # Set up headers with authentication
            headers = {
                'Private-Token': api_key,
                'Content-Type': 'application/json'
            }
            
            # Set up parameters
            params = {
                'ref': ref
            }
            
            # Make API request
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            
            # Handle different HTTP response codes
            if response.status_code == 404:
                return json.dumps({
                    "success": False,
                    "error": f"File '{file_path}' not found in project {project_id} at ref '{ref}'",
                    "error_type": "file_not_found"
                })
            elif response.status_code == 401:
                return json.dumps({
                    "success": False,
                    "error": "Unauthorized - check your GitLab API key permissions",
                    "error_type": "unauthorized"
                })
            elif response.status_code == 403:
                return json.dumps({
                    "success": False,
                    "error": f"Access denied to project {project_id} or file '{file_path}'",
                    "error_type": "access_denied"
                })
            elif response.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"GitLab API error: {response.status_code} - {response.text}",
                    "error_type": "api_error"
                })
            
            # Parse JSON response
            file_data = response.json()
            
            # Check file size (GitLab returns size in bytes)
            file_size_bytes = file_data.get('size', 0)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            if file_size_mb > self.max_file_size_mb:
                return json.dumps({
                    "success": False,
                    "error": f"File too large: {file_size_mb:.2f}MB (max: {self.max_file_size_mb}MB)",
                    "error_type": "file_too_large",
                    "file_size_mb": file_size_mb
                })
            
            # Extract file content (base64 encoded by GitLab)
            content_b64 = file_data.get('content', '')
            if not content_b64:
                return json.dumps({
                    "success": False,
                    "error": "No content returned from GitLab API",
                    "error_type": "no_content"
                })
            
            # Decode base64 content
            try:
                decoded_content = base64.b64decode(content_b64)
                
                # Try to decode as UTF-8 text
                try:
                    content_text = decoded_content.decode('utf-8')
                    is_binary = False
                    file_content = content_text
                except UnicodeDecodeError:
                    # File is binary, keep as base64
                    is_binary = True
                    file_content = content_b64
                    
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to decode file content: {str(e)}",
                    "error_type": "decode_error"
                })
            
            # Prepare result with comprehensive metadata
            result = {
                "success": True,
                "file_info": {
                    "project_id": project_id,
                    "file_path": file_path,
                    "ref": ref,
                    "size_bytes": file_size_bytes,
                    "size_mb": round(file_size_mb, 4),
                    "is_binary": is_binary,
                    "encoding": file_data.get('encoding', 'base64'),
                    "content_sha256": file_data.get('content_sha256', ''),
                    "last_commit_id": file_data.get('last_commit_id', ''),
                    "blob_id": file_data.get('blob_id', ''),
                    "file_name": file_data.get('file_name', file_path.split('/')[-1])
                },
                "content": file_content
            }
            
            return json.dumps(result, indent=2)
            
        except requests.exceptions.Timeout:
            return json.dumps({
                "success": False,
                "error": "Request timeout - GitLab API did not respond within 30 seconds",
                "error_type": "timeout_error"
            })
        except requests.exceptions.ConnectionError:
            return json.dumps({
                "success": False,
                "error": f"Connection error - unable to reach GitLab at {self.gitlab_url}",
                "error_type": "connection_error"
            })
        except requests.exceptions.RequestException as e:
            return json.dumps({
                "success": False,
                "error": f"Request error: {str(e)}",
                "error_type": "request_error"
            })
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to parse GitLab API response as JSON: {str(e)}",
                "error_type": "json_parse_error"
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "unexpected_error"
            })