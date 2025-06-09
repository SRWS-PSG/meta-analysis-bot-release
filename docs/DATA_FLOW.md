# Meta-Analysis Bot Data Flow Documentation

## Overview: R Script → JSON → Python → Slack

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   R Script      │────▶│  JSON Output │────▶│  Python Parser  │────▶│ Slack Message│
│ (metafor)       │     │  (stdout)    │     │ (analysis_exec) │     │ (formatted)  │
└─────────────────┘     └──────────────┘     └─────────────────┘     └──────────────┘
        │                       │                      │                       │
        ▼                       ▼                      ▼                       ▼
   • Generate plots        • Structured data      • Parse JSON           • Rich formatting
   • Calculate stats       • Base64 images       • Extract fields       • Attachments
   • Handle zero cells     • Error messages      • Format messages      • Thread posts
```

## JSON Structure Mapping

### Expected R Output Structure
```json
{
  "summary": {
    "overall_analysis": {
      "k": 10,                    // Number of studies
      "estimate": 1.45,           // Pooled effect estimate
      "se": 0.123,                // Standard error
      "ci_lb": 1.12,              // CI lower bound
      "ci_ub": 1.88,              // CI upper bound
      "pval": 0.005,              // P-value
      "I2": 45.2,                 // I-squared (%)
      "H2": 1.83,                 // H-squared
      "tau2": 0.0234,             // Tau-squared
      "Q": 16.45,                 // Q statistic
      "Q_pval": 0.032,            // Q test p-value
      "effect_type": "OR",        // Effect measure type
      "model": "random"           // Model type
    },
    "zero_cells_summary": {       // CRITICAL: Must be present even if empty
      "total_zero_cells": 3,
      "studies_with_zero_cells": ["Study 1", "Study 3", "Study 7"],
      "adjustments": {
        "method": "constant",
        "value": 0.5
      }
    },
    "sensitivity_analysis": {     // Optional
      "leave_one_out": [...],
      "influence_measures": [...]
    },
    "subgroup_analysis": {        // Optional
      "groups": {...},
      "test_statistic": {...}
    }
  },
  "plots": {
    "forest": "base64_encoded_png_data...",
    "funnel": "base64_encoded_png_data...",
    "influence": "base64_encoded_png_data..."  // Optional
  },
  "r_code": "# Full R script used for analysis...",
  "error": null,                  // Or error message if failed
  "warnings": [],                 // Any R warnings
  "version_info": {
    "R_version": "R version 4.3.2 (2023-10-31)",
    "metafor_version": "4.4-0",
    "platform": "x86_64-pc-linux-gnu",
    "analysis_date": "2025-01-09 10:15:30 UTC"
  }
}
```

### Zero Cells Summary Structure (REQUIRED)
```json
"zero_cells_summary": {
  // Case 1: No zero cells
  "total_zero_cells": 0,
  "studies_with_zero_cells": [],
  "adjustments": null
  
  // Case 2: Zero cells present
  "total_zero_cells": 3,
  "studies_with_zero_cells": ["Study 1", "Study 3", "Study 7"],
  "adjustments": {
    "method": "constant",     // or "tacc", "cloglog", etc.
    "value": 0.5,            // adjustment value used
    "description": "Added 0.5 to all cells of studies with zero cells"
  }
}
```

## Critical Files and Functions

### 1. R Script Generation
**File**: `templates/r_templates.py`
```python
def _get_zero_cells_handling() -> str:
    # Generates R code for zero cell detection
    # MUST include zero_cells_summary in JSON output
```

### 2. R Script Execution
**File**: `core/r_executor.py`
```python
def execute_r_script(script_content: str, ...) -> Dict:
    # Executes R script and captures stdout
    # Parses JSON from stdout
    # Returns parsed dictionary
```

### 3. Analysis Execution
**File**: `mcp_legacy/analysis_executor.py`
```python
async def _execute_analysis_with_retry(...):
    # Calls r_executor.execute_r_script
    # Handles errors and retries
    # CRITICAL: Preserves complete JSON structure
```

### 4. Result Formatting
**File**: `utils/slack_utils.py`
```python
def create_analysis_result_message(result: Dict[str, Any]) -> str:
    # Extracts fields from result['summary']
    # Formats message for Slack
    # MUST handle missing fields gracefully
```

### 5. Zero Cell Message Creation
**File**: `utils/slack_utils.py`
```python
def _create_zero_cells_message(zero_cells_info: Dict[str, Any]) -> str:
    # Formats zero cell information
    # Returns empty string if no zero cells
```

## Common Breakpoints and Debugging

### 1. R Script JSON Output
**Where it breaks**: R script doesn't output valid JSON
```r
# WRONG: Multiple print statements
print("Analysis complete")
print(toJSON(results))

# CORRECT: Single JSON output
cat(toJSON(list(
  summary = summary_data,
  plots = plot_data,
  # ... other fields
), auto_unbox = TRUE))
```

### 2. JSON Parsing in Python
**Where it breaks**: `r_executor.py` line ~85
```python
# Check if output is valid JSON
try:
    result = json.loads(output)
except json.JSONDecodeError:
    # Log the raw output for debugging
    logger.error(f"Invalid JSON output: {output[:500]}")
```

### 3. Field Access in Result Formatting
**Where it breaks**: `slack_utils.py` accessing nested fields
```python
# WRONG: Assumes field exists
zero_cells = result['summary']['zero_cells_summary']['total_zero_cells']

# CORRECT: Safe navigation
summary = result.get('summary', {})
zero_cells_summary = summary.get('zero_cells_summary', {})
total_zero_cells = zero_cells_summary.get('total_zero_cells', 0)
```

### 4. Slack Message Truncation
**Where it breaks**: Message too long for Slack
```python
# Maximum Slack message length: 4000 characters
# Truncate if necessary
if len(message) > 3900:
    message = message[:3900] + "\n\n[詳細は添付ファイルを参照]"
```

## Zero Cell Example: Complete Trace

### 1. R Script Detects Zero Cells
```r
# In R script (generated by templates/r_templates.py)
zero_cell_counts <- apply(data[, c("ai", "bi", "ci", "di")], 1, function(x) sum(x == 0))
studies_with_zero <- rownames(data)[zero_cell_counts > 0]

zero_cells_summary <- list(
  total_zero_cells = sum(zero_cell_counts > 0),
  studies_with_zero_cells = as.list(studies_with_zero),
  adjustments = if(length(studies_with_zero) > 0) {
    list(
      method = "constant",
      value = 0.5,
      description = "Added 0.5 to all cells of studies with zero cells"
    )
  } else NULL
)
```

### 2. JSON Output from R
```json
{
  "summary": {
    "overall_analysis": {
      "k": 10,
      "estimate": 1.52,
      // ... other stats
    },
    "zero_cells_summary": {
      "total_zero_cells": 2,
      "studies_with_zero_cells": ["Study 3", "Study 7"],
      "adjustments": {
        "method": "constant",
        "value": 0.5,
        "description": "Added 0.5 to all cells of studies with zero cells"
      }
    }
  },
  "plots": { /* base64 data */ },
  "r_code": "# Full script..."
}
```

### 3. Python Parses JSON
```python
# In analysis_executor.py
result = await self.r_executor.execute_r_script(r_script, ...)
# result now contains the parsed dictionary

# Verify zero cells data exists
if 'summary' in result and 'zero_cells_summary' in result['summary']:
    logger.info(f"Zero cells data present: {result['summary']['zero_cells_summary']}")
```

### 4. Slack Message Formatting
```python
# In slack_utils.py
def create_analysis_result_message(result):
    summary = result.get('summary', {})
    overall = summary.get('overall_analysis', {})
    zero_cells = summary.get('zero_cells_summary', {})
    
    # Build message
    message_parts = []
    
    # Add main results
    message_parts.append(f"• 統合効果量: {overall.get('estimate', 'N/A')}")
    
    # Add zero cells info if present
    if zero_cells.get('total_zero_cells', 0) > 0:
        zero_msg = _create_zero_cells_message(zero_cells)
        if zero_msg:
            message_parts.append(zero_msg)
    
    return "\n".join(message_parts)
```

### 5. Final Slack Display
```
📊 メタ解析が完了しました！

【解析結果サマリー】
• 統合効果量: 1.52
• 95%信頼区間: 1.15 - 2.01
• 異質性: I²=42.3%, Q-test p=0.045
• 研究数: 10件

【ゼロセルの処理】
• ゼロセルを含む研究: 2件 (Study 3, Study 7)
• 処理方法: 全セルに0.5を加算
```

## Verification Steps

### 1. Check R Output
```bash
# Save R script locally and run
Rscript test_script.R > output.json
# Verify JSON structure
cat output.json | jq .summary.zero_cells_summary
```

### 2. Check Python Parsing
```python
# In analysis_executor.py, add logging
logger.info(f"Raw R output: {output[:1000]}")
logger.info(f"Parsed result keys: {result.keys()}")
logger.info(f"Summary keys: {result.get('summary', {}).keys()}")
```

### 3. Check Slack Formatting
```python
# In slack_utils.py, add debug output
logger.debug(f"Zero cells data: {zero_cells}")
logger.debug(f"Formatted message: {message[:500]}")
```

### 4. Monitor Heroku Logs
```bash
# Watch for specific patterns
heroku logs --tail | grep -E "(zero_cells|Zero cells|ゼロセル)"

# Check for JSON parsing errors
heroku logs --tail | grep -E "(JSON|json\.loads|JSONDecodeError)"
```

## Quick Debugging Checklist

1. **No zero cell info in Slack?**
   - [ ] Check R script includes `zero_cells_summary` in output
   - [ ] Verify JSON structure in `r_executor.py` logs
   - [ ] Check `slack_utils.py` is looking for correct field names
   - [ ] Ensure zero cells detection code is in R template

2. **Data present in logs but not in Slack?**
   - [ ] Check field name mapping in `slack_utils.py`
   - [ ] Verify `_create_zero_cells_message` is being called
   - [ ] Check message length limits

3. **R script fails with zero cells?**
   - [ ] Verify data structure (ai, bi, ci, di columns exist)
   - [ ] Check zero cell handling code syntax
   - [ ] Ensure metafor functions handle adjusted data

4. **Intermittent failures?**
   - [ ] Check for race conditions in async processing
   - [ ] Verify thread state management
   - [ ] Check Redis/storage backend consistency