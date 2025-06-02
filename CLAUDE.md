# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Meta-Analysis Slack Bot that performs statistical meta-analyses on CSV files shared in Slack channels. It uses Google Gemini AI for natural language processing (Japanese) and generates academic-quality reports in English using R's metafor package.

## Essential Commands

### Local Development
```bash
# Build and run with Docker
docker build -t meta-analysis-bot .
docker run --env-file .env meta-analysis-bot

# Run without Docker
python main.py

# Install Python dependencies
pip install -r requirements.txt
```

### Docker Debugging
```bash
# Find container ID
docker ps -a

# View logs
docker logs [CONTAINER_ID]

# List files inside container
docker exec [CONTAINER_ID] ls -la /app/

# Copy files from container
docker cp [CONTAINER_ID]:/app/filename.ext ./filename.ext
```

### Testing & Development
```bash
# No automated tests exist - test manually by:
# 1. Upload CSV file to Slack channel with bot mention
# 2. Follow Japanese prompts to configure analysis
# 3. Verify forest plot and report generation
```

## Architecture

The bot follows an event-driven architecture:

1. **Entry Point**: `main.py` - Handles both HTTP mode (Heroku) and Socket mode (local)
2. **Core Orchestrator**: `mcp/slack_bot.py` - Manages component lifecycle
3. **Key Components**:
   - `message_handlers.py`: Routes Slack events
   - `csv_processor.py`: Analyzes CSV compatibility with Gemini
   - `parameter_collector.py`: Extracts parameters from Japanese text
   - `analysis_executor.py`: Runs R scripts asynchronously
   - `report_generator.py`: Creates academic reports

## Critical Implementation Details

### Security
- This is an OPEN repository - NEVER commit secrets
- All credentials must be in `.env` file (gitignored)
- Environment variables: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`, `GEMINI_API_KEY`

### Gemini Function Calling Pattern
When implementing Gemini function calling with enums, avoid None values:
```python
# WRONG - causes pydantic validation errors
class AnalysisType(str, Enum):
    META_ANALYSIS = "meta_analysis"
    SENSITIVITY = "sensitivity_analysis"
    NONE = None  # Don't do this!

# CORRECT
class AnalysisType(str, Enum):
    META_ANALYSIS = "meta_analysis"
    SENSITIVITY = "sensitivity_analysis"
    NOT_SPECIFIED = "not_specified"
```

### Async Processing
The bot uses `AsyncAnalysisRunner` to handle Slack's 3-second timeout:
- Initial response sent immediately
- Analysis runs in background
- Results posted to thread when complete

### State Management
- Uses `ThreadContextManager` for conversation persistence
- Dialog states managed by `DialogStateManager`
- Storage backend configurable via `STORAGE_BACKEND` env var:
  - `redis` (default): Persistent storage with Redis
  - `memory`: In-memory storage (ephemeral)
  - `file`: File-based storage (uses /tmp on Heroku, ephemeral)

### R Script Generation
Templates in `r_template_generator.py` support:
- Binary outcomes (OR, RR, RD)
- Continuous outcomes (SMD, MD)
- Proportions (PRAW, PLN, PAS, etc.)
- Pre-calculated effect sizes
- Subgroup analysis and meta-regression

## Common Development Tasks

### Adding New Analysis Types
1. Update `AnalysisType` enum in `parameter_collector.py`
2. Add R template in `r_template_generator.py`
3. Update Gemini prompts in `prompts.json`
4. Test with example CSV in `examples/`

### Debugging R Script Errors
The bot uses Gemini for self-debugging:
1. R errors are captured in `analysis_executor.py`
2. Sent to Gemini with script and data context
3. Gemini suggests fixes which are automatically applied
4. Maximum 3 retry attempts

### Modifying Gemini Prompts
All prompts stored in `mcp/cache/prompts.json`:
- `csv_analysis`: Initial CSV compatibility check
- `parameter_extraction`: Extract parameters from Japanese
- `r_script_debugging`: Fix R script errors
- `report_generation`: Create academic reports

## Deployment Notes

### Heroku (Production)
- Uses HTTP mode with event subscriptions
- Requires public URL for Slack events
- Configure buildpacks: `heroku/python` and `r`
- Set all environment variables in Heroku dashboard
- Add Redis addon: `heroku addons:create heroku-redis:hobby-dev`
- Redis URL automatically set as `REDIS_URL` env var

### Local Development
- Uses Socket Mode (no public URL needed)
- Set `SLACK_APP_TOKEN` in `.env`
- Easier for testing and debugging

## Important Patterns

### Error Handling
- All user-facing errors in Japanese
- Technical errors logged in English
- Gemini-assisted debugging for R scripts

### File Processing
- CSV files downloaded from Slack to `/tmp/`
- Cleaned up after processing
- Local paths used directly (no GCS upload)

### Thread Management
- All bot responses in threads
- Context maintained per thread
- Avoids infinite loops with bot message detection