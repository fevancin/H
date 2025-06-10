from pathlib import Path
import argparse
import matplotlib.pyplot as plt


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Plot logs')
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

    logs_directory_path = group_directory_path.joinpath('logs')

    iteration_indexes = set()

    master_log_data_rows = dict()
    master_log_data_columns = dict()
    master_log_data_nonzero = dict()
    master_log_data_rows_presolved = dict()
    master_log_data_columns_presolved = dict()
    master_log_data_nonzero_presolved = dict()

    subproblem_log_data_rows = dict()
    subproblem_log_data_columns = dict()
    subproblem_log_data_nonzero = dict()
    subproblem_log_data_rows_presolved = dict()
    subproblem_log_data_columns_presolved = dict()
    subproblem_log_data_nonzero_presolved = dict()

    for iteration_logs_directory_path in logs_directory_path.iterdir():

        if not iteration_logs_directory_path.is_dir():
            continue

        iteration_index = int(iteration_logs_directory_path.name.removeprefix('iter_'))
        iteration_indexes.add(iteration_index)

        subproblem_log_data_rows[iteration_index] = 0
        subproblem_log_data_columns[iteration_index] = 0
        subproblem_log_data_nonzero[iteration_index] = 0
        subproblem_log_data_rows_presolved[iteration_index] = 0
        subproblem_log_data_columns_presolved[iteration_index] = 0
        subproblem_log_data_nonzero_presolved[iteration_index] = 0

        subproblem_number = 0

        for log_file_path in iteration_logs_directory_path.iterdir():
            if log_file_path.suffix != '.log':
                continue
            with open(log_file_path, 'r') as file:
                for line in file:
                    
                    if line.startswith('Optimize a model with '):
                        tokens = line.split(' ')
                        if log_file_path.stem == 'master_log':
                            master_log_data_rows[iteration_index] = int(tokens[4])
                            master_log_data_columns[iteration_index] = int(tokens[6])
                            master_log_data_nonzero[iteration_index] = int(tokens[9])
                        else:
                            subproblem_number += 1
                            subproblem_log_data_rows[iteration_index] += int(tokens[4])
                            subproblem_log_data_columns[iteration_index] += int(tokens[6])
                            subproblem_log_data_nonzero[iteration_index] += int(tokens[9])
                    
                    elif line.startswith('Presolved: '):
                        tokens = line.split(' ')
                        if log_file_path.stem == 'master_log':
                            master_log_data_rows_presolved[iteration_index] = int(tokens[1])
                            master_log_data_columns_presolved[iteration_index] = int(tokens[3])
                            master_log_data_nonzero_presolved[iteration_index] = int(tokens[5])
                        else:
                            subproblem_log_data_rows_presolved[iteration_index] += int(tokens[1])
                            subproblem_log_data_columns_presolved[iteration_index] += int(tokens[3])
                            subproblem_log_data_nonzero_presolved[iteration_index] += int(tokens[5])
        
        subproblem_log_data_rows[iteration_index] /= subproblem_number
        subproblem_log_data_columns[iteration_index] /= subproblem_number
        subproblem_log_data_nonzero[iteration_index] /= subproblem_number
        subproblem_log_data_rows_presolved[iteration_index] /= subproblem_number
        subproblem_log_data_columns_presolved[iteration_index] /= subproblem_number
        subproblem_log_data_nonzero_presolved[iteration_index] /= subproblem_number

    master_log_data_rows = [master_log_data_rows[i] for i in range(len(master_log_data_rows))]
    master_log_data_columns = [master_log_data_columns[i] for i in range(len(master_log_data_columns))]
    master_log_data_nonzero = [master_log_data_nonzero[i] for i in range(len(master_log_data_nonzero))]
    subproblem_log_data_rows = [subproblem_log_data_rows[i] for i in range(len(subproblem_log_data_rows))]
    subproblem_log_data_columns = [subproblem_log_data_columns[i] for i in range(len(subproblem_log_data_columns))]
    subproblem_log_data_nonzero = [subproblem_log_data_nonzero[i] for i in range(len(subproblem_log_data_nonzero))]
    master_log_data_rows_presolved = [master_log_data_rows_presolved[i] for i in range(len(master_log_data_rows_presolved))]
    master_log_data_columns_presolved = [master_log_data_columns_presolved[i] for i in range(len(master_log_data_columns_presolved))]
    master_log_data_nonzero_presolved = [master_log_data_nonzero_presolved[i] for i in range(len(master_log_data_nonzero_presolved))]
    subproblem_log_data_rows_presolved = [subproblem_log_data_rows_presolved[i] for i in range(len(subproblem_log_data_rows_presolved))]
    subproblem_log_data_columns_presolved = [subproblem_log_data_columns_presolved[i] for i in range(len(subproblem_log_data_columns_presolved))]
    subproblem_log_data_nonzero_presolved = [subproblem_log_data_nonzero_presolved[i] for i in range(len(subproblem_log_data_nonzero_presolved))]

    fig, axs = plt.subplots(2)
    fig.suptitle(f'Variable and constraint number of the master model')

    iteration_indexes = list(iteration_indexes)

    axs[0].plot(iteration_indexes, master_log_data_rows, '-', label='rows')
    axs[0].plot(iteration_indexes, master_log_data_columns, '-', label='columns')
    axs[0].plot(iteration_indexes, master_log_data_rows_presolved, '-', label='presolved rows')
    axs[0].plot(iteration_indexes, master_log_data_columns_presolved, '-', label='presolved columns')
    axs[0].set(xlabel='Iteration', ylabel='Number of components')
    axs[0].set_title('Rows and columns')
    axs[0].legend(loc='lower left', ncol=2)
    
    axs[1].plot(iteration_indexes, master_log_data_nonzero, '-', label='master')
    axs[1].plot(iteration_indexes, master_log_data_nonzero_presolved, '-', label='presolved')
    axs[1].set(xlabel='Iteration', ylabel='Number of components')
    axs[1].set_title('Nonzeros')
    axs[1].legend()
    
    plt.tight_layout()

    if len(iteration_indexes) > 100:
        plt.xticks([])

    plot_directory_path = group_directory_path.joinpath('plots')
    plot_directory_path.mkdir(exist_ok=True)

    plot_file_path = plot_directory_path.joinpath('model_components.png')
    
    plt.savefig(plot_file_path)
    plt.close('all')