# Meta-Analysis Bot Debugging Guide

This guide provides comprehensive debugging procedures based on real-world issues encountered during development, particularly the zero cell display issue resolved on 2025-01-09.

## Table of Contents
1. [Problem Identification](#problem-identification)
2. [Debugging Workflow](#debugging-workflow)
3. [Common Issues and Solutions](#common-issues-and-solutions)
4. [Testing Procedures](#testing-procedures)
5. [Code Locations](#code-locations)
6. [Debugging Commands Reference](#debugging-commands-reference)

## Problem Identification

### Signs of Display Issues vs Implementation Issues

1. **Feature Implemented but Not Displaying**
   - R script generates correct output in logs
   - JSON contains expected data
   - Slack message missing information
   - Example: Zero cell information in JSON but not in Slack display

2. **R Script Execution vs Slack Display Discrepancies**
   ```bash
   # Check R script output
   heroku logs --tail | grep -A 50 "R script output"
   
   # Check JSON parsing
   heroku logs --tail | grep -A 20 "Parsed JSON result"
   
   # Check Slack message formatting
   heroku logs --tail | grep -A 30 "Analysis complete message"
   ```

3. **Key Indicators**
   - Look for "Successfully extracted zero cell information" in logs
   - Verify JSON structure matches expected format
   - Check if Slack formatting functions are called

## Debugging Workflow

### Step 1: Trace Data Flow (R → JSON → Slack)

1. **R Script Output**
   ```bash
   # Find R script execution
   heroku logs --tail | grep -E "(Executing R script|R script output)" -A 100
   
   # Look for specific JSON output
   heroku logs --tail | grep "zero_cells" -A 10
   ```

2. **JSON Parsing**
   ```bash
   # Check JSON parsing in Python
   heroku logs --tail | grep -E "(Parsing R output|Parsed JSON)" -A 50
   
   # Verify data extraction
   heroku logs --tail | grep -E "(Extracted.*from result|zero_cell_info)" -A 5
   ```

3. **Slack Message Construction**
   ```bash
   # Check message formatting
   heroku logs --tail | grep -E "(create_analysis_result_message|Formatting.*message)" -A 30
   
   # Look for zero cell sections
   heroku logs --tail | grep -E "(ゼロセル|zero cell|Zero cell)" -B 5 -A 10
   ```

### Step 2: Identify Break Points

1. **Data Generation** (R side)
   - Is the R script generating the data?
   - Check: `templates/r_templates.py` for R code generation

2. **Data Extraction** (Python side)
   - Is Python extracting the data from JSON?
   - Check: `mcp_legacy/analysis_executor.py` for JSON parsing

3. **Data Display** (Slack side)
   - Is the extracted data being formatted for display?
   - Check: `utils/slack_utils.py` for message formatting

### Step 3: Add Strategic Debug Logging

```python
# In analysis_executor.py
logger.info(f"Raw R output: {result_text[:500]}")
logger.info(f"Parsed JSON keys: {list(result.keys())}")
logger.info(f"Zero cell info extracted: {zero_cell_info}")

# In slack_utils.py
logger.info(f"Creating message with zero_cell_info: {zero_cell_info}")
logger.info(f"Final message blocks: {json.dumps(blocks, indent=2)}")
```

## Common Issues and Solutions

### 1. Zero Cell Information Not Displaying

**Problem**: R script generates zero cell data but it doesn't appear in Slack

**Solution Path**:
```bash
# 1. Verify R script output
heroku logs --tail | grep "zero_cells" -A 20

# 2. Check extraction in analysis_executor.py
heroku logs --tail | grep "Extracted zero cell" -A 5

# 3. Verify message formatting
heroku logs --tail | grep "ゼロセル処理" -A 10
```

**Code Fix Example**:
```python
# In analysis_executor.py - Add extraction
zero_cell_info = result.get('zero_cells', {})
if zero_cell_info:
    logger.info(f"Extracted zero cell info: {zero_cell_info}")

# In slack_utils.py - Add display section
if zero_cell_info and any(zero_cell_info.values()):
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*ゼロセル処理:*\n" + format_zero_cells(zero_cell_info)
        }
    })
```

### 2. Thread Response Issues

**Problem**: Bot doesn't respond in thread or loses context

**Debugging**:
```bash
# Check thread timestamp
heroku logs --tail | grep -E "(thread_ts|Thread context)" -A 5

# Verify dialog state
heroku logs --tail | grep -E "(DialogState|conversation.*state)" -A 5
```

**Common Causes**:
- Missing thread_ts in event
- Dialog state not properly managed
- Redis/storage backend issues

### 3. Parameter Collection Problems

**Problem**: Gemini doesn't extract parameters correctly

**Debugging**:
```bash
# Check Gemini calls
heroku logs --tail | grep -E "(Calling Gemini|Gemini response)" -A 20

# Verify function calling
heroku logs --tail | grep -E "(Function call|extract_parameters)" -A 10
```

**Solutions**:
- Check prompt in `prompts.json`
- Verify function schema matches expected parameters
- Ensure Gemini model supports function calling

## Testing Procedures

### 1. Testing with Specific Data Files

```bash
# Test binary data with zero cells
cd tests/
python3 test_slack_upload.py \
  --bot-id U08TKJ1JQ77 \
  --example binary \
  --message "二値データのメタ解析をお願いします。ゼロセルの調整も含めて。"

# Monitor response
python3 debug_channel_messages.py --wait 30
```

### 2. Slack Interaction Testing

```bash
# Step 1: Upload CSV with initial message
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "オッズ比で解析"

# Step 2: Get thread timestamp from output
# Thread started: 1736409876.123456

# Step 3: Continue conversation in thread
python3 send_message.py \
  --message "<@U08TKJ1JQ77> ランダム効果モデルでお願いします" \
  --thread "1736409876.123456"

# Step 4: Monitor for analysis completion
heroku logs --tail | grep -E "(Analysis completed|Uploading results)" -A 10
```

### 3. Monitoring During Testing

```bash
# Terminal 1: Monitor all logs
heroku logs --tail

# Terminal 2: Monitor specific components
heroku logs --tail | grep -E "(ERROR|Exception|Failed)" --color=always

# Terminal 3: Monitor analysis flow
heroku logs --tail | grep -E "(CSV analysis|parameter.*collection|Executing R|Analysis completed)" --color=always
```

## Code Locations

### Feature Implementation Map

| Feature | R Template | Python Processing | Slack Display |
|---------|------------|-------------------|---------------|
| Zero Cells | `templates/r_templates.py` | `mcp_legacy/analysis_executor.py` | `utils/slack_utils.py` |
| Parameter Collection | - | `handlers/parameter_handler.py` | `handlers/mention_handler.py` |
| CSV Analysis | - | `mcp_legacy/csv_processor.py` | `utils/slack_utils.py` |
| Report Generation | - | `mcp_legacy/report_generator.py` | `handlers/report_handler.py` |

### Key Files for Debugging

1. **R Script Generation**
   - `templates/r_templates.py` - R code templates
   - `mcp_legacy/r_template_generator.py` - Dynamic R script creation

2. **Data Processing**
   - `mcp_legacy/analysis_executor.py` - R execution and JSON parsing
   - `mcp_legacy/meta_analysis.py` - Analysis orchestration

3. **Slack Interaction**
   - `utils/slack_utils.py` - Message formatting
   - `handlers/mention_handler.py` - Event handling
   - `handlers/analysis_handler.py` - Analysis flow

4. **State Management**
   - `utils/conversation_state.py` - Thread context
   - `mcp_legacy/dialog_state_manager.py` - Dialog flow

### Where to Add Debug Logging

```python
# 1. R script execution (mcp_legacy/analysis_executor.py)
async def _run_r_script_internal(self, script_path, timeout=300):
    # Add before execution
    logger.info(f"Executing R script: {script_path}")
    with open(script_path, 'r') as f:
        logger.debug(f"R script content:\n{f.read()[:1000]}")
    
    # Add after execution
    logger.info(f"R script output:\n{stdout[:2000]}")

# 2. JSON parsing (mcp_legacy/analysis_executor.py)
result = json.loads(result_text)
logger.info(f"Parsed JSON structure: {json.dumps(result, indent=2)[:1000]}")

# 3. Message formatting (utils/slack_utils.py)
def create_analysis_result_message(result, analysis_type):
    logger.info(f"Creating message for analysis type: {analysis_type}")
    logger.info(f"Result keys: {list(result.keys())}")
    # ... rest of function
```

## Debugging Commands Reference

### Quick Diagnosis Commands

```bash
# Check if bot is receiving events
heroku logs --tail | grep "App mention received"

# Track full analysis flow
heroku logs --tail | grep -E "(mention.*received|CSV.*detected|Gemini|parameter|Executing R|completed)" --color=always

# Find errors quickly
heroku logs --tail | grep -iE "(error|exception|failed|timeout)" --color=always

# Check specific thread
heroku logs --tail | grep "THREAD_TS_HERE" -A 10 -B 10

# Monitor memory usage
heroku logs --tail | grep "Memory quota"
```

### Data Flow Verification

```bash
# 1. R → JSON
heroku logs --tail | grep -A 100 "R script output" | grep -E "(zero_cells|subgroup|meta_regression)"

# 2. JSON → Python
heroku logs --tail | grep -A 50 "Parsed JSON result" | jq '.'

# 3. Python → Slack
heroku logs --tail | grep -A 30 "create_analysis_result_message"
```

### Common Grep Patterns

```bash
# Component-specific
alias bot-csv='heroku logs --tail | grep -E "(CSV|csv)"'
alias bot-gemini='heroku logs --tail | grep -E "(Gemini|gemini)"'
alias bot-r='heroku logs --tail | grep -E "(R script|Executing R)"'
alias bot-slack='heroku logs --tail | grep -E "(Slack|slack_utils)"'

# Error hunting
alias bot-errors='heroku logs --tail | grep -iE "(error|exception|traceback)" --color=always'
alias bot-warnings='heroku logs --tail | grep -iE "(warning|warn)" --color=always'
```

## Best Practices

1. **Always Check Data Flow**: R → JSON → Python → Slack
2. **Add Logging Before Debugging**: Don't guess, add strategic logs
3. **Test with Known Data**: Use example CSVs that should trigger specific features
4. **Monitor in Real-Time**: Keep `heroku logs --tail` running during tests
5. **Document Fixes**: Update this guide with new issues and solutions

## Recent Fixes Reference

### Zero Cell Display (2025-01-09)
- **Issue**: Zero cell adjustments calculated but not shown
- **Root Cause**: Data extracted but not passed to Slack formatting
- **Fix**: Added zero_cell_info to message creation and formatting
- **Files Changed**: 
  - `mcp_legacy/analysis_executor.py` (extraction)
  - `utils/slack_utils.py` (display)
- **Verification**: Check for "ゼロセル処理" in Slack messages