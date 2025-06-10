from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt
import csv


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot cores')
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

    cores_directory_path = group_directory_path.joinpath('cores')
    analysis_directory_path = group_directory_path.joinpath('analysis')

    cores_analysis_data = {}

    for iteration_analysis_directory_path in analysis_directory_path.iterdir():

        if not iteration_analysis_directory_path.is_dir():
            continue

        iteration_index = int(iteration_analysis_directory_path.name.removeprefix('iter_'))

        cores_analysis_file_path = iteration_analysis_directory_path.joinpath('core_analysis.json')
        if not cores_analysis_file_path.exists():
            continue
        with open(cores_analysis_file_path, 'r') as file:
            cores_analysis = json.load(file)
        
        cores_analysis_data[iteration_index] = cores_analysis

    cores_data = {}

    cores_directory_path = group_directory_path.joinpath('cores')
    for iteration_cores_directory_path in cores_directory_path.iterdir():

        if not iteration_cores_directory_path.is_dir():
            continue

        iteration_index = int(iteration_cores_directory_path.name.removeprefix('iter_'))

        cores_file_path = iteration_cores_directory_path.joinpath('cores.json')
        if not cores_file_path.exists():
            continue
        with open(cores_file_path, 'r') as file:
            cores = json.load(file)
        
        iteration_cores_data = {}

        for core in cores:
            for day_name in core['days']:
                if day_name not in iteration_cores_data:
                    iteration_cores_data[day_name] = 0
                iteration_cores_data[day_name] += 1
        
        cores_data[iteration_index] = iteration_cores_data

    xs = []
    ys = []
    for iteration_index, iteration_cores_data in cores_data.items():
        for day_name, day_value in iteration_cores_data.items():
            xs.append(iteration_index)
            ys.append(day_value)
    
    xxs = []
    yys = []
    yyys = []
    for iteration_index, data in cores_analysis_data.items():
        xxs.append(iteration_index)
        yys.append(data['percentage_of_core_equal_to_master_request'])
        yyys.append(data['average_percentage_of_core_done_by_subproblem'])

    _, axs = plt.subplots(2)

    # axs[0].plot(xs, ys, 'o')
    # axs[0].set_title(f'Cores divided by day')
    # axs[0].set(ylabel='Core number')

    axs[0].plot(xxs, yys, 'o')
    axs[0].set_title(f'When core is equal to master request')
    axs[0].set(ylabel='Percentage')
    axs[0].set_ylim([0, 1])

    axs[1].plot(xxs, yyys, 'o')
    axs[1].set_title(f'Percentage of core satisfied by SP')
    axs[1].set(ylabel='Percentage', xlabel='Iteration')
    axs[1].set_ylim([0, 1])
    
    plt.tight_layout()

    if len(xs) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('core_number_by_day.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')