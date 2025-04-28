from checkers.tools import check_results_general_shape
from checkers.tools import check_schedule_without_window, check_schedules_with_window
from checkers.tools import check_integrity_schedule_basic, check_integrity_total_request_durations_per_care_unit, check_integrity_schedule_with_window, check_integrity_protocols_represented
from checkers.tools import common_main_checker


def check_scheduled_without_window(schedules):
    
    if type(schedules) is not dict:
        raise TypeError(f'schedules is not a dict')

    for day_name, schedule in schedules.items():

        if type(day_name) is not str:
            raise KeyError(f'\'{day_name}\' in \'scheduled\' is not a string')

        check_schedule_without_window(schedule, day_name)


def check_integrity_schedules_without_window(schedules, instance):

    for day_name, schedule in schedules.items():

        if day_name not in instance['days']:
            raise KeyError(f'\'{day_name}\' is not a valid schedule (without window) day name')
        
        check_integrity_schedule_basic(schedule, instance, day_name)
        check_integrity_total_request_durations_per_care_unit(schedule, instance, day_name)


def check_master_results(master_instance, master_results):
    
    check_results_general_shape(master_results)

    check_scheduled_without_window(master_results['scheduled'])
    check_schedules_with_window(master_results['rejected'])

    check_integrity_schedules_without_window(master_results['scheduled'], master_instance)
    check_integrity_schedule_with_window(master_results['rejected'], master_instance)
    check_integrity_protocols_represented(master_results, master_instance)
    

if __name__ == '__main__':

    common_main_checker(
        command_name='Master results checker',
        function_to_call=check_master_results,
        needs_results=True)