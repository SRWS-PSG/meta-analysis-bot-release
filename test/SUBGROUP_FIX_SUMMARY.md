# Subgroup Analysis Column Name Fix Summary

## Problem
Subgroup and meta-regression analysis results were not being returned to Slack due to column name mismatch issues.

## Root Causes
1. **Column Name Cleaning**: CSV files have column names cleaned when loaded (spaces → underscores) by `file_utils.py`
2. **R Variable Names**: R variable names cannot contain special characters like parentheses, slashes, etc.
3. **Mismatch**: The analysis handler was providing original column names instead of cleaned ones to the R template
4. **Invalid R Syntax**: R code was trying to create variables like `res_subgroup_test_Setting_(ICU_/_non-ICU)` which is invalid

## Changes Made

### 1. `handlers/analysis_handler.py`
- Added column name cleaning to match what's actually in the CSV file loaded by R
- Extracts original column names from Gemini analysis
- Applies same cleaning function as `file_utils.py`
- Passes cleaned column names in `data_summary["columns"]`

### 2. `templates/r_templates.py` 
- Added safe variable name generation for R objects (alphanumeric + underscore only)
- Updated `_generate_subgroup_code()` to use safe variable names for R objects
- Updated subgroup forest plot template to use safe variable names
- Updated JSON save code to use safe variable names
- Stores original column name in JSON for display purposes

### 3. `utils/slack_utils.py`
- Updated to extract actual column names from the `subgroup_column` field in JSON
- Handles both moderation tests and individual subgroup analyses
- Displays original column names to users, not the safe variable names

## Example Transformation
- Original column: `"Setting (ICU / non-ICU)"`
- Cleaned column (in CSV): `"Setting_(ICU_/_non-ICU)"`
- Safe R variable: `res_subgroup_test_Setting__ICU___non_ICU_`
- JSON key: `subgroup_moderation_test_Setting__ICU___non_ICU_`
- JSON value includes: `"subgroup_column": "Setting_(ICU_/_non-ICU)"`
- Slack display: `"Setting_(ICU_/_non-ICU)別サブグループ解析"`

## Result
The fix ensures that:
1. R scripts execute without syntax errors
2. Subgroup analyses complete successfully
3. Results are properly saved to JSON
4. Slack displays the correct column names to users
5. The entire pipeline works with columns containing spaces, parentheses, slashes, and other special characters