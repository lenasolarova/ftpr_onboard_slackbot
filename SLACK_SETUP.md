# Slack App Setup Guide

This guide shows how to configure your Slack app to support both slash commands and natural conversation (DMs and mentions).

## Step 1: Update Bot Scopes

Go to https://api.slack.com/apps → Select your app → **OAuth & Permissions** → **Bot Token Scopes**

Add these scopes:
- ✅ `app_mentions:read` - Read messages that mention your bot
- ✅ `chat:write` - Send messages
- ✅ `commands` - Use slash commands
- ✅ `im:history` - Read DM history
- ✅ `im:read` - View DM info
- ✅ `im:write` - Send DMs
- ✅ `users:read` - Get user info

**After adding scopes, you MUST reinstall the app:**
- Click "Reinstall to Workspace" button at the top
- Authorize the new permissions

## Step 2: Enable Event Subscriptions

Go to **Event Subscriptions** → Toggle **Enable Events** to **On**

You'll see "Request URL" - leave it empty (we're using Socket Mode)

**Subscribe to bot events:**
Click "Subscribe to bot events" and add:
- ✅ `app_mention` - When someone mentions @YourBot
- ✅ `message.im` - Messages in DMs with your bot

Click **Save Changes**

## Step 3: Verify Socket Mode

Go to **Socket Mode** → Verify it's **Enabled**

If not:
1. Toggle Socket Mode to **On**
2. Generate an App-Level Token
3. Name it: `socket-token`
4. Scope: `connections:write`
5. Copy the `xapp-...` token (this is your `SLACK_APP_TOKEN`)

## Step 4: Add New Slash Command

Go to **Slash Commands** → **Create New Command**

Add the `/devlake-list-all` command:
```
Command: /devlake-list-all
Description: List all DevLake projects
Usage Hint: (fetches all pages)
```

## Step 5: Test the Bot

### Test DMs:
1. Open Slack
2. Find your bot under "Apps" in the left sidebar
3. Click on it to open a DM
4. Type: `hi` or `list projects`
5. Bot should respond!

### Test Mentions in Channel:
1. Go to any channel (or create `#devlake-testing`)
2. Invite the bot: `/invite @DevLake`
3. Mention it: `@DevLake list projects`
4. Bot should respond!

### Test Slash Commands:
1. Type: `/devlake-help`
2. Type: `/devlake-list-projects`
3. Should work as before!

## Conversation Examples

**In DM:**
```
You: hi
Bot: 👋 Hi! I'm the DevLake bot...

You: list projects
Bot: *DevLake Projects:*
     • project-1
     • project-2
     ...

You: list all projects
Bot: *All DevLake Projects (37 total):*
     ...

You: create project
Bot: To create a new project, use /devlake-create-project...
```

**In Channel:**
```
You: @DevLake list projects
Bot: *DevLake Projects:*
     ...

You: @DevLake help
Bot: *FTPR DevLake Slack Bot - Help*
     ...
```

## Restrict to One Channel (Optional)

If you want the bot to only respond in one specific channel + DMs:

1. **Get the channel ID:**
   - Right-click the channel → View channel details
   - Scroll down, copy the Channel ID (e.g., `C12345678`)

2. **Update config:**
   Edit `~/.config/ftpr_slack_bot.toml`:
   ```toml
   ALLOWED_CHANNEL = "C12345678"
   ```

3. **Restart bot:**
   - Stop bot (Ctrl+C)
   - Start: `ftpr-slack-bot`

Now the bot will only respond to:
- DMs
- Messages in that specific channel

## Troubleshooting

**Bot doesn't respond to DMs:**
- Check `message.im` event is subscribed
- Verify `im:history` and `im:read` scopes are added
- Reinstall the app after adding scopes

**Bot doesn't respond to mentions:**
- Check `app_mention` event is subscribed
- Verify `app_mentions:read` scope is added
- Make sure you're mentioning with @BotName (not just typing the name)

**"dispatch_failed" error:**
- Ensure Socket Mode is enabled
- Verify App-Level Token has `connections:write` scope
- Try regenerating the App-Level Token

**Bot responds twice:**
- Make sure you don't have the bot running in two places
- Check: `ps aux | grep ftpr-slack-bot`
- Kill duplicates: `pkill -f ftpr-slack-bot`

## Next Steps

Once everything works:
1. Deploy to Kubernetes for production (see main README.md)
2. Set up monitoring/logging
3. Configure allowed channels if needed
4. Share with your team!
