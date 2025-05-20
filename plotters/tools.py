from pathlib import Path
import argparse
import json
import time
import shutil
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.patches import Patch


def plot_master_results(instance, results, plot_file_path):

    fig, (ax1, ax2) = plt.subplots(2, 1)
    fig.set_size_inches(16, 8)

    slot_width = 2.0
    space_between_days = 0.2 * slot_width
    colors = 'rgbcmy'

    day_number = len(instance['days'])

    # tracks care_unit bar position
    care_unit_x_position = 0
    care_unit_x_positions = {}
    day_x_positions = {}

    max_total_care_unit_duration = 0
    care_unit_names = set()

    # draw upper graphic (total care unit requests per each day)
    plt.sca(ax1)

    for day_name, day in instance['days'].items():

        care_unit_x_positions[day_name] = {}
        day_x_positions[day_name] = care_unit_x_position + len(day) * slot_width * 0.5
        
        for care_unit_name, care_unit in day.items():

            care_unit_names.add(care_unit_name)
            care_unit_x_positions[day_name][care_unit_name] = care_unit_x_position

            total_care_unit_duration = 0
            for operator in care_unit.values():
                total_care_unit_duration += operator['duration']
            
            if total_care_unit_duration > max_total_care_unit_duration:
                max_total_care_unit_duration = total_care_unit_duration

            # each care unit has an horizontal bold line indicating its own total duration
            plt.hlines(xmin=care_unit_x_position, xmax=care_unit_x_position + slot_width, y=total_care_unit_duration, colors='black', lw=2, zorder=0)
            
            care_unit_x_position += slot_width

        care_unit_x_position += space_between_days

    last_care_unit_x_position = care_unit_x_position
    day_x_positions[str(day_number)] = last_care_unit_x_position + space_between_days * 0.5

    # draw thin vertical lines between each day
    for positions in care_unit_x_positions.values():

        if len(positions) == 0:
            continue

        # find the first bar x position
        min_care_unit_x_position = 100000
        for care_unit_x_position in positions.values():
            if care_unit_x_position < min_care_unit_x_position:
                min_care_unit_x_position = care_unit_x_position

        plt.vlines(x=(min_care_unit_x_position - space_between_days * 0.5), ymin = 0, ymax=max_total_care_unit_duration, colors='grey', lw=0.5, ls=':', zorder=0)
    # last day right vertical line
    plt.vlines(x=(last_care_unit_x_position + space_between_days * 0.5), ymin = 0, ymax=max_total_care_unit_duration, colors='grey', lw=0.5, ls=':', zorder=0)

    # assign a color to each care unit encountered
    care_unit_colors = {}
    for care_unit_index, care_unit_name in enumerate(care_unit_names):
        care_unit_colors[care_unit_name] = colors[int(care_unit_index % len(colors))]

    # draw boxes
    care_unit_heights = {}
    for day_name, day_requests in results['scheduled'].items():
        for request in day_requests:
            patient_name = request['patient']
            service_name = request['service']
                
            care_unit_name = instance['services'][service_name]['care_unit']
            duration = instance['services'][service_name]['duration']

            if day_name not in care_unit_heights:
                care_unit_heights[day_name] = {}
            if care_unit_name not in care_unit_heights[day_name]:
                care_unit_heights[day_name][care_unit_name] = 0

            ax1.add_patch(Rectangle(
                (care_unit_x_positions[day_name][care_unit_name] + space_between_days, care_unit_heights[day_name][care_unit_name]),
                slot_width - space_between_days,
                duration,
                linewidth=1, edgecolor='k', lw=1.5,
                facecolor=care_unit_colors[care_unit_name], zorder=1))
            
            care_unit_heights[day_name][care_unit_name] += duration

    # creation of the legend with all care unit colors
    patch_list = []
    for care_unit_name, care_unit_color in care_unit_colors.items():
        patch_list.append(Patch(facecolor=care_unit_color, label=care_unit_name))
    ax1.legend(handles=patch_list)

    ax1.set_xticks(list(day_x_positions.values())[:-1], labels=list(care_unit_x_positions.keys()))

    ax1.set_title('Care unit total occupation')
    ax1.set_ylabel('Total request slots', weight='bold', labelpad=8)

    # draw lower graphic (patient protocol requests)
    plt.sca(ax2)

    # vertical position of the boxes
    request_y_position = 0

    slot_height = 1.0
    space_between_rows = slot_height * 0.2

    request_labels = {}
    request_y_positions = {}

    # draw request intervals
    for patient_name, patient in instance['patients'].items():
        for protocol in patient['protocols'].values():
            initial_shift = protocol['initial_shift']
            for service_protocol in protocol['protocol_services']:

                service_start = service_protocol['start']
                frequency = service_protocol['frequency']
                tolerance = service_protocol['tolerance']
                care_unit_name = instance['services'][service_protocol['service']]['care_unit']
                
                request_labels[request_y_position + 0.5 * slot_height] = f'{patient_name} - {service_protocol["service"]}'
                request_y_positions[(patient_name, service_protocol['service'])] = request_y_position + 0.5 * slot_height

                for index in range(service_protocol['times']):

                    start = initial_shift + service_start + frequency * index - tolerance
                    end = initial_shift + service_start + frequency * index + tolerance + 1

                    # clamp the window to [0; day_number] and discard fully-outside windows
                    if start >= day_number:
                        continue
                    if start < 0:
                        start = 0
                        if end < 0:
                            continue
                    if end < 0:
                        continue
                    if end > day_number:
                        end = day_number
                        if start > day_number:
                            continue
                    
                    start_day_len = len(instance['days'][str(start)])
                    if end == day_number:
                        end_day_len = 0
                    else:
                        end_day_len = len(instance['days'][str(end)])

                    start = day_x_positions[str(start)] - start_day_len * slot_width * 0.5
                    end = day_x_positions[str(end)] - end_day_len * slot_width * 0.5

                    plt.hlines(
                        xmin=start, xmax=end,
                        y=request_y_position + space_between_rows + (slot_height - space_between_rows) * 0.5,
                        lw=2, colors=care_unit_colors[care_unit_name], zorder=2)
                    plt.vlines(
                        x=start,
                        ymin=request_y_position + space_between_rows + space_between_rows,
                        ymax=request_y_position + space_between_rows + (slot_height - space_between_rows * 2),
                        lw=1.5, colors=care_unit_colors[care_unit_name], zorder=2)
                    plt.vlines(
                        x=end,
                        ymin=request_y_position + space_between_rows + space_between_rows,
                        ymax=request_y_position + space_between_rows + (slot_height - space_between_rows * 2),
                        lw=1.5, colors=care_unit_colors[care_unit_name], zorder=2)

                request_y_position += slot_height

    # draw black marks where services are scheduled
    for day_name, day_requests in results['scheduled'].items():
        for request in day_requests:
            patient_name = request['patient']
            service_name = request['service']
            care_unit_name = instance['services'][service_name]['care_unit']
            day_len = len(instance['days'][day_name])
            pos = day_x_positions[day_name]
            plt.plot(pos, request_y_positions[(patient_name, service_name)] + space_between_rows * 0.5, 'x', color='k')

    # draw thin vertical lines between each day
    for day_name, day in instance['days'].items():
        plt.vlines(x=(day_x_positions[day_name] - len(day) * slot_width * 0.5), ymin = 0, ymax=request_y_position, colors='grey', lw=0.5, ls=':', zorder=0)
    # last day right vertical line
    plt.vlines(x=(last_care_unit_x_position + space_between_days * 0.5), ymin = 0, ymax=request_y_position, colors='grey', lw=0.5, ls=':', zorder=0)

    # add axis ticks
    ax2.set_xticks(list(day_x_positions.values())[:-1], labels=list(care_unit_x_positions.keys()))
    plt.yticks([])
    
    ax2.set_title('Patient request windows')
    ax2.set_xlabel('Days', weight='bold', labelpad=6)
    ax2.set_ylabel('Requests', weight='bold', labelpad=8)

    fig.suptitle(f'Plot of {plot_file_path.stem.removesuffix("_plot")}', weight='bold')

    plt.savefig(plot_file_path)
    plt.close('all')


def plot_subproblem_results(instance, results, plot_file_path):
    
    fig, ax = plt.subplots()
    fig.set_size_inches(16, 8)

    slot_height = 2.0
    space_between_lines = 0.2 * slot_height
    colors = 'rgbcmy'

    # tracks the operator number
    operator_index = 0

    max_operator_time = 0

    # list of couples (operator, care_unit)
    operators = []
    
    first_operator_index_of_care_unit = {}
    first_operator_name_of_care_unit = {}

    # list of care unit names
    care_unit_names = []

    for care_unit_name, care_unit in instance['day'].items():
        care_unit_names.append(care_unit_name)
        
        first_operator_index_of_care_unit[care_unit_name] = len(operators)
        first_operator_name_of_care_unit[care_unit_name] = None
        
        for operator_name, operator in care_unit.items():
            
            if first_operator_name_of_care_unit[care_unit_name] is None:
                first_operator_name_of_care_unit[care_unit_name] = operator_name
            
            operators.append((operator_name, care_unit_name))
            end_slot = operator['start'] + operator['duration']

            if end_slot > max_operator_time:
                max_operator_time = end_slot

            # each operator has two bold vertical lines and one horizontal
            # indicating its own start and end slots
            start_height = operator_index * slot_height + space_between_lines * 0.5
            end_height = (operator_index + 1) * slot_height - space_between_lines * 0.5
            plt.vlines(x=operator['start'], ymin=start_height, ymax=end_height, colors='black', lw=2, zorder=2)
            plt.vlines(x=end_slot, ymin=start_height, ymax=end_height, colors='black', lw=2, zorder=2)
            plt.hlines(xmin=operator['start'], xmax=end_slot, y=(operator_index + 0.5) * slot_height, colors='black', lw=2, zorder=0)
            
            operator_index += 1

    max_end_slot_per_care_unit_first_operator = {}

    # draw boxes
    for schedule in results['scheduled']:

        care_unit_name = schedule['care_unit']
        duration = instance['services'][schedule['service']]['duration']
        operator_index = operators.index((schedule['operator'], care_unit_name))

        if schedule['operator'] == first_operator_name_of_care_unit[care_unit_name]:
        
            end_slot = schedule['time'] + duration
            
            if care_unit_name not in max_end_slot_per_care_unit_first_operator or end_slot > max_end_slot_per_care_unit_first_operator[care_unit_name]:
                max_end_slot_per_care_unit_first_operator[care_unit_name] = end_slot

        ax.add_patch(Rectangle(
            (schedule['time'], operator_index * slot_height + space_between_lines),
            duration,
            slot_height - 2 * space_between_lines,
            linewidth=1, edgecolor='k', lw=2,
            facecolor=colors[care_unit_names.index(care_unit_name) % len(colors)], zorder=1))
        
        # add a text label to every box with patient/service rejected
        plt.text(
            (schedule['time'] + duration * 0.5),
            (operator_index + 0.125) * slot_height + space_between_lines,
            f'{schedule["patient"]}\n{schedule["service"]}',
            ha='center', weight='bold')

    for rejected_schedule in results['rejected']:

        service_name = rejected_schedule['service']
        care_unit_name = instance['services'][service_name]['care_unit']
        duration = instance['services'][service_name]['duration']
        operator_index = first_operator_index_of_care_unit[care_unit_name]
        
        ax.add_patch(Rectangle(
            (max_end_slot_per_care_unit_first_operator[care_unit_name], operator_index * slot_height + space_between_lines),
            duration,
            slot_height - 2 * space_between_lines,
            linewidth=1, edgecolor='k', lw=2,
            facecolor=colors[care_unit_names.index(care_unit_name) % len(colors)], zorder=1, alpha=0.5))
        
        plt.text(
            (max_end_slot_per_care_unit_first_operator[care_unit_name] + duration * 0.5),
            (operator_index + 0.125) * slot_height + space_between_lines,
            f'{rejected_schedule["patient"]}\n{rejected_schedule["service"]}',
            ha='center', weight='bold')

        max_end_slot_per_care_unit_first_operator[care_unit_name] += duration

        if max_operator_time < max_end_slot_per_care_unit_first_operator[care_unit_name]:
            max_operator_time = max_end_slot_per_care_unit_first_operator[care_unit_name]

    # draw thin vertical lines between each time slot
    for time_slot_index in range(max_operator_time + 1):
        plt.vlines(x=time_slot_index, ymin=0, ymax=len(operators) * slot_height, colors='grey', lw=0.5, ls=':', zorder=0)

    # add ticks to both axis (time slots in the x, operators in the y)
    ax.set_xticks([i for i in range(0, max_operator_time + 1)])
    ax.set_xticklabels(range(max_operator_time + 1))
    ax.set_yticks([(i + 0.5) * slot_height for i in range(len(operators))])
    ax.set_yticklabels(operators, weight='bold')

    plt.title(f'Plot of {plot_file_path.stem.removesuffix("_plot")}', weight='bold')
    plt.xlabel('Time slots', weight='bold', labelpad=6)
    plt.ylabel('Operators', weight='bold', labelpad=8)

    plt.savefig(plot_file_path)
    plt.close('all')


def get_subproblem_instance_from_final_results(instance, results, day_name):
    
    patients = {}
    for day_result in results['scheduled'][day_name]:
        
        patient_name = day_result['patient']
        service_name = day_result['service']
        
        if patient_name not in patients:
            patients[patient_name] = {
                'priority': instance['patients'][patient_name]['priority'],
                'requests': []
            }
        patients[patient_name]['requests'].append(service_name)

    return {
        'services': instance['services'],
        'day': instance['days'][day_name],
        'patients': patients
    }


def common_main_plotter(command_name, create_plot_function, create_subproblem_plot_function=None):

    parser = argparse.ArgumentParser(prog=command_name, description='Plot instances')
    parser.add_argument('-i', '--input', type=Path, help='Group instances directory path', required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='Show what is done')
    args = parser.parse_args()

    group_directory_path = Path(args.input).resolve()
    is_verbose = bool(args.verbose)

    if not group_directory_path.exists():
        raise ValueError(f'Group directory \'{group_directory_path}\' does not exists')
    elif not group_directory_path.is_dir():
        raise ValueError(f'Group \'{group_directory_path}\' is not a directory')
    
    input_directory_path = group_directory_path.joinpath('input')
    if not input_directory_path.exists():
        raise ValueError(f'Input directory \'{input_directory_path}\' does not exists')
    elif not input_directory_path.is_dir():
        raise ValueError(f'Input \'{input_directory_path}\' is not a directory')

    results_directory_path = group_directory_path.joinpath('results')
    if not results_directory_path.exists():
        raise ValueError(f'Input directory \'{results_directory_path}\' does not exists')
    elif not results_directory_path.is_dir():
        raise ValueError(f'Input \'{results_directory_path}\' is not a directory')

    plots_directory_path = group_directory_path.joinpath('plots')
    if plots_directory_path.exists():
        shutil.rmtree(plots_directory_path)
    plots_directory_path.mkdir()
    
    if is_verbose:
        print(f'Plotting data in directory \'{group_directory_path}\'')
        start_time = time.perf_counter()
        instance_number = 0

    for instance_file_path in input_directory_path.iterdir():

        if not instance_file_path.is_file() or instance_file_path.suffix != '.json':
            continue

        with open(instance_file_path, 'r') as file:
            instance = json.load(file)
        
        instance_file_name = instance_file_path.name.removesuffix('.json')
        results_file_path = results_directory_path.joinpath(f'{instance_file_name}_results.json')
        plot_file_path = plots_directory_path.joinpath(f'{instance_file_name}_plot.png')

        with open(instance_file_path, 'r') as file:
            instance = json.load(file)
        
        with open(results_file_path, 'r') as file:
            results = json.load(file)

        if is_verbose:
            print(f'Plotting instance \'{instance_file_name}\'... ', end='')
            instance_number += 1

        create_plot_function(instance, results, plot_file_path)
        
        if create_subproblem_plot_function is not None:

            for day_name, day_results in results['scheduled'].items():
            
                subproblem_instance = get_subproblem_instance_from_final_results(instance, results, day_name)
                subproblem_plot_file_path = plots_directory_path.joinpath(f'{instance_file_name}_{day_name}_plot.png')
                create_subproblem_plot_function(subproblem_instance, day_results, subproblem_plot_file_path)

        if is_verbose:
            print(f'Done.')
        
    if is_verbose:
        end_time = time.perf_counter()
        print(f'End Plotting process. Time elapsed: {end_time - start_time} seconds')
        print(f'Plotted {instance_number} instances')