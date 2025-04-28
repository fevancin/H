from analyzers.tools import common_main_analyzer


def analyze_subproblem_instance(subproblem_instance, instance_path):

    data = {}
    
    return data


if __name__ == '__main__':

    common_main_analyzer(
        command_name='Subproblem instance analyzer',
        analyzer_function=analyze_subproblem_instance,
        analysis_file_name='subproblem_instance_analysis.csv',
        need_results=False)