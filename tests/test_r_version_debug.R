# Test script to debug version information issue
# This simulates what happens in the generated R code

library(metafor)
library(jsonlite)

# Simulate the save_results section
summary_list <- list()

# Test 1: Basic tryCatch without error
print("Test 1: Basic tryCatch without error")
tryCatch({
    summary_list$test1 <- "success"
    summary_list$r_version <- R.version.string
    print("Version added successfully in Test 1")
}, error = function(e) {
    print(paste("Error in Test 1:", e$message))
})
print(paste("Test 1 - Has r_version:", "r_version" %in% names(summary_list)))
print("")

# Test 2: Error before version assignment
print("Test 2: Error before version assignment")
summary_list2 <- list()
tryCatch({
    summary_list2$test2 <- "processing"
    # Simulate an error (like what might happen in subgroup analysis)
    stop("Simulated error in subgroup analysis")
    summary_list2$r_version <- R.version.string  # This won't be reached
    print("This message should not appear")
}, error = function(e) {
    print(paste("Error in Test 2:", e$message))
    summary_list2$error_in_summary_generation <- e$message
})
print(paste("Test 2 - Has r_version:", "r_version" %in% names(summary_list2)))
print("")

# Test 3: Error handling with version info outside error-prone section
print("Test 3: Version info outside error-prone section")
summary_list3 <- list()

# Add version info FIRST, before any potentially error-prone code
summary_list3$r_version <- R.version.string
summary_list3$metafor_version <- as.character(packageVersion("metafor"))

tryCatch({
    # Now do the potentially error-prone operations
    stop("Simulated error after version info")
}, error = function(e) {
    print(paste("Error in Test 3:", e$message))
    summary_list3$error_in_summary_generation <- e$message
})
print(paste("Test 3 - Has r_version:", "r_version" %in% names(summary_list3)))
print(paste("Test 3 - r_version value:", summary_list3$r_version))

# Check the actual structure that would be generated
print("\nActual structure simulation:")
summary_list_actual <- list()
tryCatch({
    # Overall analysis (usually succeeds)
    summary_list_actual$overall_analysis <- list(k = 10, estimate = 1.5)
    
    # Subgroup analysis (might fail)
    if (FALSE) {  # Simulate missing object
        summary_list_actual$subgroup_analyses_Region <- list()
    }
    
    # This is where version info is added in the template
    summary_list_actual$r_version <- R.version.string
    summary_list_actual$metafor_version <- as.character(packageVersion("metafor"))
    
}, error = function(e_sum) {
    summary_list_actual$error_in_summary_generation <- paste("Error:", e_message)
    print(sprintf("Error creating parts of summary_list: %s", e_message))
})

print(paste("\nActual simulation - Has r_version:", "r_version" %in% names(summary_list_actual)))
print(paste("Keys in summary_list_actual:", paste(names(summary_list_actual), collapse=", ")))