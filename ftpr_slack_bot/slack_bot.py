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

import argparse
import logging
import os
import re
import ssl

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from ftpr_slack_bot.common import config as bot_config
from ftpr_slack_bot.common.devlake_api import DevLakeAPI, DevLakeAPIError


# Configure logging (filter sensitive data)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configure SSL certificates for Red Hat corporate network
def setup_ssl_certs():
    """Setup SSL certificates for corporate network."""
    bundle_path = os.path.expanduser("~/bundle.crt")

    if os.path.exists(bundle_path):
        os.environ['SSL_CERT_FILE'] = bundle_path
        os.environ['REQUESTS_CA_BUNDLE'] = bundle_path
        logger.info(f"Using CA bundle: {bundle_path}")
    elif os.path.exists(os.path.expanduser("~/2022-IT-Root-CA.crt")):
        os.environ['SSL_CERT_FILE'] = os.path.expanduser("~/2022-IT-Root-CA.crt")
        logger.info("Using Red Hat IT Root CA")
    else:
        logger.warning("No custom CA bundle found, using system default")


# Setup SSL before any network calls
setup_ssl_certs()

# Parse arguments
parser = argparse.ArgumentParser(
    description='FTPR Slack Bot for DevLake integration',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument(
    '--config_file',
    default=None,
    required=False,
    help='Configuration file path'
)

parsed_args = parser.parse_args()
config_file = os.path.expanduser(parsed_args.config_file or "")

if config_file and os.path.exists(config_file):
    bot_config.update_config(config_file)

CONF = bot_config.CONF

# Initialize Slack app
app = App(token=CONF['default'].get("SLACK_BOT_TOKEN"))

# Initialize DevLake API client
devlake = DevLakeAPI(base_url=CONF['default'].get("DEVLAKE_URL"))


# Cron schedule options
CRON_SCHEDULES = {
    "daily": "0 0 * * *",           # Daily at midnight
    "weekly": "0 0 * * 1",          # Weekly on Monday
    "every_6h": "0 */6 * * *",      # Every 6 hours
    "every_12h": "0 */12 * * *",    # Every 12 hours
}


def get_create_project_modal():
    """Return the modal view for creating a DevLake project."""
    return {
        "type": "modal",
        "callback_id": "create_project_modal",
        "title": {"type": "plain_text", "text": "Create DevLake Project"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "project_name_block",
                "label": {"type": "plain_text", "text": "Project Name"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "project_name_input",
                    "placeholder": {"type": "plain_text", "text": "my-project"},
                }
            },
            {"type": "divider"},
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🐙 GitHub"}
            },
            {
                "type": "input",
                "block_id": "github_token_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "GitHub Personal Access Token"},
                "hint": {
                    "type": "plain_text",
                    "text": "Use /devlake-requirements for scopes. Optional if using GitLab only."
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "github_token_input",
                    "placeholder": {"type": "plain_text", "text": "ghp_****"},
                }
            },
            {
                "type": "input",
                "block_id": "github_repos_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "GitHub Repositories"},
                "hint": {
                    "type": "plain_text",
                    "text": "One per line: owner/repo-name"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "github_repos_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "kubernetes/kubernetes\nowner/repo1\nowner/repo2"},
                }
            },
            {"type": "divider"},
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🦊 GitLab"}
            },
            {
                "type": "input",
                "block_id": "gitlab_token_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "GitLab Personal Access Token"},
                "hint": {
                    "type": "plain_text",
                    "text": "Use /devlake-requirements for scopes. Optional if using GitHub only."
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "gitlab_token_input",
                    "placeholder": {"type": "plain_text", "text": "glpat-****"},
                }
            },
            {
                "type": "input",
                "block_id": "gitlab_repos_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "GitLab Projects"},
                "hint": {
                    "type": "plain_text",
                    "text": "One per line: group/project-name"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "gitlab_repos_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "gitlab-org/gitlab\ngroup/project1\ngroup/project2"},
                }
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "schedule_block",
                "label": {"type": "plain_text", "text": "Collection Schedule"},
                "element": {
                    "type": "static_select",
                    "action_id": "schedule_select",
                    "placeholder": {"type": "plain_text", "text": "Select schedule"},
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "Daily at midnight"},
                        "value": "daily"
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Daily at midnight"},
                            "value": "daily"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Weekly (Monday)"},
                            "value": "weekly"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Every 6 hours"},
                            "value": "every_6h"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Every 12 hours"},
                            "value": "every_12h"
                        }
                    ]
                }
            }
        ]
    }


@app.command("/devlake-create-project")
def open_create_modal(ack, body, client):
    """Open modal to create a new DevLake project."""
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view=get_create_project_modal()
    )


@app.view("create_project_modal")
def handle_create_project(ack, body, client, view):
    """Handle project creation modal submission."""
    # Extract values from modal
    values = view["state"]["values"]

    # Parse GitHub data
    github_token = values["github_token_block"]["github_token_input"].get("value")
    github_repos_text = values["github_repos_block"]["github_repos_input"].get("value")
    github_repos = [r.strip() for r in github_repos_text.split("\n") if r.strip()] if github_repos_text else []

    # Parse GitLab data
    gitlab_token = values["gitlab_token_block"]["gitlab_token_input"].get("value")
    gitlab_repos_text = values["gitlab_repos_block"]["gitlab_repos_input"].get("value")
    gitlab_repos = [r.strip() for r in gitlab_repos_text.split("\n") if r.strip()] if gitlab_repos_text else []

    # Validation: at least one platform must have both token and repos
    errors = {}
    if not github_repos and not gitlab_repos:
        errors["github_repos_block"] = "At least one GitHub or GitLab repository is required"
        errors["gitlab_repos_block"] = "At least one GitHub or GitLab repository is required"
    if github_repos and not github_token:
        errors["github_token_block"] = "GitHub token required when repositories are provided"
    if gitlab_repos and not gitlab_token:
        errors["gitlab_token_block"] = "GitLab token required when projects are provided"

    if errors:
        ack(response_action="errors", errors=errors)
        return

    # Acknowledge after validation
    ack()

    # Safe data (can be logged)
    project_name = values["project_name_block"]["project_name_input"]["value"]
    schedule = values["schedule_block"]["schedule_select"]["selected_option"]["value"]

    safe_data = {
        "project": project_name,
        "github_repos": github_repos,
        "gitlab_repos": gitlab_repos,
        "schedule": schedule
    }

    logger.info(f"Creating DevLake project: {safe_data}")

    user_id = body["user"]["id"]

    # Send "working on it" message
    repo_count = len(github_repos) + len(gitlab_repos)
    client.chat_postMessage(
        channel=user_id,
        text=f"⏳ Creating project '{project_name}' with {repo_count} repositor{'y' if repo_count == 1 else 'ies'}..."
    )

    try:
        # Create project with both GitHub and GitLab repos (tokens used here then garbage collected)
        result = devlake.create_multi_platform_project(
            project_name=project_name,
            github_repos=github_repos,
            github_token=github_token,  # ⚠️ In-memory only, never stored
            gitlab_repos=gitlab_repos,
            gitlab_token=gitlab_token,  # ⚠️ In-memory only, never stored
            cron_config=CRON_SCHEDULES[schedule]
        )

        # Tokens are now out of scope and will be garbage collected

        # Build repo list for success message
        repo_list = []
        if github_repos:
            repo_list.append(f"🐙 *GitHub:* {', '.join(github_repos)}")
        if gitlab_repos:
            repo_list.append(f"🦊 *GitLab:* {', '.join(gitlab_repos)}")

        # Success message
        client.chat_postMessage(
            channel=user_id,
            text=f"✅ *Project '{result['project']}' created successfully!*\n\n"
                 f"📊 *Dashboard:* {result['dashboard_url']}\n"
                 f"🔄 *First collection started* (Pipeline ID: {result['pipeline_id']})\n"
                 f"📅 *Schedule:* {schedule}\n"
                 f"🔗 *Repositories:*\n" + "\n".join(repo_list)
        )

    except DevLakeAPIError as e:
        # DO NOT log token or full error details that might contain token
        logger.error(f"Failed to create project: {str(e)}")

        client.chat_postMessage(
            channel=user_id,
            text=f"❌ *Failed to create project*\n\n"
                 f"Error: {str(e)}\n\n"
                 f"Please check:\n"
                 f"• Tokens are valid and have required scopes\n"
                 f"• Repository names are correct (owner/repo)\n"
                 f"• Project name is unique"
        )


@app.command("/devlake-list-projects")
def list_projects(ack, say, command):
    """List existing DevLake projects with pagination."""
    ack("Fetching projects...")

    try:
        send_project_list(say, command['user_id'], page=1)
    except DevLakeAPIError as e:
        logger.error(f"Failed to list projects: {str(e)}")
        say(
            f"❌ Failed to fetch projects: {str(e)}",
            channel=command['user_id']
        )


def send_project_list(say, channel, page=1):
    """Send paginated project list with buttons."""
    page_size = 10
    projects = devlake.get_projects(page=page, page_size=page_size)

    if not projects.get('projects'):
        say("No projects found.", channel=channel)
        return

    total = projects.get('count', 0)
    showing = len(projects['projects'])
    start = (page - 1) * page_size + 1
    end = start + showing - 1

    # Build message blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 DevLake Projects ({start}-{end} of {total})"
            }
        },
        {"type": "divider"}
    ]

    # Add project list
    for project in projects['projects']:
        project_text = f"*{project['name']}*"
        if project.get('blueprint'):
            project_text += f"\n_Blueprint: {project['blueprint'].get('name', 'N/A')}_"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": project_text
            }
        })

    # Add pagination buttons
    has_more = total > page * page_size
    has_prev = page > 1

    if has_more or has_prev:
        buttons = []

        if has_prev:
            buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "⬅️ Previous"},
                "action_id": f"projects_prev_{page}",
                "value": str(page - 1)
            })

        if has_more:
            buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Show More ➡️"},
                "action_id": f"projects_next_{page}",
                "value": str(page + 1)
            })

        blocks.append({
            "type": "actions",
            "elements": buttons
        })

    say(blocks=blocks, channel=channel, text=f"DevLake Projects ({start}-{end} of {total})")


@app.action(re.compile("^projects_(next|prev)_.*"))
def handle_project_pagination(ack, body, say):
    """Handle 'Show More' and 'Previous' button clicks."""
    ack()

    action = body['actions'][0]
    page = int(action['value'])
    channel = body['user']['id']

    # Send the requested page
    send_project_list(say, channel, page=page)


@app.command("/devlake-list-all")
def list_all_projects(ack, say, command):
    """List all DevLake projects (fetches all pages)."""
    ack("Fetching all projects... this may take a moment")

    try:
        all_projects = []
        page = 1
        page_size = 50

        # Fetch all pages
        while True:
            result = devlake.get_projects(page=page, page_size=page_size)
            projects = result.get('projects', [])
            all_projects.extend(projects)

            if len(projects) < page_size:
                break  # Last page
            page += 1

        if all_projects:
            msg = f"*All DevLake Projects ({len(all_projects)} total):*\n\n"
            for project in all_projects:
                msg += f"• *{project['name']}*\n"
            msg += f"\n_Total: {len(all_projects)} projects_"
        else:
            msg = "No projects found."

        say(msg, channel=command['user_id'])

    except DevLakeAPIError as e:
        logger.error(f"Failed to list all projects: {str(e)}")
        say(
            f"❌ Failed to fetch projects: {str(e)}",
            channel=command['user_id']
        )


def get_requirements_text():
    """Get token requirements text."""
    return """
*🔐 GitHub/GitLab Token Requirements*

Before creating a DevLake project, you need a Personal Access Token (PAT) with the correct permissions.

---

*GitHub PAT Permissions:*

For *public repositories*:
• `repo:status`
• `repo_deployment`
• `read:user`
• `read:org`

For *private repositories*:
• `repo` (full repo access)
• `read:user`
• `read:org`

📖 *How to create GitHub PAT:*
<https://devlake.apache.org/docs/Configuration/GitHub|DevLake GitHub Configuration Guide>

---

*GitLab PAT Permissions:*

Required scope:
• `read_api`

⚠️ *Important:* Make sure you are NOT a Guest in the project!
• Go to Project information → Members
• Check your role in "Max role" column
• Must be Developer, Maintainer, or Owner (not Guest)

📖 *How to create GitLab PAT:*
<https://devlake.apache.org/docs/Configuration/GitLab|DevLake GitLab Configuration Guide>

---

*Creating a PAT:*

*GitHub:*
1. Go to Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Select the scopes listed above
4. Copy the token (starts with `ghp_`)

*GitLab:*
1. Go to User Settings → Access Tokens
2. Add token name, expiration, and select `read_api` scope
3. Click "Create personal access token"
4. Copy the token (starts with `glpat-`)

---

💡 *Tip:* Keep your token safe! The bot never stores it - it's sent directly to DevLake.

*Ready to create a project?* Use `/devlake-create-project`
"""


@app.command("/devlake-requirements")
def show_requirements(ack, say, command):
    """Show GitHub/GitLab token requirements."""
    ack()
    say(get_requirements_text(), channel=command['user_id'])


@app.command("/devlake-help")
def show_help(ack, say, command):
    """Show help message with available commands."""
    ack()

    help_text = get_help_text()
    say(help_text, channel=command['user_id'])


def get_help_text():
    """Get help message text."""
    return """
*FTPR DevLake Slack Bot - Help*

*Slash Commands:*

`/devlake-create-project`
Create a new DevLake project with GitHub integration.
Opens a modal to collect project details, repository, and GitHub token.

`/devlake-requirements`
Show GitHub/GitLab token requirements and how to create PATs.
⭐ *Read this before creating a project!*

`/devlake-list-projects`
List existing DevLake projects (shows 10 per page with "Show More" button).

`/devlake-list-all`
List all DevLake projects at once (may be slow if many projects).

`/devlake-help`
Show this help message.

*Chat with me:*
You can also DM me or mention me in a channel! Try:
• `@DevLake list projects`
• `@DevLake help`
• `@DevLake requirements` (token help)
• `create project` (in DM)
• `list all projects` (in DM)

*Security Note:*
Your GitHub Personal Access Token is sent directly to DevLake and is never stored by this bot. It exists in memory only during project creation (~2 seconds).

*DevLake Dashboard:*
{dashboard_url}

*Support:*
For issues or questions, contact the FTPR team.
""".format(dashboard_url=CONF['default'].get("DEVLAKE_URL"))


# Message event handlers for natural conversation

@app.event("app_mention")
def handle_mention(event, say):
    """Handle when bot is mentioned in a channel."""
    text = event.get('text', '').lower()
    user = event.get('user')

    logger.info(f"Bot mentioned by {user}: {text}")

    # Parse what the user wants
    if 'requirement' in text or ('token' in text and 'help' not in text) or 'pat' in text or 'scope' in text:
        # Show requirements
        say(get_requirements_text())
    elif 'help' in text:
        say(get_help_text())
    elif 'list' in text and 'all' in text:
        # Simulate the list-all command
        try:
            all_projects = []
            page = 1
            page_size = 50

            while True:
                result = devlake.get_projects(page=page, page_size=page_size)
                projects = result.get('projects', [])
                all_projects.extend(projects)
                if len(projects) < page_size:
                    break
                page += 1

            if all_projects:
                msg = f"*All DevLake Projects ({len(all_projects)} total):*\n\n"
                for project in all_projects:
                    msg += f"• *{project['name']}*\n"
                msg += f"\n_Total: {len(all_projects)} projects_"
            else:
                msg = "No projects found."

            say(msg)
        except DevLakeAPIError as e:
            say(f"❌ Failed to fetch projects: {str(e)}")
    elif 'list' in text or 'projects' in text:
        # Use the paginated list with buttons
        try:
            channel = event.get('channel')
            send_project_list(say, channel, page=1)
        except DevLakeAPIError as e:
            say(f"❌ Failed to fetch projects: {str(e)}")
    elif 'create' in text or 'new project' in text:
        say(
            "To create a new project, use the `/devlake-create-project` command!\n"
            "It will open a form where you can enter project details."
        )
    else:
        say(
            f"Hey <@{user}>! 👋\n\n"
            "I can help you manage DevLake projects!\n\n"
            "Try:\n"
            "• `@DevLake list projects`\n"
            "• `@DevLake help`\n"
            "• Or use `/devlake-help` to see all commands"
        )


@app.event("message")
def handle_direct_message(event, say):
    """Handle direct messages to the bot."""
    # Only respond to DMs (not channel messages)
    channel_type = event.get('channel_type')
    if channel_type != 'im':
        return  # Ignore channel messages (only DMs)

    # Ignore bot messages to avoid loops
    if event.get('subtype') == 'bot_message':
        return

    text = event.get('text', '').lower()
    user = event.get('user')

    logger.info(f"DM from {user}: {text}")

    # Parse what the user wants
    if 'requirement' in text or ('token' in text and 'help' not in text) or 'pat' in text or 'scope' in text:
        # Show requirements
        say(get_requirements_text())
    elif 'help' in text or text in ['hi', 'hello', 'hey']:
        say(get_help_text())
    elif 'list' in text and 'all' in text:
        # List all projects
        try:
            all_projects = []
            page = 1
            page_size = 50

            while True:
                result = devlake.get_projects(page=page, page_size=page_size)
                projects = result.get('projects', [])
                all_projects.extend(projects)
                if len(projects) < page_size:
                    break
                page += 1

            if all_projects:
                msg = f"*All DevLake Projects ({len(all_projects)} total):*\n\n"
                for project in all_projects:
                    msg += f"• *{project['name']}*\n"
                msg += f"\n_Total: {len(all_projects)} projects_"
            else:
                msg = "No projects found."

            say(msg)
        except DevLakeAPIError as e:
            say(f"❌ Failed to fetch projects: {str(e)}")
    elif 'list' in text or 'projects' in text:
        # Use the paginated list with buttons
        try:
            channel = event.get('channel')
            send_project_list(say, channel, page=1)
        except DevLakeAPIError as e:
            say(f"❌ Failed to fetch projects: {str(e)}")
    elif 'create' in text or 'new project' in text:
        say(
            "To create a new project, use the `/devlake-create-project` command!\n"
            "It will open a form where you can enter project details."
        )
    else:
        say(
            "👋 Hi! I'm the DevLake bot.\n\n"
            "I can help you:\n"
            "• Create DevLake projects\n"
            "• List existing projects\n\n"
            "Try typing:\n"
            "• `list projects`\n"
            "• `list all projects`\n"
            "• `help`\n"
            "• Or use `/devlake-help` for all commands"
        )


def main():
    """Start the Slack bot."""
    logger.info("Starting FTPR Slack Bot...")
    logger.info(f"DevLake URL: {CONF['default'].get('DEVLAKE_URL')}")

    handler = SocketModeHandler(app, CONF['default'].get("SLACK_APP_TOKEN"))
    handler.start()


if __name__ == "__main__":
    main()
