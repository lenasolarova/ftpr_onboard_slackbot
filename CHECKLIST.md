# Setup Checklist for DM/Mention Support

## ✅ Step 1: Update Slack App Permissions (CRITICAL!)

Go to: https://api.slack.com/apps → Your App → **OAuth & Permissions**

### Add These Scopes:
- [ ] `app_mentions:read` - Read when bot is @mentioned
- [ ] `im:history` - Read DM messages
- [ ] `im:read` - Access DM info
- [ ] `im:write` - Send DMs (should already have this)
- [ ] `chat:write` - Send messages (should already have this)
- [ ] `commands` - Slash commands (should already have this)

### After Adding Scopes:
- [ ] Click "Reinstall to Workspace" at the top of the page
- [ ] Authorize the new permissions

**WITHOUT THIS STEP, DMs AND MENTIONS WON'T WORK!**

---

## ✅ Step 2: Enable Event Subscriptions

Go to: **Event Subscriptions** → Toggle **On**

### Subscribe to Bot Events:
- [ ] `app_mention` - When someone @mentions the bot
- [ ] `message.im` - DM messages to bot

### Save:
- [ ] Click "Save Changes" at the bottom

---

## ✅ Step 3: Update Local Code

```bash
cd ~/Documents/ftpr_slack_bot
source venv/bin/activate
pip uninstall -y ftpr-slack-bot
pip install -e .
```

---

## ✅ Step 4: Restart Bot

```bash
# Stop the bot (Ctrl+C)
# Start it again:
cd ~/Documents/ftpr_slack_bot
source venv/bin/activate
ftpr-slack-bot
```

You should see:
```
INFO - Using CA bundle: ...
INFO - Starting FTPR Slack Bot...
INFO - Starting to receive messages from a new connection
```

---

## ✅ Step 5: Test in Slack

### Test DM:
1. Find bot in Apps sidebar
2. Click to open DM
3. Type: `hi`
4. Bot should respond!

### Test Mention in Channel:
1. Go to a channel
2. Type: `@DevLake list projects` (use actual bot name)
3. Bot should respond!

### If nothing works:
- Check Slack app logs: https://api.slack.com/apps → Your App → Event Subscriptions → scroll to "Recent Events"
- Look for errors

---

## Common Issues:

**Bot doesn't respond to DM:**
- Did you add `im:history` and `message.im`?
- Did you reinstall the app after adding scopes?

**Bot doesn't respond to @mentions:**
- Did you add `app_mentions:read` and `app_mention`?
- Are you using @BotName (not just typing the name)?

**"insufficient_scope" error:**
- You forgot to reinstall the app after adding scopes!
- Go to OAuth & Permissions → Reinstall to Workspace

**Bot responds to commands but not DMs:**
- Event Subscriptions not enabled
- Or `message.im` event not subscribed
