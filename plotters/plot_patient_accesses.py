from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot patient accesses')
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
    average_days_used_per_iteration = dict()

    max_day_index = None

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))
        iteration_indexes.add(iteration_index)

        final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
        with open(final_results_file_path, 'r') as file:
            final_results = json.load(file)
        
        days_used_by_patient = dict()
        for daily_scheduled in final_results['scheduled'].values():
            for schedule in daily_scheduled:
                patient_name = schedule['patient']
                if patient_name not in days_used_by_patient:
                    days_used_by_patient[patient_name] = 0
                days_used_by_patient[patient_name] += 1
        average_days_used_per_iteration[iteration_index] = sum(days_used_by_patient[p] for p in days_used_by_patient) / len(days_used_by_patient)
        
        if max_day_index is None:
            max_day_index = len(final_results['scheduled'])
        
    average_days_used_per_iteration = [average_days_used_per_iteration[iteration_index] for iteration_index in range(len(iteration_indexes))]

    fig, ax = plt.subplots()

    iteration_indexes = list(iteration_indexes)

    ax.plot(iteration_indexes, average_days_used_per_iteration, '-')
    ax.plot([0, len(iteration_indexes) - 1], [max_day_index + 1, max_day_index + 1], 'r--')
    ax.set(xlabel='Iteration', ylabel='Hospital trips')
    ax.set_ylim([0, None])
    ax.set_title('Average patient\'s days used per iteration')

    ax.text(0, max_day_index - 0.5, 'Day number', color='r')

    plt.tight_layout()

    if len(iteration_indexes) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('patient_accesses.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')