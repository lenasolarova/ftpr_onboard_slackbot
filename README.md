# FTPR Slack Bot for DevLake Integration

A Slack bot that allows users to create DevLake projects, connections, and scopes through a single modal interface with secure token handling.

## Overview

This bot enables users to set up DevLake data collection pipelines for GitHub repositories directly from Slack, without storing sensitive GitHub Personal Access Tokens (PATs).

**DevLake Instance:**
```
https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com
```

## Installation

### From Source

```bash
# Clone the repository
git clone <repo-url> ftpr-slack-bot
cd ftpr-slack-bot

# Create virtual environment
python3 -m venv ~/.local/share/ftpr-slack-bot
source ~/.local/share/ftpr-slack-bot/bin/activate

# Install dependencies and package
pip install -r requirements.txt
pip install .
```

### Configuration

Create configuration file:
```bash
mkdir -p ~/.config
cp etc/config/ftpr_slack_bot.toml ~/.config/
```

Edit `~/.config/ftpr_slack_bot.toml` with your tokens:
```toml
[default]
DEVLAKE_URL = "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"
SLACK_BOT_TOKEN = "xoxb-your-bot-token"
SLACK_APP_TOKEN = "xapp-your-app-token"
```

Alternatively, use environment variables:
```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export DEVLAKE_URL="https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"
```

### Kubernetes Deployment

For production deployment in Kubernetes:

```bash
# Update secrets in etc/kubernetes/deployment.yaml
# Then apply:
kubectl apply -f etc/kubernetes/deployment.yaml
```

Or build and deploy with a container:

```bash
# Build container
podman build -t quay.io/ftpr/slack-bot:latest .

# Push to registry
podman push quay.io/ftpr/slack-bot:latest

# Deploy to Kubernetes
kubectl apply -f etc/kubernetes/deployment.yaml
```

## Usage

### Running the Bot

**Local development:**
```bash
# Activate virtual environment
source ~/.local/share/ftpr-slack-bot/bin/activate

# Run bot
ftpr-slack-bot

# With custom config
ftpr-slack-bot --config_file /path/to/config.toml
```

**As a service (Kubernetes):**
The bot runs as a deployment in the cluster and automatically reconnects if disconnected.

### Slack Commands

**`/devlake-create-project`**
Opens a modal to create a new DevLake project. Collects:
- Project name
- GitHub repository (owner/repo format)
- GitHub Personal Access Token
- Collection schedule (daily, weekly, etc.)

**`/devlake-list-projects`**
Lists existing DevLake projects (shows up to 10 most recent).

**`/devlake-help`**
Shows help message with available commands.

## Package Structure

```
ftpr_slack_bot/
├── ftpr_slack_bot/
│   ├── __init__.py
│   ├── slack_bot.py           # Main Slack bot with commands
│   └── common/
│       ├── __init__.py
│       ├── config.py           # Configuration loader (TOML)
│       └── devlake_api.py     # DevLake API client
├── etc/
│   ├── config/
│   │   └── ftpr_slack_bot.toml  # Config template
│   └── kubernetes/
│       └── deployment.yaml      # K8s manifests
├── setup.py                     # Package setup (pbr)
├── setup.cfg                    # Package metadata
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container build
└── README.md                    # This file
```

## Architecture

### User Flow

```
User: /create-project
  ↓
Single Modal (collects all info)
  ↓
User submits (editable until submit)
  ↓
Bot makes sequential POSTs:
  1. Create GitHub connection
  2. Add repository scope
  3. Create project with blueprint
  4. Trigger initial pipeline
  ↓
Success/Error message to user
```

### Security Design

**Token Flow:**
```
User types PAT in Slack
  ↓ HTTPS (encrypted)
Slack servers
  ↓ HTTPS webhook (encrypted)
Python bot pod (in-memory only, ~2 seconds)
  ↓ HTTPS (encrypted)
DevLake API (persisted for GitHub API calls)
```

**Key Security Features:**
- ✅ PAT never stored in bot database/cache/logs
- ✅ In-memory variable only during POST sequence
- ✅ HTTPS/TLS for all transit
- ✅ Garbage collected after function completes
- ✅ No logging of sensitive values
- ✅ Read-only pod filesystem
- ✅ NetworkPolicy restricts pod egress

## Modal Design

### Single Modal with All Fields

```
┌─────────────────────────────────────┐
│ Create DevLake Project              │
├─────────────────────────────────────┤
│ GitHub Token (PAT):                 │
│ [ghp_**********************]        │  ← User can edit before submit
│                                     │
│ Repository (owner/repo):            │
│ [konflux-ci/quality-dashboard]      │
│                                     │
│ Project Name:                       │
│ [my-project]                        │
│                                     │
│ Collection Schedule:                │
│ [Dropdown: Daily/Weekly/Custom]     │
│                                     │
│ [Cancel] [Create Project]           │
└─────────────────────────────────────┘
```

**Benefits:**
- User can edit all fields before submission
- No intermediate storage of PAT
- All validation happens on submit
- Simple UX - one form, one submit

## DevLake API Integration

### Sequential POST Workflow

The bot makes 3-4 API calls in sequence:

#### 1. Create GitHub Connection
```bash
POST /api/plugins/github/connections
{
  "name": "user-connection-name",
  "endpoint": "https://api.github.com/",
  "authMethod": "AccessToken",
  "token": "ghp_xxx",  # PAT from user
  "enableGraphql": true
}

Response: {"id": 11, "name": "user-connection-name", ...}
```

#### 2. Add Repository Scope
```bash
PUT /api/plugins/github/connections/11/scopes
[{
  "fullName": "owner/repo-name"
}]

Response: {"scopes": [{"githubId": 3638964, ...}]}
```

#### 3. Create Project with Blueprint
```bash
POST /api/projects
{
  "name": "my-project",
  "enable": true,
  "metrics": [
    {"pluginName": "dora", "enable": true},
    {"pluginName": "issue_trace", "enable": true}
  ],
  "blueprint": {
    "name": "my-project-Blueprint",
    "projectName": "my-project",
    "mode": "NORMAL",
    "enable": true,
    "cronConfig": "0 0 * * *",  # Daily at midnight
    "plan": [[
      {
        "plugin": "github",
        "options": {
          "connectionId": 11,
          "githubId": 3638964
        }
      }
    ]]
  }
}

Response: {"name": "my-project", "blueprint": {...}}
```

#### 4. Trigger Initial Pipeline (Optional)
```bash
POST /api/blueprints/{blueprintId}/trigger

Response: {"pipelineId": 2055, ...}
```

## Implementation Example

### Modal Submission Handler

```python
import requests
from slack_bolt import App

DEVLAKE_URL = "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"

@app.view("project_creation_modal")
def handle_submission(ack, body, client):
    ack()

    # Extract values from modal
    values = body["view"]["state"]["values"]

    # Safe data (can be logged)
    safe_data = {
        "repo": values["repo_block"]["repo_input"]["value"],
        "project": values["name_block"]["name_input"]["value"],
        "schedule": values["schedule_block"]["schedule_select"]["selected_option"]["value"]
    }
    logger.info(f"Creating project: {safe_data}")  # ✅ No token

    # Sensitive data (never logged)
    github_token = values["token_block"]["token_input"]["value"]

    user_id = body["user"]["id"]

    # Send "working on it" message
    client.chat_postMessage(
        channel=user_id,
        text=f"⏳ Creating project '{safe_data['project']}'..."
    )

    try:
        # 1. Create connection
        conn_resp = requests.post(
            f"{DEVLAKE_URL}/api/plugins/github/connections",
            json={
                "name": f"{safe_data['project']}-connection",
                "endpoint": "https://api.github.com/",
                "authMethod": "AccessToken",
                "token": github_token,  # ⚠️ Only use here
                "enableGraphql": True
            },
            timeout=30
        )
        conn_resp.raise_for_status()
        conn_id = conn_resp.json()["id"]

        # Token no longer needed - out of scope after this function!

        # 2. Add scope
        scope_resp = requests.put(
            f"{DEVLAKE_URL}/api/plugins/github/connections/{conn_id}/scopes",
            json=[{"fullName": safe_data["repo"]}],
            timeout=30
        )
        scope_resp.raise_for_status()
        github_id = scope_resp.json()["scopes"][0]["scope"]["githubId"]

        # 3. Create project
        project_resp = requests.post(
            f"{DEVLAKE_URL}/api/projects",
            json={
                "name": safe_data["project"],
                "enable": True,
                "metrics": [
                    {"pluginName": "dora", "enable": True},
                    {"pluginName": "issue_trace", "enable": True}
                ],
                "blueprint": {
                    "name": f"{safe_data['project']}-Blueprint",
                    "projectName": safe_data["project"],
                    "mode": "NORMAL",
                    "enable": True,
                    "cronConfig": safe_data["schedule"],
                    "plan": [[{
                        "plugin": "github",
                        "options": {
                            "connectionId": conn_id,
                            "githubId": github_id
                        }
                    }]]
                }
            },
            timeout=30
        )
        project_resp.raise_for_status()
        blueprint_id = project_resp.json()["blueprint"]["id"]

        # 4. Trigger initial pipeline
        trigger_resp = requests.post(
            f"{DEVLAKE_URL}/api/blueprints/{blueprint_id}/trigger",
            timeout=30
        )
        trigger_resp.raise_for_status()

        # Success!
        client.chat_postMessage(
            channel=user_id,
            text=f"✅ Project '{safe_data['project']}' created successfully!\n"
                 f"📊 View dashboard: {DEVLAKE_URL}\n"
                 f"🔄 First data collection started"
        )

    except requests.exceptions.RequestException as e:
        # DON'T log token or full request body!
        logger.error(f"DevLake API error: {str(e)}")  # ✅ Safe

        client.chat_postMessage(
            channel=user_id,
            text=f"❌ Failed to create project: {str(e)}\n"
                 f"Please check your GitHub token and repository name."
        )
```

### Security Best Practices

```python
# ✅ GOOD - Sanitize logging
safe_values = {k: v for k, v in values.items() if "token" not in k.lower()}
logger.info(f"Creating project: {safe_values}")

# ❌ BAD - Token in logs
logger.info(f"Creating with data: {values}")  # Contains token!

# ✅ GOOD - Explicit cleanup (though Python GC handles this)
try:
    github_token = values["token_block"]["token_input"]["value"]
    conn = requests.post(...)
finally:
    github_token = None
    del github_token

# ❌ BAD - Token in error messages
except Exception as e:
    logger.error(f"Failed with token {github_token}: {e}")  # Exposed!

# ✅ GOOD - Generic error without sensitive data
except Exception as e:
    logger.error(f"API call failed: {str(e)}")
```

## Kubernetes Deployment

### Pod Security

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: slack-bot
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: slack-bot
    image: slack-bot:latest
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      readOnlyRootFilesystem: true  # Prevent writing PAT to disk
    env:
    - name: DEVLAKE_URL
      value: "https://devlake-service.devlake-namespace.svc.cluster.local"
    - name: SLACK_BOT_TOKEN
      valueFrom:
        secretKeyRef:
          name: slack-credentials
          key: bot-token
    volumeMounts:
    - name: tmp
      mountPath: /tmp  # For Python temp files
  volumes:
  - name: tmp
    emptyDir: {}
```

### Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: slack-bot-egress
  namespace: slack-bot
spec:
  podSelector:
    matchLabels:
      app: slack-bot
  policyTypes:
  - Egress
  egress:
  # Allow to DevLake only
  - to:
    - podSelector:
        matchLabels:
          app: devlake
    ports:
    - protocol: TCP
      port: 8080
  # Allow to Slack API
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

## DevLake API Reference

### Base URL
```
https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com/api
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/version` | Check API version |
| GET | `/projects` | List all projects |
| POST | `/projects` | Create project with blueprint |
| GET | `/plugins/github/connections/:id` | Get connection details |
| POST | `/plugins/github/connections` | Create GitHub connection |
| PUT | `/plugins/github/connections/:id/scopes` | Add repository scopes |
| GET | `/plugins/github/connections/:id/scopes` | List repository scopes |
| POST | `/blueprints` | Create blueprint (schedule) |
| POST | `/blueprints/:id/trigger` | Trigger blueprint pipeline |
| GET | `/pipelines` | List pipelines |
| POST | `/pipelines` | Create and run pipeline |

### Response Format

All responses follow this structure:
```json
{
  "success": true,
  "message": "success",
  "data": {}
}
```

### Cron Schedule Format

```
"cronConfig": "M H D M WD"

M  - Minute (0-59)
H  - Hour (0-23)
D  - Day of month (1-31)
M  - Month (1-12)
WD - Day of week (0-6, Sunday=0)

Examples:
"0 0 * * *"   - Daily at midnight
"0 0 * * 1"   - Weekly on Monday at midnight
"0 */6 * * *" - Every 6 hours
```

## Testing

### Test GET Access (No Auth Required)
```bash
curl -s "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com/api/version"
# Response: {"version":"@"}

curl -s "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com/api/projects?page=1&pageSize=5"
# Response: {"projects": [...], "count": 10}
```

### Test POST Pipeline
```bash
curl -X POST \
  "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com/api/pipelines" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Pipeline",
    "plan": [[{
      "plugin": "github",
      "options": {
        "connectionId": 11,
        "githubId": 3638964
      }
    }]]
  }'
# Response: {"id": 2055, "status": "TASK_CREATED", ...}
```

## Next Steps

1. [ ] Set up Slack app and get bot token
2. [ ] Implement modal view definition
3. [ ] Implement submission handler with sequential POSTs
4. [ ] Add error handling and validation
5. [ ] Deploy to Kubernetes cluster
6. [ ] Configure NetworkPolicy and SecurityContext
7. [ ] Set up monitoring/logging (with sensitive data filtering)
8. [ ] Test end-to-end flow

## References

- [DevLake API Documentation](https://devlake.apache.org/docs/Overview/Architecture)
- [Slack Bolt Python Framework](https://slack.dev/bolt-python/)
- [Slack Modals Documentation](https://api.slack.com/surfaces/modals)
- [GitHub PAT Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)

## License

Apache 2.0
