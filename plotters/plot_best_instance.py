from pathlib import Path
import argparse
import json

from plotters.final_results_plotter import plot_final_results
from plotters.subproblem_results_plotter import plot_subproblem_results


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot instances', description='Plot results')
parser.add_argument('-i', '--input', type=Path, help='Groups directory path', required=True)
args = parser.parse_args()

groups_directory_path = Path(args.input).resolve()

if not groups_directory_path.exists():
    raise ValueError(f'Groups directory \'{groups_directory_path}\' does not exists')
elif not groups_directory_path.is_dir():
    raise ValueError(f'Groups \'{groups_directory_path}\' is not a directory')

for group_directory_path in groups_directory_path.iterdir():

    if not group_directory_path.is_dir():
        continue

    print(f'Start group {group_directory_path}')

    analysis_directory_path = group_directory_path.joinpath('analysis')

    best_iteration_index = None
    best_solution_value = None

    for iteration_analysis_directory_path in analysis_directory_path.iterdir():

        if not iteration_analysis_directory_path.is_dir():
            continue


        final_results_analysis_file_path = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
        with open(final_results_analysis_file_path, 'r') as file:
            final_analysis = json.load(file)

        solution_value = final_analysis['solution_value']
        
        if best_solution_value is None or solution_value > best_solution_value:
            best_iteration_index = int(iteration_analysis_directory_path.name.removeprefix('iter_'))
            best_solution_value = solution_value
    
    input_directory_path = group_directory_path.joinpath('input')
    instance_file_path = None
    
    for instance_file_path in input_directory_path.iterdir():
        if instance_file_path.is_dir() or instance_file_path.suffix != '.json':
            continue
        break
    
    if instance_file_path is None:
        raise FileNotFoundError('Instance file not found')
    
    with open(instance_file_path, 'r') as file:
        instance = json.load(file)

    results_file_path = group_directory_path.joinpath('results').joinpath(f'iter_{best_iteration_index}').joinpath('final_results.json')
    if not results_file_path.exists():
        raise FileNotFoundError(f'Results file {results_file_path} does not exists')
    
    with open(results_file_path, 'r') as file:
        results = json.load(file)
    
    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    best_solution_plot_directory = plot_directory_path.joinpath(f'best_solution_iter_{best_iteration_index}')
    best_solution_plot_directory.mkdir(exist_ok=True)

    if 'days' in instance:
        
        best_final_solution_plot_file_path = best_solution_plot_directory.joinpath('final_results.png')
        plot_final_results(instance, results, best_final_solution_plot_file_path)
        
        for day_name in instance['days'].keys():

            subproblem_instance = {
                'services': instance['services'],
                'day': instance['days'][day_name]
            }
            subproblem_results = {
                'scheduled': results['scheduled'][day_name]
            }

            best_subproblem_solution_day_plot_file_path = best_solution_plot_directory.joinpath(f'subproblem_results_day_{day_name}.png')
            plot_subproblem_results(subproblem_instance, subproblem_results, best_subproblem_solution_day_plot_file_path)

    else:
        best_subproblem_solution_plot_file_path = best_solution_plot_directory.joinpath('subproblem_results.png')
        plot_subproblem_results(instance, results, best_subproblem_solution_plot_file_path)

    print(f'End group {group_directory_path}')