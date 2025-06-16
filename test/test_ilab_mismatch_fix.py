#!/usr/bin/env python3
"""
Test script to reproduce and verify the fix for the ilab argument length mismatch error.

This test creates a dataset with exactly 20 studies where one study belongs to a 
subgroup that will be excluded (n=1 subgroup), then runs the R script to check 
if the error still occurs.
"""

import os
import sys
import json
import tempfile
import subprocess
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

def run_r_script(r_script_path, csv_path):
    """Run the R script and capture output."""
    cmd = ['Rscript', r_script_path, csv_path]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result
    except subprocess.TimeoutExpired:
        return None

def analyze_results(result, output_dir):
    """Analyze the R script execution results."""
    print("=" * 80)
    print("TEST RESULTS: ilab Argument Length Mismatch Fix")
    print("=" * 80)
    
    # Check if script executed
    if result is None:
        print("❌ FAILED: Script timed out")
        return False
        
    print(f"Return code: {result.returncode}")
    print("\n--- STDOUT ---")
    print(result.stdout)
    print("\n--- STDERR ---")
    print(result.stderr)
    
    # Check for the specific error
    error_found = "length of the ilab argument" in result.stderr
    
    if error_found:
        print("\n❌ FAILED: ilab argument length mismatch error still occurs!")
        # Extract error details
        for line in result.stderr.split('\n'):
            if "length of the ilab argument" in line:
                print(f"   Error: {line}")
        return False
    
    # Check if script completed successfully
    if result.returncode != 0:
        print(f"\n❌ FAILED: Script exited with code {result.returncode}")
        return False
    
    # Check if output files were created
    json_path = Path(output_dir) / "summary.json"
    if json_path.exists():
        print("\n✅ SUCCESS: Script completed without ilab errors!")
        
        # Load and verify JSON
        try:
            with open(json_path) as f:
                summary = json.load(f)
            
            print("\n--- Summary JSON ---")
            print(f"Overall k (studies): {summary.get('overall_analysis', {}).get('k', 'N/A')}")
            
            if 'subgroup_analysis' in summary:
                print("\nSubgroup Analysis:")
                for subgroup, stats in summary['subgroup_analysis'].items():
                    if subgroup != 'test_results':
                        print(f"  {subgroup}: k={stats.get('k', 'N/A')} studies")
                
                # Check excluded subgroups
                if 'excluded_subgroups' in summary:
                    print(f"\nExcluded subgroups: {summary['excluded_subgroups']}")
                    if 'GroupB' in summary['excluded_subgroups']:
                        print("✅ GroupB correctly excluded (n=1)")
                    else:
                        print("⚠️  GroupB was not excluded as expected")
            
            return True
            
        except Exception as e:
            print(f"\n⚠️  Warning: Could not parse JSON: {e}")
            return True  # Still success if script completed
    else:
        print("\n❌ FAILED: No output files generated")
        return False

def main():
    """Run the test."""
    print("Creating test environment...")
    
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
        
        # Create R script
        r_script = create_r_script(data, temp_dir, csv_path)
        r_script_path = os.path.join(temp_dir, 'test_script.R')
        with open(r_script_path, 'w') as f:
            f.write(r_script)
        
        print(f"\nRunning R script...")
        print(f"CSV: {csv_path}")
        print(f"Script: {r_script_path}")
        
        # Run the test
        result = run_r_script(r_script_path, csv_path)
        
        # Analyze results
        success = analyze_results(result, temp_dir)
        
        # Additional diagnostics
        if not success:
            print("\n--- Diagnostics ---")
            print("Checking for common issues:")
            
            # Check if R and packages are available
            check_r = subprocess.run(['which', 'Rscript'], capture_output=True, text=True)
            if check_r.returncode != 0:
                print("❌ Rscript not found in PATH")
            else:
                print(f"✅ Rscript found: {check_r.stdout.strip()}")
            
            # Save problematic script for debugging
            debug_script = '/tmp/debug_ilab_test.R'
            with open(debug_script, 'w') as f:
                f.write(r_script)
            print(f"\nDebug script saved to: {debug_script}")
            print(f"Debug CSV saved to: /tmp/debug_ilab_test.csv")
            
            import shutil
            shutil.copy(csv_path, '/tmp/debug_ilab_test.csv')
        
        print("\n" + "=" * 80)
        if success:
            print("✅ TEST PASSED: ilab argument length mismatch has been fixed!")
        else:
            print("❌ TEST FAILED: ilab argument length mismatch still occurs!")
        print("=" * 80)
        
        return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())