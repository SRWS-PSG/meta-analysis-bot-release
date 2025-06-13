# Test Directory

This directory contains test scripts and debugging tools for the Meta-Analysis Bot.

## Test Files

### test_subgroup_column_fix.py
**Purpose**: Tests the fix for subgroup analysis with special characters in column names
- Verifies R variable name generation with special characters
- Tests column name cleaning and matching
- Validates JSON output structure
- Tests Slack message display with proper column names

### test_subgroup_exclusion_fix.py
**Purpose**: Tests the subgroup exclusion logic for small subgroups
- Verifies that subgroups with n≤1 are excluded from forest plots
- Tests exclusion information is properly recorded
- Validates that analysis continues with remaining valid subgroups

### test_r_template_fixes.py
**Purpose**: General R template generation tests
- Tests various effect size types
- Validates plot generation
- Tests error handling in R scripts

## Debug Tools

### SUBGROUP_FIX_SUMMARY.md
Documentation of the column name handling fix implemented on 2025-06-14

## Running Tests

```bash
# Run individual test
python test/test_subgroup_column_fix.py

# Run all tests (if test runner implemented)
python -m pytest test/
```

## Adding New Tests

When adding new test files:
1. Create the test file in this directory
2. Add a description to this README
3. Include clear documentation of what the test validates
4. Use descriptive function names and comments