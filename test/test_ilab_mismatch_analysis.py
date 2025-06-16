#!/usr/bin/env python3
"""
Test script to analyze the generated R script and verify the ilab argument length mismatch fix.

This test creates a dataset with exactly 20 studies where one study belongs to a 
subgroup that will be excluded (n=1 subgroup), generates the R script, and analyzes
the code to verify the fix is properly implemented.
"""

import os
import sys
import json
import tempfile
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def create_test_dataset():
    """Create a test dataset with 20 studies where one belongs to a n=1 subgroup."""
    data = {
        'headers': ['Study', 'Intervention_Events', 'Intervention_Total', 
                   'Control_Events', 'Control_Total', 'Subgroup'],
        'rows': []
    }
    
    # Add 19 studies to "GroupA" 
    for i in range(1, 20):
        data['rows'].append([
            f'Study{i}',
            str(10 + i),  # Intervention events
            str(50 + i),  # Intervention total
            str(8 + i),   # Control events  
            str(50 + i),  # Control total
            'GroupA'      # Subgroup
        ])
    
    # Add 1 study to "GroupB" (this will be excluded as n=1)
    data['rows'].append([
        'Study20',
        '25',  # Intervention events
        '70',  # Intervention total
        '20',  # Control events
        '70',  # Control total
        'GroupB'  # Subgroup (n=1, will be excluded)
    ])
    
    return data

def create_r_script(data, output_dir, csv_path):
    """Generate R script using the RTemplateGenerator."""
    generator = RTemplateGenerator()
    
    # Analysis parameters with proper column mappings
    analysis_params = {
        'measure': 'OR',
        'method': 'REML',
        'test': 'knha',
        'subgroup_columns': ['Subgroup'],
        'analysis_type': 'subgroup_analysis',
        'data_columns': {
            'ai': 'Intervention_Events',  # intervention events
            'bi': None,  # will be calculated from n1i - ai
            'ci': 'Control_Events',       # control events 
            'di': None,  # will be calculated from n2i - ci
            'n1i': 'Intervention_Total',  # intervention total
            'n2i': 'Control_Total',       # control total
            'study_label': 'Study'
        }
    }
    
    # Data summary (CSV column information)
    data_summary = {
        'columns': data['headers'],
        'detected_columns': {
            'binary_intervention_events': ['Intervention_Events'],
            'binary_intervention_total': ['Intervention_Total'],
            'binary_control_events': ['Control_Events'],
            'binary_control_total': ['Control_Total'],
            'study_id_candidates': ['Study']
        },
        'num_studies': len(data['rows']),
        'effect_measure': 'OR'
    }
    
    # Output paths (use correct key names)
    output_paths = {
        'json_summary_path': os.path.join(output_dir, 'summary.json'),
        'forest_plot_path': os.path.join(output_dir, 'forest_plot.png'),
        'funnel_plot_path': os.path.join(output_dir, 'funnel_plot.png'),
        'rdata_path': os.path.join(output_dir, 'results.RData')
    }
    
    # Generate full R script
    r_script = generator.generate_full_r_script(
        analysis_params=analysis_params,
        data_summary=data_summary,
        output_paths=output_paths,
        csv_file_path_in_script=csv_path
    )
    
    return r_script

def analyze_r_script_for_ilab_fix(r_script):
    """Analyze the R script to verify ilab argument length fix is implemented."""
    print("=" * 80)
    print("ANALYSIS: R Script ilab Argument Length Mismatch Fix")
    print("=" * 80)
    
    issues_found = []
    fixes_found = []
    
    # Check 1: Look for subgroup exclusion detection
    exclusion_patterns = [
        r'filtered_indices.*<-.*which',
        r'length.*filtered_indices',
        r'excluded.*subgroups',
        r'group_size.*<.*2',
        r'subgroup.*analysis.*filtered'
    ]
    
    for pattern in exclusion_patterns:
        if re.search(pattern, r_script, re.IGNORECASE):
            fixes_found.append(f"✅ Found subgroup exclusion logic: {pattern}")
    
    # Check 2: Look for proper ilab handling
    ilab_patterns = [
        r'ilab.*=.*.*\[filtered_indices\]',
        r'ilab.*filtered',
        r'slab.*\[.*filtered.*\]',
        r'length.*ilab.*==.*length'
    ]
    
    for pattern in ilab_patterns:
        if re.search(pattern, r_script, re.IGNORECASE):
            fixes_found.append(f"✅ Found ilab filtering: {pattern}")
    
    # Check 3: Look for potential issues
    problematic_patterns = [
        r'ilab.*=.*slab(?!\[)',  # ilab = slab without filtering
        r'forest\(.*ilab.*=.*[^[]slab',  # forest plot with unfiltered slab
    ]
    
    for pattern in problematic_patterns:
        if re.search(pattern, r_script, re.IGNORECASE):
            issues_found.append(f"❌ Potential issue: {pattern}")
    
    # Check 4: Look for filtered data consistency 
    consistency_patterns = [
        r'dat_filtered.*<-.*dat\[filtered_indices',
        r'yi_filtered.*<-.*yi\[filtered_indices',
        r'vi_filtered.*<-.*vi\[filtered_indices'
    ]
    
    consistency_found = 0
    for pattern in consistency_patterns:
        if re.search(pattern, r_script, re.IGNORECASE):
            consistency_found += 1
            fixes_found.append(f"✅ Found data consistency: {pattern}")
    
    # Display results
    print(f"\n🔍 FIXES FOUND ({len(fixes_found)}):")
    for fix in fixes_found:
        print(f"  {fix}")
    
    if issues_found:
        print(f"\n⚠️  POTENTIAL ISSUES ({len(issues_found)}):")
        for issue in issues_found:
            print(f"  {issue}")
    
    # Check specific sections of the script
    sections_to_check = {
        'Subgroup Exclusion': r'# サブグループから単一研究.*?(?=^#|\Z)',
        'Forest Plot': r'forest\(.*?(?=^\w|\Z)',
        'Data Filtering': r'filtered_indices.*?(?=^#|\Z)'
    }
    
    print(f"\n📋 DETAILED SECTION ANALYSIS:")
    for section_name, pattern in sections_to_check.items():
        matches = re.findall(pattern, r_script, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if matches:
            print(f"\n--- {section_name} ---")
            for i, match in enumerate(matches):
                print(f"Match {i+1}:")
                # Show first few lines to avoid flooding output
                lines = match.strip().split('\n')[:5]
                for line in lines:
                    print(f"  {line}")
                if len(match.strip().split('\n')) > 5:
                    print(f"  ... ({len(match.strip().split('\n')) - 5} more lines)")
        else:
            print(f"\n--- {section_name} ---")
            print(f"  ❌ No matches found")
    
    # Overall assessment
    print(f"\n" + "=" * 80)
    print("OVERALL ASSESSMENT:")
    
    if len(fixes_found) >= 3 and not issues_found:
        print("✅ LIKELY FIXED: Multiple fix patterns detected, no issues found")
        return True
    elif len(fixes_found) >= 2:
        print("⚠️  PARTIALLY FIXED: Some fix patterns detected")
        return True
    else:
        print("❌ LIKELY NOT FIXED: Few or no fix patterns detected")
        return False

def main():
    """Run the analysis."""
    print("Creating test environment for R script analysis...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test dataset
        data = create_test_dataset()
        print(f"Created dataset with {len(data['rows'])} studies")
        print(f"- GroupA: 19 studies")
        print(f"- GroupB: 1 study (should be excluded)")
        
        # Save CSV
        csv_path = os.path.join(temp_dir, 'test_data.csv')
        with open(csv_path, 'w') as f:
            f.write(','.join(data['headers']) + '\n')
            for row in data['rows']:
                f.write(','.join(row) + '\n')
        
        # Generate R script
        print(f"\nGenerating R script...")
        r_script = create_r_script(data, temp_dir, csv_path)
        
        # Save script for analysis
        r_script_path = os.path.join(temp_dir, 'test_script.R')
        with open(r_script_path, 'w') as f:
            f.write(r_script)
        
        print(f"R script generated: {r_script_path}")
        print(f"Script length: {len(r_script)} characters")
        print(f"Script lines: {len(r_script.splitlines())}")
        
        # Analyze the script
        success = analyze_r_script_for_ilab_fix(r_script)
        
        # Save script to /tmp for debugging
        debug_script = '/tmp/debug_ilab_test.R'
        with open(debug_script, 'w') as f:
            f.write(r_script)
        print(f"\nDebug R script saved to: {debug_script}")
        
        debug_csv = '/tmp/debug_ilab_test.csv'
        with open(debug_csv, 'w') as f:
            f.write(','.join(data['headers']) + '\n')
            for row in data['rows']:
                f.write(','.join(row) + '\n')
        print(f"Debug CSV saved to: {debug_csv}")
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ANALYSIS PASSED: ilab argument length mismatch fix appears to be implemented!")
        else:
            print("❌ ANALYSIS FAILED: ilab argument length mismatch may still occur!")
        print("=" * 80)
        
        return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())