from pathlib import Path
import argparse
import json
import matplotlib.pyplot as plt


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot patient request number')
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
    
    patient_request_number = dict()
    numbers = set()

    for iteration_results_directory_path in results_directory_path.iterdir():

        if not iteration_results_directory_path.is_dir():
            continue

        iteration_index = int(iteration_results_directory_path.name.removeprefix('iter_'))
        iteration_indexes.add(iteration_index)

        master_results_file_path = iteration_results_directory_path.joinpath('master_results.json')
        with open(master_results_file_path, 'r') as file:
            master_results = json.load(file)

        patient_request_number[iteration_index] = {}

        for day_requests in master_results['scheduled'].values():
            
            patients = {}

            for request in day_requests:
                if request['patient'] not in patients:
                    patients[request['patient']] = 0
                patients[request['patient']] += 1
            
            for value in patients.values():
                
                if value not in patient_request_number[iteration_index]:
                    patient_request_number[iteration_index][value] = 0
                
                patient_request_number[iteration_index][value] += 1
            
            for value in patients.values():
                numbers.add(value)


    numbers = sorted(numbers)
    rows = []

    max_value_in_graph = 0

    for number in numbers:
        
        row = []
        
        for iteration_index in range(len(patient_request_number)):
            iteration_data = patient_request_number[iteration_index]
            
            if number == numbers[0]:
                prev_cumulate_value = 0
            else:
                prev_cumulate_value = rows[-1][iteration_index]
            
            if number in iteration_data:
                value = prev_cumulate_value + iteration_data[number]
                row.append(value)
                if value > max_value_in_graph:
                    max_value_in_graph = value
            else:
                row.append(prev_cumulate_value)

        rows.append(row)

    fig, ax = plt.subplots()

    iteration_indexes = list(iteration_indexes)

    for row_index, row in enumerate(rows):
        # ax.plot(iteration_indexes, row, '-', label=f'{row_index} rejected')
        plt.fill_between(iteration_indexes, row, '-', label=f'{numbers[row_index]} requests', zorder=-row_index)
    
    # ax.set_ylim([0, max_day_index + 1])
    ax.set_xlim([0, len(iteration_indexes) - 1])
    ax.set_yticks([i * max_value_in_graph / 10 for i in range(10)], [i * max_value_in_graph / 10 for i in range(10)])

    ax.set(xlabel='Iteration', ylabel='Patient number')
    ax.set_title('Number of patients per iteration grouped by requests in same day')
    ax.legend(loc='lower right')

    plt.tight_layout()

    if len(iteration_indexes) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('patient_requests_by_number.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')