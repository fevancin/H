from checkers.tools import check_results_general_shape
from checkers.tools import check_schedules_with_window, check_schedule_with_time
from checkers.tools import check_integrity_schedule_with_window, check_integrity_schedule_with_time, check_integrity_protocols_represented


def check_schedules_with_time(schedules):
    
    if type(schedules) is not dict:
        raise TypeError(f'\'scheduled\' is not a dict')

    for day_name, schedule in schedules.items():

        if type(day_name) is not str:
            raise KeyError(f'\'{day_name}\' in \'scheduled\' is not a string')

        check_schedule_with_time(schedule, day_name)


def check_integrity_schedules_with_time(schedules, instance):
    
    for day_name, schedule in schedules.items():

        if day_name not in instance['days']:
            raise KeyError(f'\'{day_name}\' is not a valid scheduled (with time) day name')
        
        check_integrity_schedule_with_time(schedule, instance, day_name)


def check_final_results(subproblem_instance, subproblem_results):
    check_results_general_shape(subproblem_results)

    check_schedules_with_time(subproblem_results['scheduled'])
    check_schedules_with_window(subproblem_results['rejected'])
    
    check_integrity_schedules_with_time(subproblem_results['scheduled'], subproblem_instance)
    check_integrity_schedule_with_window(subproblem_results['rejected'], subproblem_instance)
    check_integrity_protocols_represented(subproblem_results, subproblem_instance)