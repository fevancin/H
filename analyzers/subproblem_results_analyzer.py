from analyzers.tools import common_main_analyzer


def analyze_subproblem_results(subproblem_instance, subproblem_results, instance_path):

    data = {}
    
    return data


if __name__ == '__main__':

    common_main_analyzer(
        command_name='Subproblem results analyzer',
        analyzer_function=analyze_subproblem_results,
        analysis_file_name='subproblem_results_analysis.csv',
        need_results=True)