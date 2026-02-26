# Copyright (c) 2026 Red Hat Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import requests
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


class DevLakeAPIError(Exception):
    """Exception raised for DevLake API errors."""
    pass


class DevLakeAPI:
    """Client for interacting with DevLake API."""

    def __init__(self, base_url: str, api_token: str = None, timeout: int = 30):
        """
        Initialize DevLake API client.

        Args:
            base_url: Base URL for DevLake instance
            api_token: DevLake API token for authentication (optional)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._api_token = api_token  # Store for session refresh
        self.session = requests.Session()

        # Set auth header if token provided
        if api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {api_token}'
            })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Make HTTP request to DevLake API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Response JSON data

        Raises:
            DevLakeAPIError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)

            # If 401, session expired - create new session and retry once
            if response.status_code == 401:
                logger.warning("Session expired (401), refreshing session and retrying...")
                self.session = requests.Session()
                if hasattr(self, '_api_token') and self._api_token:
                    self.session.headers.update({'Authorization': f'Bearer {self._api_token}'})
                response = self.session.request(method, url, **kwargs)

            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            logger.error(f"DevLake API request failed: {method} {endpoint} - {str(e)}")
            raise DevLakeAPIError(f"API request failed: {str(e)}")

    def create_connection(
        self,
        name: str,
        github_token: str,
        endpoint: str = "https://api.github.com/"
    ) -> dict:
        """
        Create a new GitHub connection in DevLake.

        Args:
            name: Connection name
            github_token: GitHub Personal Access Token (NOT LOGGED)
            endpoint: GitHub API endpoint

        Returns:
            Connection object with 'id' field

        Raises:
            DevLakeAPIError: If connection creation fails
        """
        payload = {
            "name": name,
            "endpoint": endpoint,
            "authMethod": "AccessToken",
            "token": github_token,  # ⚠️ Only place token is used, never logged
            "enableGraphql": True
        }

        # DO NOT log the payload (contains token)
        logger.info(f"Creating GitHub connection: {name}")

        return self._make_request('POST', '/api/plugins/github/connections', json=payload)

    def create_gitlab_connection(self, name: str, gitlab_token: str, endpoint: str = "https://gitlab.cee.redhat.com/api/v4/") -> dict:
        """
        Create a GitLab connection in DevLake.

        Args:
            name: Connection name
            gitlab_token: GitLab Personal Access Token (NOT LOGGED)
            endpoint: GitLab API endpoint (default: Red Hat internal GitLab)

        Returns:
            Connection object with 'id' field

        Raises:
            DevLakeAPIError: If connection creation fails
        """
        payload = {
            "name": name,
            "endpoint": endpoint,
            "authMethod": "AccessToken",
            "token": gitlab_token,  # ⚠️ Only place token is used, never logged
        }

        # DO NOT log the payload (contains token)
        logger.info(f"Creating GitLab connection: {name}")

        return self._make_request('POST', '/api/plugins/gitlab/connections', json=payload)

    def create_scope_config(self, connection_id: int, name: str, plugin: str = "github") -> dict:
        """
        Create a scope configuration for a connection.

        Args:
            connection_id: Connection ID
            name: Name for the scope config
            plugin: Plugin type (github or gitlab)

        Returns:
            Scope config object with 'id' field

        Raises:
            DevLakeAPIError: If creation fails
        """
        payload = {
            "connectionId": connection_id,
            "name": name,
            "entities": ["CODE", "CICD"],
            "envNamePattern": "(?i)prod(.*)",
            "deploymentPattern": "",
            "productionPattern": ""
        }

        logger.info(f"Creating scope config for {plugin} connection {connection_id}")

        return self._make_request(
            'POST',
            f'/api/plugins/{plugin}/connections/{connection_id}/scope-configs',
            json=payload
        )

    def search_github_repo(self, connection_id: int, repo_full_name: str) -> dict:
        """
        Search for a GitHub repository by name to get its ID.

        Args:
            connection_id: GitHub connection ID
            repo_full_name: Repository full name (e.g., "owner/repo")

        Returns:
            Repository data with githubId

        Raises:
            DevLakeAPIError: If repository not found
        """
        # Extract owner and repo name from path
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise DevLakeAPIError(f"Invalid repo path: {repo_full_name}. Use format: owner/repo")

        owner_name, repo_name = parts

        # Search for the owner/organization first
        result = self._make_request(
            'GET',
            f'/api/plugins/github/connections/{connection_id}/remote-scopes',
            params={"search": owner_name, "page": 1, "pageSize": 50}
        )

        owner_id = None
        for child in result.get('children', []):
            if child.get('name') == owner_name and child.get('type') == 'group':
                owner_id = child.get('id')
                break

        if not owner_id:
            # Owner not found in DevLake - try GitHub public API as fallback
            logger.warning(f"Owner '{owner_name}' not found via DevLake API, trying GitHub public API")
            return self._fallback_github_public_api(repo_full_name)

        # Search for the repo within the owner/organization
        # Try multiple pages since orgs can have many repos
        for page in range(1, 6):  # Search up to 5 pages (1000 repos)
            result = self._make_request(
                'GET',
                f'/api/plugins/github/connections/{connection_id}/remote-scopes',
                params={"groupId": owner_id, "page": page, "pageSize": 200}
            )

            for child in result.get('children', []):
                if child.get('type') == 'scope' and child.get('fullName') == repo_full_name:
                    return child.get('data', {})

            # Check if there are more pages
            if not result.get('nextPageToken'):
                break

        # Not found via DevLake - try GitHub public API as fallback
        logger.warning(f"Repository '{repo_full_name}' not found via DevLake API, trying GitHub public API")
        return self._fallback_github_public_api(repo_full_name)

    def _fallback_github_public_api(self, repo_full_name: str) -> dict:
        """
        Fallback to GitHub's public API to get repo details.

        This is used when DevLake's remote-scopes API doesn't return the repo,
        which can happen due to caching, pagination limits, or API inconsistencies.

        Args:
            repo_full_name: Repository full name (e.g., "owner/repo")

        Returns:
            Repository data in DevLake format with githubId

        Raises:
            DevLakeAPIError: If repository not found or not accessible
        """
        import requests

        try:
            # Use GitHub's public API
            response = requests.get(
                f'https://api.github.com/repos/{repo_full_name}',
                timeout=10
            )

            if response.status_code == 404:
                raise DevLakeAPIError(
                    f"Repository '{repo_full_name}' not found. Please verify the repo name is correct."
                )
            elif response.status_code != 200:
                raise DevLakeAPIError(
                    f"Failed to fetch repo details from GitHub API: {response.status_code}"
                )

            repo = response.json()

            # Convert GitHub API response to DevLake format
            return {
                'githubId': repo['id'],
                'name': repo['name'],
                'fullName': repo['full_name'],
                'HTMLUrl': repo['html_url'],
                'description': repo.get('description', ''),
                'ownerId': repo['owner']['id'],
                'cloneUrl': repo['clone_url'],
                'createdDate': repo['created_at'],
                'updatedDate': repo['updated_at'],
                'language': repo.get('language', '')
            }

        except requests.RequestException as e:
            raise DevLakeAPIError(f"Failed to connect to GitHub API: {str(e)}")

    def add_scope(self, connection_id: int, repo_full_name: str, scope_config_id: int = None) -> dict:
        """
        Add a repository scope to a GitHub connection.

        Args:
            connection_id: GitHub connection ID
            repo_full_name: Repository full name (e.g., "owner/repo")
            scope_config_id: Optional scope config ID (if None, must be provided separately)

        Returns:
            Scope object with githubId

        Raises:
            DevLakeAPIError: If scope creation fails
        """
        # First, search for the repo to get its metadata
        repo_data = self.search_github_repo(connection_id, repo_full_name)
        github_id = repo_data.get('githubId')

        if not github_id:
            raise DevLakeAPIError(f"Could not find githubId for repository: {repo_full_name}")

        # Add scope using githubId and include metadata for immediate display
        payload = {
            "data": [
                {
                    "githubId": github_id,
                    "name": repo_data.get('name', ''),
                    "fullName": repo_data.get('fullName', repo_full_name),
                    "HTMLUrl": repo_data.get('HTMLUrl', ''),
                    "description": repo_data.get('description', ''),
                    "ownerId": repo_data.get('ownerId', 0),
                    "cloneUrl": repo_data.get('cloneUrl', ''),
                    "createdDate": repo_data.get('createdDate', ''),
                    "updatedDate": repo_data.get('updatedDate', ''),
                    "scopeConfigId": scope_config_id
                }
            ]
        }

        logger.info(f"Adding GitHub scope {repo_full_name} (ID: {github_id}) to connection {connection_id} with config {scope_config_id}")

        result = self._make_request(
            'PUT',
            f'/api/plugins/github/connections/{connection_id}/scopes',
            json=payload
        )

        # Return in consistent format
        return {"scopes": result if isinstance(result, list) else [result]}

    def search_gitlab_project(self, connection_id: int, project_name: str) -> dict:
        """
        Search for a GitLab project by name to get its ID.

        Args:
            connection_id: GitLab connection ID
            project_name: Project name to search for

        Returns:
            Project data with gitlabId

        Raises:
            DevLakeAPIError: If project not found
        """
        # Extract group and project name from path
        parts = project_name.split("/")
        if len(parts) != 2:
            raise DevLakeAPIError(f"Invalid project path: {project_name}. Use format: group/project")

        group_name, proj_name = parts

        # First, search for the group
        result = self._make_request(
            'GET',
            f'/api/plugins/gitlab/connections/{connection_id}/remote-scopes',
            params={"search": group_name, "page": 1, "pageSize": 50}
        )

        group_id = None
        for child in result.get('children', []):
            if child.get('name') == group_name and child.get('type') == 'group':
                group_id = child.get('id')
                break

        if not group_id:
            raise DevLakeAPIError(f"Group '{group_name}' not found")

        # Search for the project within the group
        result = self._make_request(
            'GET',
            f'/api/plugins/gitlab/connections/{connection_id}/remote-scopes',
            params={"groupId": group_id, "page": 1, "pageSize": 100}
        )

        for child in result.get('children', []):
            if child.get('type') == 'scope' and child.get('fullName') == project_name:
                return child.get('data', {})

        # Not found - provide a helpful error message
        raise DevLakeAPIError(
            f"Project '{project_name}' not found in group '{group_name}'. "
            f"This could mean: (1) The GitLab PAT token configured in this connection doesn't have access to the project, "
            f"(2) The project is private and requires additional permissions, or "
            f"(3) The project doesn't exist. Please verify the project path and that the PAT token has access to it."
        )

    def add_gitlab_scope(self, connection_id: int, project_full_name: str, scope_config_id: int = None) -> dict:
        """
        Add a project scope to a GitLab connection.

        Args:
            connection_id: GitLab connection ID
            project_full_name: Project full name (e.g., "group/project")
            scope_config_id: Optional scope config ID (if None, must be provided separately)

        Returns:
            Scope object with gitlabId

        Raises:
            DevLakeAPIError: If scope creation fails
        """
        # First, search for the project to get its metadata
        project_data = self.search_gitlab_project(connection_id, project_full_name)
        gitlab_id = project_data.get('gitlabId')

        if not gitlab_id:
            raise DevLakeAPIError(f"Could not find gitlabId for project: {project_full_name}")

        # Add scope using gitlabId and include metadata for immediate display
        payload = {
            "data": [
                {
                    "gitlabId": gitlab_id,
                    "name": project_data.get('name', ''),
                    "pathWithNamespace": project_data.get('pathWithNamespace', project_full_name),
                    "description": project_data.get('description', ''),
                    "defaultBranch": project_data.get('defaultBranch', ''),
                    "webUrl": project_data.get('webUrl', ''),
                    "visibility": project_data.get('visibility', ''),
                    "httpUrlToRepo": project_data.get('httpUrlToRepo', ''),
                    "scopeConfigId": scope_config_id
                }
            ]
        }

        logger.info(f"Adding GitLab scope {project_full_name} (ID: {gitlab_id}) to connection {connection_id} with config {scope_config_id}")

        result = self._make_request(
            'PUT',
            f'/api/plugins/gitlab/connections/{connection_id}/scopes',
            json=payload
        )

        # Return in same format as GitHub for consistency
        return {"scopes": result if isinstance(result, list) else [result]}

    def create_project(
        self,
        project_name: str,
        connection_id: int,
        github_id: int,
        cron_config: str = "0 0 * * *"
    ) -> dict:
        """
        Create a DevLake project with blueprint.

        Args:
            project_name: Name of the project
            connection_id: GitHub connection ID
            github_id: GitHub repository ID
            cron_config: Cron schedule (default: daily at midnight)

        Returns:
            Project object

        Raises:
            DevLakeAPIError: If project creation fails
        """
        payload = {
            "name": project_name,
            "enable": True,
            "metrics": [
                {"pluginName": "dora", "enable": True},
                {"pluginName": "issue_trace", "enable": True}
            ],
            "blueprint": {
                "name": f"{project_name}-Blueprint",
                "projectName": project_name,
                "mode": "NORMAL",
                "enable": True,
                "cronConfig": cron_config,
                "plan": [[{
                    "plugin": "github",
                    "options": {
                        "connectionId": connection_id,
                        "githubId": github_id
                    }
                }]]
            }
        }

        logger.info(f"Creating project: {project_name}")

        return self._make_request('POST', '/api/projects', json=payload)

    def trigger_blueprint(self, blueprint_id: int) -> dict:
        """
        Trigger a blueprint to run immediately.

        Args:
            blueprint_id: Blueprint ID to trigger

        Returns:
            Pipeline object

        Raises:
            DevLakeAPIError: If trigger fails
        """
        logger.info(f"Triggering blueprint: {blueprint_id}")

        return self._make_request('POST', f'/api/blueprints/{blueprint_id}/trigger')

    def create_full_project(
        self,
        project_name: str,
        repo_full_name: str,
        github_token: str,
        cron_config: str = "0 0 * * *"
    ) -> dict:
        """
        Create a complete DevLake project (connection + scope + project + trigger).

        This is the main method for creating projects from Slack.
        GitHub token is used immediately and never stored.

        Args:
            project_name: Name for the project
            repo_full_name: GitHub repo (e.g., "owner/repo")
            github_token: GitHub PAT (in-memory only, never logged)
            cron_config: Cron schedule

        Returns:
            Dict with project info and URLs

        Raises:
            DevLakeAPIError: If any step fails
        """
        try:
            # Step 1: Create connection (token used here, then out of scope)
            conn = self.create_connection(
                name=f"{project_name}-connection",
                github_token=github_token
            )
            conn_id = conn['id']

            # Token is no longer needed after this point!

            # Step 2: Create scope configuration
            scope_config = self.create_scope_config(
                connection_id=conn_id,
                name=project_name,
                plugin="github"
            )
            scope_config_id = scope_config['id']

            # Step 3: Add repository scope
            scope = self.add_scope(conn_id, repo_full_name, scope_config_id)
            github_id = scope['scopes'][0]['scope']['githubId']

            # Step 4: Create project with blueprint
            project = self.create_project(
                project_name=project_name,
                connection_id=conn_id,
                github_id=github_id,
                cron_config=cron_config
            )

            # Step 5: Trigger initial pipeline
            blueprint_id = project['blueprint']['id']
            pipeline = self.trigger_blueprint(blueprint_id)

            return {
                'success': True,
                'project': project_name,
                'connection_id': conn_id,
                'blueprint_id': blueprint_id,
                'pipeline_id': pipeline.get('id'),
                'dashboard_url': self.base_url
            }

        except DevLakeAPIError as e:
            logger.error(f"Failed to create project {project_name}: {str(e)}")
            raise

    def create_multi_platform_project(
        self,
        project_name: str,
        github_repos: list = None,
        github_token: str = None,
        github_conn_id: int = None,
        gitlab_repos: list = None,
        gitlab_token: str = None,
        gitlab_conn_id: int = None,
        cron_config: str = "0 0 * * *"
    ) -> dict:
        """
        Create a DevLake project with both GitHub and GitLab repositories.

        This method creates connections for both platforms (if provided),
        adds multiple repository scopes, and creates a single project.

        Args:
            project_name: Name for the project
            github_repos: List of GitHub repos (e.g., ["owner/repo1", "owner/repo2"])
            github_token: GitHub PAT (in-memory only, never logged) - for new connection
            github_conn_id: Existing GitHub connection ID (use instead of creating new)
            gitlab_repos: List of GitLab projects (e.g., ["group/project1"])
            gitlab_token: GitLab PAT (in-memory only, never logged) - for new connection
            gitlab_conn_id: Existing GitLab connection ID (use instead of creating new)
            cron_config: Cron schedule

        Returns:
            Dict with project info and URLs

        Raises:
            DevLakeAPIError: If any step fails
        """
        github_repos = github_repos or []
        gitlab_repos = gitlab_repos or []

        try:
            scope_configs = []

            # Process GitHub repositories
            if github_repos:
                # Use existing connection or create new
                if github_conn_id:
                    logger.info(f"Using existing GitHub connection ID: {github_conn_id}")
                    actual_github_conn_id = github_conn_id
                elif github_token:
                    # Create GitHub connection (token used here, then out of scope)
                    logger.info("Creating new GitHub connection")
                    github_conn = self.create_connection(
                        name=f"{project_name}-github",
                        github_token=github_token
                    )
                    actual_github_conn_id = github_conn['id']
                else:
                    raise DevLakeAPIError("Either github_conn_id or github_token must be provided")

                # Get existing scope configs or create new one
                existing_configs = self.get_scope_configs(actual_github_conn_id, "github")
                if existing_configs and len(existing_configs) > 0:
                    scope_config_id = existing_configs[0]['id']
                    logger.info(f"Reusing existing GitHub scope config ID: {scope_config_id}")
                else:
                    scope_config = self.create_scope_config(
                        connection_id=actual_github_conn_id,
                        name=project_name,
                        plugin="github"
                    )
                    scope_config_id = scope_config['id']
                    logger.info(f"Created new GitHub scope config ID: {scope_config_id}")

                # Add all GitHub repo scopes
                for repo in github_repos:
                    scope = self.add_scope(actual_github_conn_id, repo, scope_config_id)
                    github_id = scope['scopes'][0]['scope']['githubId']
                    scope_configs.append({
                        "plugin": "github",
                        "connectionId": actual_github_conn_id,
                        "scopeId": f"github:GithubRepo:{actual_github_conn_id}:{github_id}"
                    })

            # Process GitLab repositories
            if gitlab_repos:
                # Use existing connection or create new
                if gitlab_conn_id:
                    logger.info(f"Using existing GitLab connection ID: {gitlab_conn_id}")
                    actual_gitlab_conn_id = gitlab_conn_id
                elif gitlab_token:
                    # Create GitLab connection (token used here, then out of scope)
                    logger.info(f"Creating new GitLab connection for {len(gitlab_repos)} projects")
                    gitlab_conn = self.create_gitlab_connection(
                        name=f"{project_name}-gitlab",
                        gitlab_token=gitlab_token
                    )
                    actual_gitlab_conn_id = gitlab_conn['id']
                    logger.info(f"GitLab connection created with ID: {actual_gitlab_conn_id}")
                else:
                    raise DevLakeAPIError("Either gitlab_conn_id or gitlab_token must be provided")

                # Get existing scope configs or create new one
                existing_configs = self.get_scope_configs(actual_gitlab_conn_id, "gitlab")
                if existing_configs and len(existing_configs) > 0:
                    scope_config_id = existing_configs[0]['id']
                    logger.info(f"Reusing existing GitLab scope config ID: {scope_config_id}")
                else:
                    scope_config = self.create_scope_config(
                        connection_id=actual_gitlab_conn_id,
                        name=project_name,
                        plugin="gitlab"
                    )
                    scope_config_id = scope_config['id']
                    logger.info(f"Created new GitLab scope config ID: {scope_config_id}")

                # Add all GitLab project scopes
                for project in gitlab_repos:
                    logger.info(f"Adding GitLab project scope: {project}")
                    scope = self.add_gitlab_scope(actual_gitlab_conn_id, project, scope_config_id)
                    logger.info(f"GitLab scope response: {scope}")
                    gitlab_id = scope['scopes'][0]['scope']['gitlabId']
                    scope_configs.append({
                        "plugin": "gitlab",
                        "connectionId": actual_gitlab_conn_id,
                        "scopeId": f"gitlab:GitlabProject:{actual_gitlab_conn_id}:{gitlab_id}"
                    })

            # Tokens are no longer needed after this point!

            # Time range: collect last 30 days only
            from datetime import datetime, timezone, timedelta
            time_after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')

            # Create project with all scopes from both platforms
            payload = {
                "name": project_name,
                "enable": True,
                "metrics": [
                    {"pluginName": "dora", "enable": True},
                    {"pluginName": "issue_trace", "enable": True}
                ],
                "blueprint": {
                    "name": f"{project_name}-Blueprint",
                    "projectName": project_name,
                    "mode": "NORMAL",
                    "enable": True,
                    "cronConfig": cron_config,
                    "isManual": False,
                    "skipOnFail": False,
                    "timeAfter": time_after,
                    "skipCollectors": False,
                    "fullSync": False,
                    "settings": {
                        "version": "2.0.0",
                        "connections": scope_configs
                    }
                }
            }

            logger.info(f"Creating multi-platform project: {project_name}")
            project = self._make_request('POST', '/api/projects', json=payload)

            # Build blueprint connections format (for linking scopes to project)
            blueprint_connections = []

            # Extract GitHub scope IDs
            github_scopes = [
                {"scopeId": sc['scopeId'].split(':')[-1]}
                for sc in scope_configs if sc['plugin'] == 'github'
            ]
            if github_scopes:
                blueprint_connections.append({
                    "pluginName": "github",
                    "connectionId": actual_github_conn_id,
                    "scopes": github_scopes
                })

            # Extract GitLab scope IDs
            gitlab_scopes = [
                {"scopeId": sc['scopeId'].split(':')[-1]}
                for sc in scope_configs if sc['plugin'] == 'gitlab'
            ]
            if gitlab_scopes:
                blueprint_connections.append({
                    "pluginName": "gitlab",
                    "connectionId": actual_gitlab_conn_id,
                    "scopes": gitlab_scopes
                })

            # Update blueprint to link scopes to project and confirm time range
            blueprint_id = project['blueprint']['id']
            logger.info(f"Linking {len(github_repos) + len(gitlab_repos)} scopes to project via blueprint {blueprint_id}")
            self._make_request(
                'PATCH',
                f'/api/blueprints/{blueprint_id}',
                json={
                    "connections": blueprint_connections,
                    "timeAfter": time_after,
                    "cronConfig": cron_config,
                    "skipCollectors": False,
                    "fullSync": False
                }
            )

            # Trigger initial pipeline
            pipeline = self.trigger_blueprint(blueprint_id)

            return {
                'success': True,
                'project': project_name,
                'blueprint_id': blueprint_id,
                'pipeline_id': pipeline.get('id'),
                'dashboard_url': self.base_url
            }

        except DevLakeAPIError as e:
            logger.error(f"Failed to create multi-platform project {project_name}: {str(e)}")
            raise

    def get_projects(self, page: int = 1, page_size: int = 10) -> dict:
        """Get list of projects."""
        return self._make_request(
            'GET',
            f'/api/projects?page={page}&pageSize={page_size}'
        )

    def get_connections(self, plugin: str = "github") -> dict:
        """Get list of connections for a plugin."""
        return self._make_request('GET', f'/api/plugins/{plugin}/connections')

    def get_scope_configs(self, connection_id: int, plugin: str = "github") -> list:
        """Get scope configs for a connection."""
        result = self._make_request('GET', f'/api/plugins/{plugin}/connections/{connection_id}/scope-configs')
        # Result is a list of scope configs
        return result if isinstance(result, list) else []

    def link_scopes_to_project(self, project_name: str, plugin: str, connection_id: int, scope_ids: list):
        """
        Link scopes to a project by updating its blueprint.

        Args:
            project_name: Name of the project
            plugin: Plugin name ("github" or "gitlab")
            connection_id: Connection ID
            scope_ids: List of scope IDs to add (numeric IDs as strings)

        Raises:
            DevLakeAPIError: If linking fails
        """
        # Get project to get blueprint ID
        project = self._make_request('GET', f'/api/projects/{project_name}')
        blueprint_id = project['blueprint']['id']

        # Get current blueprint connections
        blueprint = self._make_request('GET', f'/api/blueprints/{blueprint_id}')
        connections = blueprint.get('connections', [])

        # Find or create the connection entry
        connection_found = False
        for conn in connections:
            if conn.get('pluginName') == plugin and conn.get('connectionId') == connection_id:
                # Add new scope IDs to existing connection (avoid duplicates)
                existing_scope_ids = {s['scopeId'] for s in conn.get('scopes', [])}
                for scope_id in scope_ids:
                    if scope_id not in existing_scope_ids:
                        conn['scopes'].append({"scopeId": scope_id})
                connection_found = True
                break

        # If connection not found, create new entry
        if not connection_found:
            connections.append({
                "pluginName": plugin,
                "connectionId": connection_id,
                "scopes": [{"scopeId": sid} for sid in scope_ids]
            })

        # Update blueprint with new connections
        logger.info(f"Updating blueprint {blueprint_id} to link {len(scope_ids)} scopes")
        self._make_request(
            'PATCH',
            f'/api/blueprints/{blueprint_id}',
            json={"connections": connections}
        )
