from analyzers.tools import get_master_results_value, analyze_master_results, common_main_analyzer


def get_final_results_value(master_instance, final_results):
    return get_master_results_value(master_instance, final_results)


def analyze_final_results(master_instance, final_results, instance_path):
    return analyze_master_results(master_instance, final_results, instance_path)


if __name__ == '__main__':

    common_main_analyzer(
        command_name='Final results analyzer',
        analyzer_function=analyze_final_results,
        analysis_file_name='final_results_analysis.csv',
        need_results=True)