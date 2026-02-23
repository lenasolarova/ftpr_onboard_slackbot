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

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize DevLake API client.

        Args:
            base_url: Base URL for DevLake instance
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

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

    def create_gitlab_connection(self, name: str, gitlab_token: str, endpoint: str = "https://gitlab.com/api/v4/") -> dict:
        """
        Create a GitLab connection in DevLake.

        Args:
            name: Connection name
            gitlab_token: GitLab Personal Access Token (NOT LOGGED)
            endpoint: GitLab API endpoint

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

    def add_scope(self, connection_id: int, repo_full_name: str) -> dict:
        """
        Add a repository scope to a GitHub connection.

        Args:
            connection_id: GitHub connection ID
            repo_full_name: Repository full name (e.g., "owner/repo")

        Returns:
            Scope object with githubId

        Raises:
            DevLakeAPIError: If scope creation fails
        """
        payload = [{"fullName": repo_full_name}]

        logger.info(f"Adding scope {repo_full_name} to connection {connection_id}")

        return self._make_request(
            'PUT',
            f'/api/plugins/github/connections/{connection_id}/scopes',
            json=payload
        )

    def add_gitlab_scope(self, connection_id: int, project_full_name: str) -> dict:
        """
        Add a project scope to a GitLab connection.

        Args:
            connection_id: GitLab connection ID
            project_full_name: Project full name (e.g., "group/project")

        Returns:
            Scope object with gitlabId

        Raises:
            DevLakeAPIError: If scope creation fails
        """
        payload = [{"name": project_full_name}]

        logger.info(f"Adding GitLab scope {project_full_name} to connection {connection_id}")

        return self._make_request(
            'PUT',
            f'/api/plugins/gitlab/connections/{connection_id}/scopes',
            json=payload
        )

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

            # Step 2: Add repository scope
            scope = self.add_scope(conn_id, repo_full_name)
            github_id = scope['scopes'][0]['scope']['githubId']

            # Step 3: Create project with blueprint
            project = self.create_project(
                project_name=project_name,
                connection_id=conn_id,
                github_id=github_id,
                cron_config=cron_config
            )

            # Step 4: Trigger initial pipeline
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
        gitlab_repos: list = None,
        gitlab_token: str = None,
        cron_config: str = "0 0 * * *"
    ) -> dict:
        """
        Create a DevLake project with both GitHub and GitLab repositories.

        This method creates connections for both platforms (if provided),
        adds multiple repository scopes, and creates a single project.

        Args:
            project_name: Name for the project
            github_repos: List of GitHub repos (e.g., ["owner/repo1", "owner/repo2"])
            github_token: GitHub PAT (in-memory only, never logged)
            gitlab_repos: List of GitLab projects (e.g., ["group/project1"])
            gitlab_token: GitLab PAT (in-memory only, never logged)
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
            if github_repos and github_token:
                # Create GitHub connection (token used here, then out of scope)
                github_conn = self.create_connection(
                    name=f"{project_name}-github",
                    github_token=github_token
                )
                github_conn_id = github_conn['id']

                # Add all GitHub repo scopes
                for repo in github_repos:
                    scope = self.add_scope(github_conn_id, repo)
                    github_id = scope['scopes'][0]['scope']['githubId']
                    scope_configs.append({
                        "plugin": "github",
                        "connectionId": github_conn_id,
                        "scopeId": f"github:GithubRepo:{github_conn_id}:{github_id}"
                    })

            # Process GitLab repositories
            if gitlab_repos and gitlab_token:
                # Create GitLab connection (token used here, then out of scope)
                gitlab_conn = self.create_gitlab_connection(
                    name=f"{project_name}-gitlab",
                    gitlab_token=gitlab_token
                )
                gitlab_conn_id = gitlab_conn['id']

                # Add all GitLab project scopes
                for project in gitlab_repos:
                    scope = self.add_gitlab_scope(gitlab_conn_id, project)
                    gitlab_id = scope['scopes'][0]['scope']['gitlabId']
                    scope_configs.append({
                        "plugin": "gitlab",
                        "connectionId": gitlab_conn_id,
                        "scopeId": f"gitlab:GitlabProject:{gitlab_conn_id}:{gitlab_id}"
                    })

            # Tokens are no longer needed after this point!

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
                    "settings": {
                        "version": "2.0.0",
                        "connections": scope_configs
                    }
                }
            }

            logger.info(f"Creating multi-platform project: {project_name}")
            project = self._make_request('POST', '/api/projects', json=payload)

            # Trigger initial pipeline
            blueprint_id = project['blueprint']['id']
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
