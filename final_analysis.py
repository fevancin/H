from pathlib import Path
import argparse
import json
import csv

from analyzers.master_instance_analyzer import analyze_master_instance
from analyzers.master_results_analyzer import analyze_master_results
from analyzers.final_results_analyzer import analyze_final_results

from plotters.aggregate_results_plotter import plot_all_instances_iteration_times
from plotters.aggregate_results_plotter import plot_results_values_by_group
from plotters.aggregate_results_plotter import plot_results_values_by_instance
from plotters.aggregate_results_plotter import plot_subproblem_cumulative_times
from plotters.aggregate_results_plotter import plot_solving_times
from plotters.aggregate_results_plotter import plot_cores

from plotters.aggregate_results_plotter import plot_solving_times_by_day
from plotters.aggregate_results_plotter import plot_free_slots


def get_all_master_results_info(results_directory_path):

    all_master_results_info = []
    iteration_index = 0
    
    iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
    while iteration_results_directory_path.exists():
        
        master_results_file_path = iteration_results_directory_path.joinpath('master_results.json')
        if not master_results_file_path.exists():
            return all_master_results_info
        
        with open(master_results_file_path, 'r') as file:
            master_results = json.load(file)
        all_master_results_info.append(master_results['info'])

        iteration_index += 1
        iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')

    return all_master_results_info


def get_all_subproblem_results_info(results_directory_path):

    all_subproblem_results_info = []
    iteration_index = 0

    iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
    while iteration_results_directory_path.exists():
    
        all_subproblem_results_info.append({})
        
        day_index = 0
        subproblem_results_file_path = iteration_results_directory_path.joinpath(f'subproblem_day_{day_index}_results.json')
        
        if not subproblem_results_file_path.exists():
            all_subproblem_results_info.pop()
            return all_subproblem_results_info
        
        while subproblem_results_file_path.exists():
            with open(subproblem_results_file_path, 'r') as file:
                subproblem_results = json.load(file)
        
            all_subproblem_results_info[-1][str(day_index)] = subproblem_results['info']
            day_index += 1
        
            subproblem_results_file_path = iteration_results_directory_path.joinpath(f'subproblem_day_{day_index}_results.json')

        iteration_index += 1
        iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
        
    return all_subproblem_results_info


def get_all_final_results_info(results_directory_path):

    all_final_results_info = []
    iteration_index = 0

    iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
    while iteration_results_directory_path.exists():

        final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
        if not final_results_file_path.exists():
            return all_final_results_info
        
        with open(final_results_file_path, 'r') as file:
            final_results = json.load(file)
        all_final_results_info.append(final_results['info'])

        iteration_index += 1
        iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
    
    return all_final_results_info


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Final analysis', description='Aggregate and plot results')
parser.add_argument('-i', '--input', type=Path, help='Groups directory path', required=True)
args = parser.parse_args()

groups_directory_path = Path(args.input).resolve()

if not groups_directory_path.exists():
    raise ValueError(f'Groups directory \'{groups_directory_path}\' does not exists')
elif not groups_directory_path.is_dir():
    raise ValueError(f'Groups \'{groups_directory_path}\' is not a directory')

plot_all_instances_iteration_times(groups_directory_path, 'instance_times.png')

plot_results_values_by_group(groups_directory_path, 'results_values_groups.png')
plot_results_values_by_instance(groups_directory_path, 'results_values_instances.png')

for group_directory_path in groups_directory_path.iterdir():

    if not group_directory_path.is_dir():
        continue

    print(f'Starting group {group_directory_path}')

    input_directory_path = group_directory_path.joinpath('input')
    results_directory_path = group_directory_path.joinpath('results')
    cores_directory_path = group_directory_path.joinpath('cores')

    if not input_directory_path.exists():
        raise ValueError(f'Input directory \'{input_directory_path}\' does not exists')
    elif not input_directory_path.is_dir():
        raise ValueError(f'Input directory \'{input_directory_path}\' is not a directory')

    if not results_directory_path.exists():
        raise ValueError(f'Results directory \'{results_directory_path}\' does not exists')
    elif not results_directory_path.is_dir():
        raise ValueError(f'Results directory \'{results_directory_path}\' is not a directory')

    all_master_results_info = get_all_master_results_info(results_directory_path)
    all_subproblem_results_info = get_all_subproblem_results_info(results_directory_path)
    all_final_results_info = get_all_final_results_info(results_directory_path)

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    if all_master_results_info is not None and all_subproblem_results_info is not None:
        plot_file_path = plot_directory_path.joinpath('cumulative_times.png')
        plot_subproblem_cumulative_times(all_master_results_info, all_subproblem_results_info, plot_file_path)

    if all_subproblem_results_info is not None:
        plot_file_path = plot_directory_path.joinpath('solving_times.png')
        plot_solving_times(all_master_results_info, all_subproblem_results_info, plot_file_path)

    if all_subproblem_results_info is not None:
        plot_file_path = plot_directory_path.joinpath('solving_times_by_day.png')
        plot_solving_times_by_day(all_subproblem_results_info, plot_file_path)

    plot_file_path = plot_directory_path.joinpath('cores.png')
    plot_cores(cores_directory_path, plot_file_path)

    master_instance_file_path = None
    for input_file_name in input_directory_path.iterdir():
        if input_file_name.suffix == '.json':
            master_instance_file_path = input_file_name
            break

    if master_instance_file_path is None:
        raise ValueError(f'Master instance not found')

    with open(master_instance_file_path, 'r') as file:
        master_instance = json.load(file)
    
    plot_file_path = plot_directory_path.joinpath('free_time_slots.png')
    
    all_final_results = {}
    results_directory_path = group_directory_path.joinpath('results')
    
    for iteration_results_path in results_directory_path.iterdir():
    
        if not iteration_results_path.is_dir():
            continue
    
        iteration_index = int(iteration_results_path.name.removeprefix('iter_'))
        final_results_file_path = iteration_results_path.joinpath('final_results.json')
    
        with open(final_results_file_path, 'r') as file:
            all_final_results[iteration_index] = json.load(file)
    
    plot_free_slots(master_instance, all_final_results, plot_file_path)

    analysis_directory_path = group_directory_path.joinpath('analysis')
    analysis_directory_path.mkdir(exist_ok=True)

    master_instance_analysis_file_path = analysis_directory_path.joinpath('master_instance_analysis.json')
    if not master_instance_analysis_file_path.exists():
        master_instance_analysis = analyze_master_instance(master_instance, master_instance_file_path)
        with open(master_instance_analysis_file_path, 'w') as file:
            json.dump(master_instance_analysis, file, indent=4)

    master_results_analysis_rows = []
    final_results_analysis_rows = []

    for iteration_results_directory_path in results_directory_path.iterdir():

        iteration_name = iteration_results_directory_path.name
        
        iteration_results_directory_path = results_directory_path.joinpath(iteration_name)
        master_results_file_name = iteration_results_directory_path.joinpath('master_results.json')
        if master_results_file_name.exists():
            with open(master_results_file_name, 'r') as file:
                master_results = json.load(file)
        else:
            master_results = None
        final_results_file_name = iteration_results_directory_path.joinpath('final_results.json')
        if final_results_file_name.exists():
            with open(final_results_file_name, 'r') as file:
                final_results = json.load(file)
        else:
            final_results = None
        
        iteration_analysis_directory_path = analysis_directory_path.joinpath(iteration_name)
        master_results_analysis_file_name = iteration_analysis_directory_path.joinpath('master_results_analysis.json')
        final_results_analysis_file_name = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
        
        if master_results is not None:
            if not master_results_analysis_file_name.exists():
                master_results_analysis = analyze_master_results(master_instance, master_results, master_instance_file_path)
                master_results_analysis['iteration'] = iteration_name
                with open(master_results_analysis_file_name, 'w') as file:
                    json.dump(master_results_analysis, file, indent=4)
            else:
                with open(master_results_analysis_file_name, 'r') as file:
                    master_results_analysis = json.load(file)
                master_results_analysis['iteration'] = iteration_name

            master_results_analysis_rows.append(master_results_analysis)

        if final_results is not None:
            if not final_results_analysis_file_name.exists():
                final_results_analysis = analyze_final_results(master_instance, final_results, master_instance_file_path)
                final_results_analysis['iteration'] = iteration_name
                with open(final_results_analysis_file_name, 'w') as file:
                    json.dump(final_results_analysis, file, indent=4)
            else:
                with open(final_results_analysis_file_name, 'r') as file:
                    final_results_analysis = json.load(file)
                final_results_analysis['iteration'] = iteration_name
        
            final_results_analysis_rows.append(final_results_analysis)

    if len(master_results_analysis_rows) > 0:
        with open(analysis_directory_path.joinpath('master_results.csv'), 'w', newline='') as file:
            fieldnames = list(master_results_analysis_rows[0].keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for master_results_analysis_row in master_results_analysis_rows:
                writer.writerow(master_results_analysis_row)

    if len(final_results_analysis_rows) > 0:
        with open(analysis_directory_path.joinpath('final_results.csv'), 'w', newline='') as file:
            fieldnames = list(final_results_analysis_rows[0].keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for final_results_analysis_row in final_results_analysis_rows:
                writer.writerow(final_results_analysis_row)
                
    print(f'Ending group {group_directory_path}')