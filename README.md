# FTPR Slack Bot for DevLake

Slack bot for creating and managing DevLake projects directly from Slack.

## Features

- 🚀 Create DevLake projects via interactive modal
- 📊 List and browse projects with button pagination
- 💬 Natural conversation (DMs and @mentions)
- 🔐 Secure token handling (PATs never stored)
- 📖 Built-in documentation for GitHub/GitLab token requirements

## Quick Start

### 1. Installation

```bash
# Clone and setup
git clone git@github.com:lenasolarova/ftpr_onboard_slackbot.git
cd ftpr_onboard_slackbot

# Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install .
```

### 2. Configure

Set environment variables:
```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export DEVLAKE_URL="https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"
```

Or create `~/.config/ftpr_slack_bot.toml`:
```toml
[default]
DEVLAKE_URL = "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"
SLACK_BOT_TOKEN = "xoxb-your-bot-token"
SLACK_APP_TOKEN = "xapp-your-app-token"
```

### 3. Slack App Setup

You need to create a Slack app and get two tokens (`SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`).

📖 **Full setup guide:** [create_slackbot.md](create_slackbot.md)

The guide walks you through:
- Creating the Slack app with correct scopes and permissions
- Enabling Socket Mode and getting your tokens
- Setting up slash commands and event subscriptions
- Enabling the Messages Tab for DMs

### 4. Run

```bash
ftpr-slack-bot
```

## Usage

### Slash Commands

```
/devlake-create-project          # Opens modal to create project
/devlake-requirements            # Shows GitHub/GitLab PAT requirements
/devlake-list-projects           # Lists projects (10 per page with buttons)
/devlake-list-all                # Lists all projects
/devlake-help                    # Shows help
```

### Natural Chat

**In DM:**
```
You: hi
Bot: (shows help)

You: list projects
Bot: (shows paginated list with buttons)

You: requirements
Bot: (shows token requirements)
```

**In Channel:**
```
You: @BotName list projects
Bot: (shows projects)

You: @BotName requirements
Bot: (shows token requirements)
```

## Token Requirements

Before creating a project, you need a GitHub or GitLab Personal Access Token (PAT).

**GitHub (public repos):**
- `repo:status`, `repo_deployment`, `read:user`, `read:org`

**GitHub (private repos):**
- `repo`, `read:user`, `read:org`

**GitLab:**
- `read_api` (and you must not be a Guest in the project)

📖 Details: Use `/devlake-requirements` command in Slack

## Security

- ✅ PATs are **never stored** by the bot
- ✅ Tokens exist in memory only during API calls (~2 seconds)
- ✅ All communication over HTTPS/TLS
- ✅ Read-only filesystem in Kubernetes pods
- ✅ Network policies restrict egress

## Deployment

### Kubernetes

Update secrets in `etc/kubernetes/deployment.yaml`, then:

```bash
# Build and push image
podman build -t quay.io/your-org/ftpr-slack-bot:latest .
podman push quay.io/your-org/ftpr-slack-bot:latest

# Deploy
kubectl apply -f etc/kubernetes/deployment.yaml
```

See `etc/kubernetes/deployment.yaml` for full configuration including security contexts and network policies.

## Architecture

```
User → Slack → Bot (in-memory PAT) → DevLake API
                ↓
           PostgreSQL
```

**Workflow:**
1. User fills modal with project info + PAT
2. Bot receives submission
3. Bot makes 4 sequential API calls to DevLake:
   - Create GitHub connection (PAT sent here)
   - Add repository scope
   - Create project with blueprint
   - Trigger initial pipeline
4. PAT is garbage collected
5. User receives success/error message

## Project Structure

```
ftpr_slack_bot/
├── ftpr_slack_bot/
│   ├── slack_bot.py              # Main bot (commands, handlers, modals)
│   └── common/
│       ├── config.py             # TOML config loader
│       └── devlake_api.py        # DevLake REST API client
├── etc/
│   ├── config/
│   │   └── ftpr_slack_bot.toml   # Config template
│   └── kubernetes/
│       └── deployment.yaml       # K8s manifests
├── Dockerfile
├── requirements.txt
├── setup.py
└── setup.cfg
```

## DevLake Dashboard

https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com

## Support

For issues or questions, contact the FTPR team or open an issue on GitHub.

## License

Apache 2.0
