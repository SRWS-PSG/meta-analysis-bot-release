# Manual test R script for version information issue
# This script simulates what the bot generates for subgroup analysis

library(metafor)
library(jsonlite)

# Create test data
dat <- data.frame(
    Study = paste0("Study", 1:10),
    Intervention_Events = c(15, 22, 18, 25, 30, 12, 28, 35, 20, 32),
    Intervention_Total = c(48, 55, 50, 60, 65, 40, 70, 80, 55, 75),
    Control_Events = c(10, 18, 15, 20, 25, 8, 22, 30, 18, 28),
    Control_Total = c(52, 58, 50, 62, 68, 38, 65, 85, 60, 70),
    Region = c("Asia", "Europe", "Asia", "Europe", "America", "Asia", "Europe", "America", "Asia", "Europe")
)

# Calculate n-events
dat$Intervention_Events_n_minus_event <- dat$Intervention_Total - dat$Intervention_Events
dat$Control_Events_n_minus_event <- dat$Control_Total - dat$Control_Events

# Calculate effect sizes
dat <- escalc(measure="OR", 
              ai=Intervention_Events, 
              bi=Intervention_Events_n_minus_event, 
              ci=Control_Events, 
              di=Control_Events_n_minus_event, 
              data=dat)

# Main analysis
res <- rma(yi, vi, data=dat, method="REML")
res_for_plot <- res

# Subgroup analysis
res_subgroup_test_Region <- rma(yi, vi, mods = ~ factor(Region), data=dat, method="REML")

# By-level subgroup analysis
if ("Region" %in% names(dat)) {
    dat_split_Region <- split(dat, dat[['Region']])
    res_by_subgroup_Region <- lapply(names(dat_split_Region), function(level_name) {
        current_data_sg <- dat_split_Region[[level_name]]
        if (nrow(current_data_sg) > 0) {
            tryCatch({
                rma_result_sg <- rma(yi, vi, data=current_data_sg, method="REML")
                rma_result_sg$subgroup_level <- level_name
                return(rma_result_sg)
            }, error = function(e) {
                print(sprintf("RMA failed for subgroup 'Region' level '%s': %s", level_name, e$message))
                return(NULL)
            })
        } else {
            return(NULL)
        }
    })
    res_by_subgroup_Region <- res_by_subgroup_Region[!sapply(res_by_subgroup_Region, is.null)]
    if (length(res_by_subgroup_Region) > 0) {
        names(res_by_subgroup_Region) <- sapply(res_by_subgroup_Region, function(x) x$subgroup_level)
    }
}

# Build summary list
summary_list <- list()
tryCatch({
    summary_list$overall_summary_text <- paste(capture.output(summary(res)), collapse = "\n")
    
    summary_list$overall_analysis <- list(
        k = res$k,
        estimate = as.numeric(res$b)[1], 
        se = as.numeric(res$se)[1],    
        zval = as.numeric(res$zval)[1],  
        pval = as.numeric(res$pval)[1],  
        ci_lb = as.numeric(res$ci.lb)[1],
        ci_ub = as.numeric(res$ci.ub)[1],
        I2 = res$I2,
        H2 = res$H2,
        tau2 = res$tau2,
        QE = res$QE,
        QEp = res$QEp,
        method = res$method
    )
    
    # Subgroup results
    if (exists("res_subgroup_test_Region") && !is.null(res_subgroup_test_Region)) {
        summary_list$subgroup_moderation_test_Region <- list(
            subgroup_column = "Region", 
            QM = res_subgroup_test_Region$QM,
            QMp = res_subgroup_test_Region$QMp, 
            df = res_subgroup_test_Region$p -1,
            summary_text = paste(capture.output(print(res_subgroup_test_Region)), collapse = "\n")
        )
    }
    
    if (exists("res_by_subgroup_Region") && !is.null(res_by_subgroup_Region) && length(res_by_subgroup_Region) > 0) {
        subgroup_results_list_Region <- list()
        for (subgroup_name_idx in seq_along(res_by_subgroup_Region)) {
            current_res_sg <- res_by_subgroup_Region[[subgroup_name_idx]]
            subgroup_level_name <- names(res_by_subgroup_Region)[subgroup_name_idx]
            if (!is.null(current_res_sg)) {
                subgroup_results_list_Region[[subgroup_level_name]] <- list(
                    k = current_res_sg$k, 
                    estimate = as.numeric(current_res_sg$b)[1], 
                    se = as.numeric(current_res_sg$se)[1], 
                    zval = as.numeric(current_res_sg$zval)[1],
                    pval = as.numeric(current_res_sg$pval)[1], 
                    ci_lb = as.numeric(current_res_sg$ci.lb)[1],
                    ci_ub = as.numeric(current_res_sg$ci.ub)[1], 
                    I2 = current_res_sg$I2, 
                    tau2 = current_res_sg$tau2,
                    summary_text = paste(capture.output(print(current_res_sg)), collapse = "\n")
                )
            }
        }
        summary_list$subgroup_analyses_Region <- subgroup_results_list_Region
    }
    
    # Add R and metafor versions
    print("Adding version information...")
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
        analysis_time = as.character(Sys.time()),
        packages_info = list(
            metafor = list(
                version = as.character(packageVersion("metafor")),
                description = "Conducting Meta-Analyses in R"
            ),
            jsonlite = list(
                version = as.character(packageVersion("jsonlite")),
                description = "JSON output generation"
            )
        )
    )
    
    print("Version information added successfully")
    
}, error = function(e_sum) {
    summary_list$error_in_summary_generation <- paste("Error creating parts of summary:", e_sum$message)
    print(sprintf("Error creating parts of summary_list: %s", e_sum$message))
})

# Check what's in summary_list
print("Keys in summary_list:")
print(names(summary_list))

# Save to JSON
json_output_file_path <- "/tmp/test_version_output.json"
tryCatch({
    json_data <- jsonlite::toJSON(summary_list, auto_unbox = TRUE, pretty = TRUE, null = "null", force=TRUE)
    write(json_data, file=json_output_file_path)
    print(paste("Analysis summary saved to JSON:", json_output_file_path))
    
    # Check if version info is in JSON
    saved_json <- jsonlite::fromJSON(json_output_file_path)
    print(paste("JSON has r_version:", "r_version" %in% names(saved_json)))
    print(paste("JSON has metafor_version:", "metafor_version" %in% names(saved_json)))
    print(paste("JSON has analysis_environment:", "analysis_environment" %in% names(saved_json)))
    
}, error = function(e_json) {
    print(paste("Error saving summary_list as JSON:", e_json$message))
})