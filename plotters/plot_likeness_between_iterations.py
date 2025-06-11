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

    data = {}

    iteration_index = 0
    master_results_file_path = results_directory_path.joinpath(f'iter_{iteration_index}').joinpath('master_results.json')
    next_master_results_file_path = results_directory_path.joinpath(f'iter_{iteration_index + 1}').joinpath('master_results.json')
    
    while master_results_file_path.exists() and next_master_results_file_path.exists():
        
        with open(master_results_file_path, 'r') as file:
            master_results = json.load(file)
        with open(next_master_results_file_path, 'r') as file:
            next_master_results = json.load(file)
        
        total_requests_number = 0
        equal_requests = 0

        for day_name, daily_scheduled in master_results['scheduled'].items():
            
            total_requests_number += len(daily_scheduled)
            
            for schedule_item in daily_scheduled:
            
                is_schedule_present = False
                for next_schedule_item in next_master_results['scheduled'][day_name]:
                    if schedule_item['patient'] == next_schedule_item['patient'] and schedule_item['service'] == next_schedule_item['service']:
                        is_schedule_present = True
                        equal_requests += 1
                        break
            
            data[iteration_index] = (equal_requests, total_requests_number)

        iteration_index += 1
        master_results_file_path = results_directory_path.joinpath(f'iter_{iteration_index}').joinpath('master_results.json')
        next_master_results_file_path = results_directory_path.joinpath(f'iter_{iteration_index + 1}').joinpath('master_results.json')
    
    xs = []
    ys = []

    for iteration_index in range(len(data)):

        xs.append(iteration_index)
        ys.append(data[iteration_index][0] / data[iteration_index][1])
    
    _, ax = plt.subplots()

    if len(xs) > 100:
        ax.plot(xs, ys, 'o', linewidth=0.5, markersize=0.75)
        plt.xticks([])
    else:
        ax.plot(xs, ys, 'o')
    
    ax.set_ylim([0, 1])
    
    plt.title(f'Equal requests percentage between iterations')
    plt.xlabel('Iteration')
    plt.ylabel('Equal requests percentage')

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('likeness_between_iterations.png')
    
    plt.savefig(plot_file_path)


    xms = []
    yms = []
    xss = []
    yss = []

    for iteration_index in range(len(data)):

        xms.append(iteration_index)
        yms.append(data[iteration_index][1])
        xss.append(iteration_index)
        yss.append(data[iteration_index][0])
    
    _, ax = plt.subplots()

    if len(xms) > 100:
        ax.plot(xms, yms, 'o-', linewidth=0.5, markersize=0.75, label='Total master requests')
        ax.plot(xss, yss, 'x-', linewidth=0.5, markersize=0.75, label='Equal requests')
        plt.xticks([])
    else:
        ax.plot(xms, yms, 'o-', label='Total master requests')
        ax.plot(xss, yss, 'x-', label='Equal requests')
    ax.legend()
    ax.set_ylim([0, None])

    plt.title(f'Requests between iterations')
    plt.xlabel('Iteration')
    plt.ylabel('Requests')

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('absolute_likeness_between_iterations.png')
    
    plt.savefig(plot_file_path)


    plt.close('all')