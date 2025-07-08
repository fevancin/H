from pathlib import Path
import argparse
import json

from tools import plot_master_results
from tools import plot_subproblem_results


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

    if not group_directory_path.is_dir() or group_directory_path.name == 'analysis' or group_directory_path.name == 'plots':
        continue

    print(f'Start group {group_directory_path}')

    instance_file_path = group_directory_path.joinpath('input').joinpath('master_instance.json')
    results_directory_path = group_directory_path.joinpath('results')

    with open(instance_file_path, 'r') as file:
        instance = json.load(file)

    best_iteration_index = None
    best_solution_value = None

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
        if not final_results_file_path.exists():
            break
        
        with open(final_results_file_path, 'r') as file:
            final_results = json.load(file)

        solution_value = 0
        for day in final_results['scheduled'].values():
            for request in day:
                solution_value += instance['services'][request['service']]['duration'] * instance['patients'][request['patient']]['priority']
        
        if best_solution_value is None or solution_value > best_solution_value:
            best_iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))
            best_solution_value = solution_value

    if best_iteration_index is None:
        continue

    final_results_file_path = group_directory_path.joinpath('results').joinpath(f'iter_{best_iteration_index}').joinpath('final_results.json')
    with open(final_results_file_path, 'r') as file:
        results = json.load(file)
    
    plot_directory_path = groups_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    best_solution_plot_directory = plot_directory_path.joinpath(f'best_solution_iter_{best_iteration_index}_{group_directory_path.name}')
    best_solution_plot_directory.mkdir(exist_ok=True)

    best_final_solution_plot_file_path = best_solution_plot_directory.joinpath('final_results.png')
    plot_master_results(instance, results, best_final_solution_plot_file_path)
    
    for day_name in instance['days'].keys():

        subproblem_instance = {
            'services': instance['services'],
            'day': instance['days'][day_name]
        }
        subproblem_results = {
            'scheduled': results['scheduled'][day_name],
            'rejected': []
        }

        subproblem_results_file_path = group_directory_path.joinpath('results').joinpath(f'iter_{best_iteration_index}').joinpath(f'subproblem_day_{day_name}_results.json')
        if subproblem_results_file_path.exists():
            with open(subproblem_results_file_path, 'r') as file:
                true_subproblem_results = json.load(file)
            subproblem_results['rejected'] = true_subproblem_results['rejected']

        best_subproblem_solution_day_plot_file_path = best_solution_plot_directory.joinpath(f'subproblem_results_day_{day_name}.png')
        plot_subproblem_results(subproblem_instance, subproblem_results, best_subproblem_solution_day_plot_file_path)

    print(f'End group {group_directory_path}')