import matplotlib.pyplot as plt
import matplotlib.patches as patches
import json


def plot_subproblem_cumulative_times(all_master_results_info, all_subproblem_results_info, plot_file_path):

    time = 0
    xmas = []
    ymas = []
    xsub = []
    ysub = []

    for iteration_index, master_results_info in enumerate(all_master_results_info):

        time += master_results_info['model_solving_time']
        xmas.append(time)
        ymas.append(master_results_info['objective_function_value'])

        if iteration_index >= len(all_subproblem_results_info):
            continue

        objective_function_value_sum = 0
        for subproblem_results_info in all_subproblem_results_info[iteration_index].values():
            time += subproblem_results_info['model_solving_time']
            objective_function_value_sum += subproblem_results_info['objective_function_value']
        
        xsub.append(time)
        ysub.append(objective_function_value_sum)

    _, ax = plt.subplots()
    ax.plot(xmas, ymas, 'o-')
    if len(xsub) > 0:
        ax.plot(xsub, ysub, 'x-')
        ax.set_xlim(xmin=0, xmax=(xsub[-1] + 0.5))

    plt.title(f'Cumulated solving times')
    plt.xlabel('Time (s)')
    plt.ylabel('Objective function value')

    plt.savefig(plot_file_path)
    plt.close('all')


def plot_scatter_times(all_master_results_info, all_subproblem_results_info, plot_file_path):

    _, ax = plt.subplots()

    xs = []
    ys = []
    ylowererror = []
    yuppererror = []

    for iteration_index, iteration_subproblem_results_info in enumerate(all_subproblem_results_info):
        
        times = []
        
        for subproblem_results_info in iteration_subproblem_results_info.values():
            times.append(subproblem_results_info['model_solving_time'])

        times.sort()

        average_time = sum(times) / len(times)
        lower_error = abs(average_time - times[int(len(times) / 4)])
        upper_error = abs(times[int(len(times) / 4 * 3)] - average_time)

        xs.append(iteration_index)
        ys.append(average_time)
        ylowererror.append(lower_error)
        yuppererror.append(upper_error)
    
    ax.errorbar(xs, ys, yerr=[ylowererror, yuppererror], fmt='o', capsize=4, label='Subproblem')

    xs = []
    ys = []

    for iteration_index, iteration_master_results_info in enumerate(all_master_results_info):
        xs.append(iteration_index)
        ys.append(iteration_master_results_info['model_solving_time'])
    ax.plot(xs, ys, label='Master')

    ax.legend()

    plt.title(f'Solving time by iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Time (s)')

    plt.savefig(plot_file_path)
    plt.close('all')


def plot_cores(cores_directory_path, plot_file_path):

    iteration_index = 0
    cores_number = []
    cores_average_size = []

    iteration_cores_directory_path = cores_directory_path.joinpath(f'iter_{iteration_index}')
    while iteration_cores_directory_path.exists():

        cores_file_path = iteration_cores_directory_path.joinpath('cores.json')
        if not cores_file_path.exists():
            break
        
        with open(cores_file_path, 'r') as file:
            cores = json.load(file)

        cores_number.append(len(cores))

        cores_size_sum = 0
        for core in cores:
            cores_size_sum += len(core['components'])
        cores_average_size.append(cores_size_sum / len(cores))

        iteration_index += 1
        iteration_cores_directory_path = cores_directory_path.joinpath(f'iter_{iteration_index}')

    _, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 4))

    plt.sca(ax1)
    ax1.plot(range(len(cores_number)), cores_number)
    average_core_number = sum(cores_number) / len(cores_number)
    ax1.plot([0, len(cores_number)], [average_core_number, average_core_number], '--')
    ax1.set_title('Core number by iteration')
    ax1.set_ylabel('Core number')

    plt.sca(ax2)
    ax2.plot(range(len(cores_average_size)), cores_average_size)
    average_core_size = sum(cores_average_size) / len(cores_average_size)
    ax2.plot([0, len(cores_average_size)], [average_core_size, average_core_size], '--')
    ax2.set_title('Cores average size by iteration')
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Size')

    plt.tight_layout()
    plt.savefig(plot_file_path)
    plt.close('all')


def plot_all_instances_iteration_times(groups_directory_path, plot_file_path):

    group_paths = []
    for group_directory_path in groups_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue
        group_paths.append(group_directory_path)
    group_paths.sort()

    data = {}
    for group_path in group_paths:

        data[group_path.name] = {}
        
        analysis_directory_path = group_path.joinpath('analysis')
        for iteration_analysis_directory_path in analysis_directory_path.iterdir():

            if not iteration_analysis_directory_path.is_dir():
                continue
        
            iteration_index = int(iteration_analysis_directory_path.name.removeprefix('iter_'))
        
            analysis_file_path = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
            with open(analysis_file_path, 'r') as file:
                analysis = json.load(file)
            data[group_path.name][iteration_index] = analysis['model_solving_time']

    colors = 'bgrcmyk'
    _, ax = plt.subplots()

    column_width = 1
    column_space_between = 0.5

    max_time = 0
    group_index = 0
    group_names = []
    for group_name, group_data in data.items():    
        group_index += 1
        group_names.append(group_name)

        cumulate_time = 0
        for iteration_index in range(len(group_data)):
            iteration_time = group_data[iteration_index]
            ax.add_patch(patches.Rectangle(
                (group_index * column_space_between + (group_index - 1) * column_width, cumulate_time),
                column_width, iteration_time, facecolor=colors[iteration_index % len(colors)]))
            cumulate_time += iteration_time
        
        if cumulate_time > max_time:
            max_time = cumulate_time

    ax.set_xlim([0, group_index * (column_width + column_space_between) + column_space_between])
    ax.set_ylim([0, max_time * 1.1])

    ax.set_xticks([i * column_space_between + (i - 0.5) * column_width for i in range(1, group_index + 1)], labels=group_names)
    plt.xticks(rotation=90)
    ax.tick_params(axis='x', labelsize=5)

    plt.title(f'Solving time by instance and iteration')
    plt.xlabel('Instance')
    plt.ylabel('Time (s)')

    plt.tight_layout()
    plt.savefig(groups_directory_path.joinpath(plot_file_path))
    plt.close('all')


def plot_results_values_by_group(groups_directory_path, plot_file_path):

    group_paths = []
    for group_directory_path in groups_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue
        group_paths.append(group_directory_path)
    group_paths.sort()

    data = {}
    for group_path in group_paths:

        data[group_path.name] = {}
        
        analysis_directory_path = group_path.joinpath('analysis')
        for iteration_analysis_directory_path in analysis_directory_path.iterdir():

            if not iteration_analysis_directory_path.is_dir():
                continue
        
            iteration_index = int(iteration_analysis_directory_path.name.removeprefix('iter_'))
        
            analysis_file_path = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
            with open(analysis_file_path, 'r') as file:
                analysis = json.load(file)
            data[group_path.name][iteration_index] = analysis['solution_value']

    colors = 'bgrcmyk'
    fig, ax = plt.subplots()
    fig.set_size_inches(10, 8)

    color_map = {}

    for group_path in group_paths:
        group_name = group_path.name
        solution_values = data[group_name]
        
        
        xs = list(range(len(solution_values)))
        ys = [0 for _ in range(len(solution_values))]
        for iteration_index, solution_value in solution_values.items():
            ys[iteration_index] = solution_value

        group_prefix = group_name.split('_instance')[0]
        if group_prefix in color_map:
            ax.plot(xs, ys, color=color_map[group_prefix], alpha=0.75)
        else:
            color_map[group_prefix] = colors[len(color_map) % len(colors)]
            ax.plot(xs, ys, color=color_map[group_prefix], alpha=0.75, label=group_prefix)

    plt.legend(bbox_to_anchor=(1.04, 1), loc="upper left")

    plt.title(f'Results values by iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Solution value')

    plt.tight_layout()
    plt.savefig(groups_directory_path.joinpath(plot_file_path))
    plt.close('all')


def plot_results_values_by_instance(groups_directory_path, plot_file_path):

    group_paths = []
    for group_directory_path in groups_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue
        group_paths.append(group_directory_path)
    group_paths.sort()

    data = {}
    for group_path in group_paths:

        data[group_path.name] = {}
        
        analysis_directory_path = group_path.joinpath('analysis')
        for iteration_analysis_directory_path in analysis_directory_path.iterdir():

            if not iteration_analysis_directory_path.is_dir():
                continue
        
            iteration_index = int(iteration_analysis_directory_path.name.removeprefix('iter_'))
        
            analysis_file_path = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
            with open(analysis_file_path, 'r') as file:
                analysis = json.load(file)
            data[group_path.name][iteration_index] = analysis['solution_value']

    colors = 'bgrcmyk'
    fig, ax = plt.subplots()
    fig.set_size_inches(10, 8)

    color_map = {}

    for group_path in group_paths:
        group_name = group_path.name
        solution_values = data[group_name]
        
        xs = list(range(len(solution_values)))
        ys = [0 for _ in range(len(solution_values))]
        for iteration_index, solution_value in solution_values.items():
            ys[iteration_index] = solution_value

        instance_name = f'instance_{group_name.split('instance_')[1]}'
        if instance_name in color_map:
            ax.plot(xs, ys, color=color_map[instance_name], alpha=0.75)
        else:
            color_map[instance_name] = colors[len(color_map) % len(colors)]
            ax.plot(xs, ys, color=color_map[instance_name], alpha=0.75, label=instance_name)

    plt.legend(bbox_to_anchor=(1.04, 1), loc="upper left")

    plt.title(f'Results values by iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Solution value')

    plt.tight_layout()
    plt.savefig(groups_directory_path.joinpath(plot_file_path))
    plt.close('all')