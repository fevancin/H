from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt


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

group_paths = []
for group_directory_path in groups_directory_path.iterdir():
    if not group_directory_path.is_dir():
        continue
    group_paths.append(group_directory_path)
group_paths.sort()

for group_directory_path in group_paths:

    if not group_directory_path.is_dir():
        continue

    input_directory_path = group_directory_path.joinpath('input')
    instance_file_path = None
    
    for instance_file_path in input_directory_path.iterdir():
        if instance_file_path.is_dir() or instance_file_path.suffix != '.json':
            continue
        break
    
    if instance_file_path is None:
        raise FileNotFoundError('Instance file not found')
    
    with open(instance_file_path, 'r') as file:
        master_instance = json.load(file)

    results_directory_path = group_directory_path.joinpath('results')

    daily_total_capacity = {}
    for day_name, day in master_instance['days'].items():
        daily_total_capacity[day_name] = 0
        for care_unit in day.values():
            for operator in care_unit.values():
                daily_total_capacity[day_name] += operator['duration']

    data = {}

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))
        data[iteration_index] = []

        final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
        
        if not final_results_file_path.exists():
            raise FileNotFoundError(f'Results file {final_results_file_path} not found')
        
        with open(final_results_file_path, 'r') as file:
            final_results = json.load(file)
        
        for day_name, daily_scheduled in final_results['scheduled'].items():

            scheduled_total_duration = 0
            for schedule_item in daily_scheduled:
                scheduled_total_duration += master_instance['services'][schedule_item['service']]['duration']
            
            data[iteration_index].append(daily_total_capacity[day_name] - scheduled_total_duration)

    xs = []
    ys = []
    ylowererror = []
    yuppererror = []

    for iteration_index, iteration_free_time_slots in data.items():

        iteration_free_time_slots.sort()

        average_time = sum(iteration_free_time_slots) / len(iteration_free_time_slots)
        lower_error = abs(average_time - iteration_free_time_slots[int(len(iteration_free_time_slots) / 4)])
        upper_error = abs(iteration_free_time_slots[int(len(iteration_free_time_slots) / 4 * 3)] - average_time)

        xs.append(iteration_index)
        ys.append(average_time)
        ylowererror.append(lower_error)
        yuppererror.append(upper_error)
    
    _, ax = plt.subplots()

    ax.errorbar(xs, ys, yerr=[ylowererror, yuppererror], fmt='o', capsize=1, linewidth=0.25, markersize=0.75)
    if len(xs) > 100:
        plt.xticks([])

    plt.title(f'Rejected slots by iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Slots rejected')


    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('rejected_slots_by_iteration.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')