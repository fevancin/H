from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot rejected requests')
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

    results_directory_path = group_directory_path.joinpath('results')

    iteration_indexes = set()
    
    rejected_requests_per_day_per_iteration = dict()
    rejected_requests_numbers = set()
    max_day_index = 0

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))
        iteration_indexes.add(iteration_index)

        rejected_requests_per_day_per_iteration[iteration_index] = {}

        for day_results_file_path in iteration_results_directory_path.iterdir():
            
            if day_results_file_path.suffix != '.json':
                continue
            if not day_results_file_path.name.startswith('subproblem'):
                continue

            with open(day_results_file_path, 'r') as file:
                subproblem_results = json.load(file)
            
            rejected_requests_number = len(subproblem_results['rejected'])
            if rejected_requests_number not in rejected_requests_per_day_per_iteration[iteration_index]:
                rejected_requests_per_day_per_iteration[iteration_index][rejected_requests_number] = 0
            rejected_requests_per_day_per_iteration[iteration_index][rejected_requests_number] += 1

            rejected_requests_numbers.add(rejected_requests_number)
            
            day_index = int(day_results_file_path.stem.removeprefix('subproblem_day_').removesuffix('_results'))
            if day_index > max_day_index:
                max_day_index = day_index

    rows = []

    for rejected_requests_number in sorted(rejected_requests_numbers):
        
        row = []
        
        for iteration_index in range(len(rejected_requests_per_day_per_iteration)):
            iteration_data = rejected_requests_per_day_per_iteration[iteration_index]
            
            if rejected_requests_number == 0:
                prev_cumulate_value = 0
            else:
                prev_cumulate_value = rows[-1][iteration_index]
            
            if rejected_requests_number in iteration_data:
                row.append(prev_cumulate_value + iteration_data[rejected_requests_number])
            else:
                row.append(prev_cumulate_value)

        rows.append(row)

    fig, ax = plt.subplots()

    iteration_indexes = list(iteration_indexes)

    for row_index, row in enumerate(rows):
        # ax.plot(iteration_indexes, row, '-', label=f'{row_index} rejected')
        plt.fill_between(iteration_indexes, row, '-', label=f'{row_index} rejected', zorder=-row_index)
    
    ax.set_ylim([0, max_day_index + 1])
    if len(iteration_indexes) > 1:
        ax.set_xlim([0, len(iteration_indexes) - 1])
    plt.yticks([i for i in range(max_day_index + 2)], [i for i in range(max_day_index + 2)])

    ax.set(xlabel='Iteration', ylabel='Day number')
    ax.set_title('Number of days per iteration grouped by number of rejected requests')
    ax.legend(loc='lower left')

    plt.tight_layout()

    if len(iteration_indexes) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('grouped_rejected_days.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')