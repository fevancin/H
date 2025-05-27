from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt


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

    analysis_directory_path = group_directory_path.joinpath('analysis')

    cores_data = {}

    for iteration_analysis_directory_path in analysis_directory_path.iterdir():

        if not iteration_analysis_directory_path.is_dir():
            continue

        iteration_index = int(iteration_analysis_directory_path.name.removeprefix('iter_'))

        cores_file_path = iteration_analysis_directory_path.joinpath('core_analysis.json')
        if not cores_file_path.exists():
            continue
        with open(cores_file_path, 'r') as file:
            cores = json.load(file)
        
        cores_data[iteration_index] = cores

    xs = []
    y1 = []
    y2 = []
    y3 = []
    y4 = []
    y5 = []

    for iteration_index, data in cores_data.items():

        xs.append(iteration_index)

        y1.append(data['core_number_pre_expansion'])
        y2.append(data['core_number_post_name_expansion'])

        y3.append(data['average_core_size_pre_expansion'])
        y4.append(data['average_core_size_post_name_expansion'])

        y5.append(data['day_with_cores_pre_expansion'])
    
    _, axs = plt.subplots(2)

    axs[0].plot(xs, y1, 'o-', linewidth=0.5, markersize=0.75, label='pre expansion')
    axs[0].plot(xs, y2, 'x-', linewidth=0.5, markersize=0.75, label='post expansion')
    axs[0].legend()
    axs[0].set_title(f'Cores')
    axs[0].set(ylabel='Average core number')

    axs[1].plot(xs, y3, 'o-', linewidth=0.5, markersize=0.75, label='pre expansion')
    axs[1].plot(xs, y4, 'x-', linewidth=0.5, markersize=0.75, label='post expansion')
    axs[1].legend()
    axs[1].set(ylabel='Average core size', xlabel='Iteration')

    if len(xs) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('cores.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')