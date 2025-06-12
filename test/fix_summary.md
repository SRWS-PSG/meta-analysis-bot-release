# R Script JSON Output Processing Fix Summary

## Issue
When running meta-analyses for continuous outcomes (SMD/MD/ROM), proportions (PLO/PR/etc.), correlations (COR), or pre-calculated effect sizes (PRE), the Slack bot displayed "N/A" for all analysis results:

```
**【解析結果サマリー】**
• 統合効果量: N/A
• 95%信頼区間: N/A - N/A
• 異質性: I²=N/A%
• 研究数: N/A件
```

## Root Cause
The R template generator (`templates/r_templates.py`) had a critical bug where:

1. For continuous outcomes (SMD/MD/ROM), it tried to use a non-existent template `self.templates["main_analysis"]`
2. For proportions, correlations, and pre-calculated values, it only generated `escalc()` calls but never ran `rma()` to create the `res` object
3. Without the `res` object, the JSON summary generation in the R script would fail, resulting in missing `overall_analysis` section
4. The Python code would then display "N/A" for all values

## Fix Applied
Modified `templates/r_templates.py` to ensure all analysis types properly execute `rma()`:

1. **Continuous outcomes (SMD/MD/ROM)**: Changed from non-existent `main_analysis` to `rma_basic` template
2. **Proportions (PLO/PR/etc.)**: Added `rma_basic` execution after `escalc`
3. **Correlations (COR)**: Added `rma_basic` execution after `escalc`
4. **Pre-calculated (PRE)**: Added `rma_basic` execution
5. **Added `res_for_plot <- res`** to `rma_basic` template for consistency with binary outcomes

## Files Modified
- `/home/youkiti/meta-analysis-bot-release/templates/r_templates.py`

## Testing
Created test script `test/test_r_template_fixes.py` which verified that all measure types now correctly generate:
- `res <- rma()` call (creates the analysis result object)
- `res_for_plot <- res` assignment (needed for plots)

## Impact
This fix ensures that ALL meta-analysis types (not just binary outcomes) will display proper results in Slack instead of "N/A" values.