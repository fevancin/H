from analyzers.tools import analyze_master_results, common_main_analyzer


if __name__ == '__main__':

    common_main_analyzer(
        command_name='Master results analyzer',
        analyzer_function=analyze_master_results,
        analysis_file_name='master_results_analysis.csv',
        need_results=True)