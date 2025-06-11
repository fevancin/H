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

    results_directory_path = group_directory_path.joinpath('results')

    master_data = {}
    final_data = {}

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))

        master_results_file_path = iteration_results_directory_path.joinpath('master_results.json')
        if not master_results_file_path.exists():
            raise FileNotFoundError(f'Results file {master_results_file_path} not found')
        with open(master_results_file_path, 'r') as file:
            master_results = json.load(file)
        
        final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
        if not final_results_file_path.exists():
            raise FileNotFoundError(f'Results file {final_results_file_path} not found')
        with open(final_results_file_path, 'r') as file:
            final_results = json.load(file)
        
        patient_names = set()
        master_data[iteration_index] = 0
        for day_name, daily_scheduled in master_results['scheduled'].items():
            for schedule_item in daily_scheduled:
                patient_names.add(schedule_item['patient'])
            master_data[iteration_index] += len(daily_scheduled)
        master_data[iteration_index] /= len(patient_names)
        
        final_data[iteration_index] = 0
        for day_name, daily_scheduled in final_results['scheduled'].items():
            final_data[iteration_index] += len(daily_scheduled)
        final_data[iteration_index] /= len(patient_names)

    xmas = []
    ymas = []
    xfin = []
    yfin = []

    for iteration_index in range(len(master_data)):

        xmas.append(iteration_index)
        ymas.append(master_data[iteration_index])
        xfin.append(iteration_index)
        yfin.append(final_data[iteration_index])
    
    _, ax = plt.subplots()

    if len(xmas) > 100:
        ax.plot(xmas, ymas, 'o-', linewidth=0.5, markersize=0.75, label='master')
        ax.plot(xfin, yfin, 'x-', linewidth=0.5, markersize=0.75, label='final')
        plt.xticks([])
    else:
        ax.plot(xmas, ymas, 'o-', label='master')
        ax.plot(xfin, yfin, 'x-', label='subproblem')

    ax.legend()

    plt.title(f'Average requests per patient by iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Average requests per patient')

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('average_requests_per_patient.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')