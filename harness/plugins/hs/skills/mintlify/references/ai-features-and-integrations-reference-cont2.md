# AI Features and Integrations Reference (continued 3/3)

## Slack Bot

AI assistant for Slack workspaces.

### Setup

1. **Enable Integration:**
   - Go to Mintlify dashboard
   - Navigate to Integrations > Slack
   - Click "Add to Slack"

2. **Authorize:**
   - Select workspace
   - Approve permissions
   - Configure channels

3. **Configuration:**
   ```json
   {
     "integrations": {
       "slack": {
         "enabled": true,
         "channels": ["#engineering", "#support"],
         "notifyUpdates": true,
         "dailyDigest": true
       }
     }
   }
   ```

### Usage

**Ask Questions:**
```
@DocsBot How do I authenticate API requests?
@DocsBot Show me user creation example
@DocsBot What's the rate limit for /users endpoint?
```

**Search:**
```
/docs search webhooks
/docs find deployment guide
```

**Get Updates:**
```
/docs subscribe api-updates
/docs notifications on
```

### Features

- Conversational interface
- Code snippet formatting
- Direct message support
- Channel subscriptions
- Documentation update notifications
- Daily digest summaries

## Agent Automation

AI agent for automated doc tasks.

### Configuration

```json
{
  "ai": {
    "agent": {
      "enabled": true,
      "capabilities": [
        "suggest-improvements",
        "detect-outdated",
        "generate-examples",
        "fix-broken-links"
      ],
      "schedule": "daily",
      "notifications": {
        "slack": "#docs-updates",
        "email": "team@example.com"
      }
    }
  }
}
```

### Capabilities

**Suggest Improvements:**
- Identify unclear explanations
- Suggest better wording
- Recommend additional examples
- Highlight missing sections

**Detect Outdated Content:**
- Compare with codebase
- Check API version compatibility
- Flag deprecated features
- Identify stale examples

**Generate Examples:**
- Auto-generate code examples
- Create usage scenarios
- Build tutorial content
- Produce troubleshooting guides

**Fix Broken Links:**
- Scan for 404s
- Update redirected URLs
- Fix internal references
- Validate external links

### Slack Integration

Receive agent suggestions in Slack:

```
Agent Report - Daily Digest

Suggestions (3):
- Add Python example to /api/authentication
- Update rate limits in /api/overview (changed in v2.5)
- Clarify webhook signature verification in /webhooks

Broken Links (1):
- /guides/deployment links to removed page /setup

Outdated Content (2):
- /api/users references deprecated `user_type` field
- /quickstart shows old authentication method
```

### Workflow Automation

Configure automated workflows:

```json
{
  "ai": {
    "workflows": [
      {
        "name": "Weekly Review",
        "trigger": "schedule",
        "schedule": "0 9 * * MON",
        "actions": [
          "detect-outdated",
          "broken-links",
          "suggest-improvements"
        ],
        "output": "slack"
      },
      {
        "name": "PR Review",
        "trigger": "pull_request",
        "actions": [
          "validate-changes",
          "suggest-examples",
          "check-consistency"
        ],
        "output": "github"
      }
    ]
  }
}
```

## AI API Access

Programmatic access to AI features.

### Endpoints

**Search:**
```bash
curl -X POST https://api.mintlify.com/v1/ai/search \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I authenticate?",
    "scope": "api"
  }'
```

**Ask Question:**
```bash
curl -X POST https://api.mintlify.com/v1/ai/ask \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the rate limits?",
    "context": ["api/overview", "api/rate-limits"]
  }'
```

**Generate Example:**
```bash
curl -X POST https://api.mintlify.com/v1/ai/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "code_example",
    "endpoint": "POST /users",
    "language": "python"
  }'
```

### SDK Usage

**JavaScript:**
```javascript
import { MintlifyAI } from '@mintlify/ai';

const ai = new MintlifyAI({ apiKey: 'YOUR_API_KEY' });

const answer = await ai.ask({
  question: 'How do I authenticate API requests?',
  context: ['api/authentication']
});

console.log(answer.response);
console.log(answer.sources);
```

**Python:**
```python
from mintlify import MintlifyAI

ai = MintlifyAI(api_key='YOUR_API_KEY')

answer = ai.ask(
    question='How do I authenticate API requests?',
    context=['api/authentication']
)

print(answer.response)
print(answer.sources)
```

## Analytics and Insights

Track AI feature usage and effectiveness.

### AI Metrics

**Search Analytics:**
- Popular queries
- Query success rate
- Zero-result searches
- Click-through rates

**Question Analytics:**
- Most asked questions
- Response accuracy
- User satisfaction ratings
- Follow-up questions

**Usage Patterns:**
- Peak usage times
- User segments
- Feature adoption
- Integration usage

### Dashboard

View AI analytics in Mintlify dashboard:
- AI > Analytics
- Filter by date range
- Export reports
- Track trends

### Configuration

```json
{
  "ai": {
    "analytics": {
      "enabled": true,
      "trackQueries": true,
      "trackClicks": true,
      "collectFeedback": true
    }
  }
}
```
