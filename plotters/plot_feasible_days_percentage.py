from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot feasible days')
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
    rejected_requests_per_iteration = dict()
    fully_scheduled_days_per_iteration = dict()

    max_day_index = 0

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))
        iteration_indexes.add(iteration_index)

        rejected_requests_per_iteration[iteration_index] = 0
        fully_scheduled_days_per_iteration[iteration_index] = 0

        for day_results_file_path in iteration_results_directory_path.iterdir():
            if day_results_file_path.suffix != '.json':
                continue
            if not day_results_file_path.name.startswith('subproblem'):
                continue
            with open(day_results_file_path, 'r') as file:
                subproblem_results = json.load(file)
            rejected_requests_per_iteration[iteration_index] += len(subproblem_results['rejected'])
            if len(subproblem_results['rejected']) == 0:
                fully_scheduled_days_per_iteration[iteration_index] += 1
            day_index = int(day_results_file_path.stem.removeprefix('subproblem_day_').removesuffix('_results'))
            if day_index > max_day_index:
                max_day_index = day_index

    rejected_requests_per_iteration = [rejected_requests_per_iteration[i] for i in range(len(rejected_requests_per_iteration))]
    fully_scheduled_days_per_iteration = [fully_scheduled_days_per_iteration[i] / max_day_index for i in range(len(fully_scheduled_days_per_iteration))]

    fig, axs = plt.subplots(2)

    iteration_indexes = list(iteration_indexes)

    axs[0].plot(iteration_indexes, rejected_requests_per_iteration, '-')
    axs[0].plot([0, len(iteration_indexes) - 1], [max_day_index + 1, max_day_index + 1], 'r--')
    axs[0].set(xlabel='Iteration', ylabel='Rejected request number')
    axs[0].set_title('Number of rejected requests per iteration')
    
    axs[1].plot(iteration_indexes, fully_scheduled_days_per_iteration, '-')
    axs[1].set(xlabel='Iteration', ylabel='Percentage')
    axs[1].set_title('Percentage of days fully satisfied per iteration')
    axs[1].set_ylim([0, 1])

    axs[0].text(0, max_day_index - 2, 'Day number', color='r')

    plt.tight_layout()

    if len(iteration_indexes) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('fully_scheduled_days.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')