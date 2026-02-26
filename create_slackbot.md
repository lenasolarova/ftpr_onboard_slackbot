# Creating the Slack App for FTPR DevLake Bot

This guide shows you how to create and configure the Slack app from scratch.

## Step 1: Create the Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. **App Name:** `DevLake Project Creator` (or your preferred name)
4. **Workspace:** Choose your workspace
5. Click **"Create App"**

## Step 2: Enable Socket Mode

Socket Mode allows the bot to run locally or behind a firewall without needing a public URL.

1. Go to **Settings → Socket Mode**
2. Toggle **"Enable Socket Mode"** to **ON**
3. Click **"Generate an App-Level Token"**
   - **Token Name:** `socket-token`
   - **Scopes:** Select `connections:write`
4. Click **"Generate"**
5. **Copy the token** (starts with `xapp-`) - this is your `SLACK_APP_TOKEN`
6. Click **"Done"**

## Step 3: Add Bot Token Scopes

1. Go to **OAuth & Permissions**
2. Scroll to **"Scopes"** → **"Bot Token Scopes"**
3. Click **"Add an OAuth Scope"** and add these scopes:

   - `app_mentions:read` - Read messages that mention the bot
   - `chat:write` - Send messages
   - `commands` - Use slash commands
   - `im:history` - Read DM history
   - `im:read` - View DM info
   - `im:write` - Send DMs
   - `users:read` - Get user info

## Step 4: Install App to Workspace

1. Still on **OAuth & Permissions** page
2. Scroll to the top
3. Click **"Install to Workspace"** (or "Reinstall to Workspace" if you added new scopes)
4. Click **"Allow"**
5. **Copy the "Bot User OAuth Token"** (starts with `xoxb-`) - this is your `SLACK_BOT_TOKEN`

## Step 5: Create Slash Commands

1. Go to **Slash Commands**
2. Click **"Create New Command"** for each command below:

**Command 1:**
```
Command: /devlake-create-project
Short Description: Create a new DevLake project
Usage Hint: (opens a modal)
```

**Command 2:**
```
Command: /devlake-add-repos
Short Description: Add repos to an existing connection
Usage Hint: (opens a modal)
```

**Command 3:**
```
Command: /devlake-list-projects
Short Description: List DevLake projects with pagination
Usage Hint: (shows 10 per page with buttons)
```

**Command 4:**
```
Command: /devlake-list-all
Short Description: List all DevLake projects
Usage Hint: (may be slow if many projects)
```

**Command 5:**
```
Command: /devlake-requirements
Short Description: Show GitHub/GitLab token requirements
Usage Hint: (displays required PAT scopes)
```

**Command 6:**
```
Command: /devlake-help
Short Description: Show help and available commands
```

3. Click **"Save"** after each command

## Step 6: Enable Event Subscriptions

1. Go to **Event Subscriptions**
2. Toggle **"Enable Events"** to **ON**
3. Under **"Subscribe to bot events"**, click **"Add Bot User Event"** and add:
   - `app_mention` - When someone @mentions the bot
   - `message.im` - Messages in DMs with the bot
4. Click **"Save Changes"**

## Step 7: Enable Messages Tab

This allows users to DM the bot directly.

1. Go to **App Home**
2. Scroll to **"Show Tabs"**
3. Toggle **"Messages Tab"** to **ON**
4. Check the box: **"Allow users to send Slash commands and messages from the messages tab"**
5. Click **"Save Changes"**

## Step 8: Get Your Tokens

You should now have both tokens:

**Bot Token** (`SLACK_BOT_TOKEN`):
```
xoxb-...
```
Found at: OAuth & Permissions → Bot User OAuth Token

**App Token** (`SLACK_APP_TOKEN`):
```
xapp-...
```
Found at: Basic Information → App-Level Tokens

⚠️ **Keep these tokens secure!** Don't commit them to git.

## Step 9: Configure the Bot

Set environment variables:
```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"
export SLACK_APP_TOKEN="xapp-your-app-token-here"
export DEVLAKE_URL="https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"
```

Or create `~/.config/ftpr_slack_bot.toml`:
```toml
[default]
SLACK_BOT_TOKEN = "xoxb-your-bot-token-here"
SLACK_APP_TOKEN = "xapp-your-app-token-here"
DEVLAKE_URL = "https://konflux-devlake-ui-konflux-devlake.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com"
```

## Step 10: Run the Bot

```bash
# Local
ftpr-slack-bot

# Or in container
podman run --rm \
  -e SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN" \
  -e SLACK_APP_TOKEN="$SLACK_APP_TOKEN" \
  -e DEVLAKE_URL="$DEVLAKE_URL" \
  ftpr-slack-bot:latest
```

You should see:
```
INFO - Starting FTPR Slack Bot...
INFO - ⚡️ Bolt app is running!
INFO - Starting to receive messages from a new connection
```

## Step 11: Test in Slack

1. **Find the bot** in your Slack workspace (Apps section)
2. **DM the bot:** Type `hi` or `help`
3. **Try a command:** `/devlake-help`
4. **Mention in channel:** `@YourBot list projects`

If everything works, you're done! 🎉

## Troubleshooting

**Bot doesn't respond:**
- Check logs for errors
- Verify both tokens are set correctly
- Make sure Socket Mode is enabled

**"not_authed" error:**
- SLACK_BOT_TOKEN is invalid or missing
- Reinstall the app to workspace

**"dispatch_failed" error:**
- Socket Mode not enabled
- App-Level Token doesn't have `connections:write` scope

**Slash commands don't show up:**
- Wait 5-10 minutes for Slack to sync
- Try typing `/devlake` to see if autocomplete shows your commands

**Bot can't see DMs:**
- Messages Tab not enabled in App Home
- Missing `im:history` or `message.im` permissions
