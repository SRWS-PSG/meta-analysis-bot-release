#!/usr/bin/env Rscript

# Test script to verify R version output formatting
library(metafor)
library(jsonlite)

# Create summary_list like in the actual script
summary_list <- list()

# Test the version information collection
tryCatch({
    # Add R and metafor versions with detailed information
    summary_list$r_version <- R.version.string
    summary_list$metafor_version <- as.character(packageVersion("metafor"))
    
    # Additional analysis environment information
    summary_list$analysis_environment <- list(
        r_version_full = R.version.string,
        r_version_short = paste(R.version$major, R.version$minor, sep="."),
        metafor_version = as.character(packageVersion("metafor")),
        jsonlite_version = as.character(packageVersion("jsonlite")),
        platform = R.version$platform,
        os_type = .Platform$OS.type,
        analysis_date = as.character(Sys.Date()),
        analysis_time = as.character(Sys.time())
    )
    
    cat("R Version Information Test:\n")
    cat("R.version.string:", R.version.string, "\n")
    cat("metafor version:", as.character(packageVersion("metafor")), "\n")
    cat("Platform:", R.version$platform, "\n")
    
    # Test JSON serialization
    json_output <- jsonlite::toJSON(summary_list, auto_unbox = TRUE, pretty = TRUE, null = "null", force=TRUE)
    cat("\nJSON Output:\n")
    cat(json_output)
    cat("\n")
    
}, error = function(e) {
    cat("Error in version collection:", e$message, "\n")
})