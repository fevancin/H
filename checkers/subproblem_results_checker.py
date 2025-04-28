from checkers.tools import check_results_general_shape
from checkers.tools import check_schedule_without_window, check_schedule_with_time
from checkers.tools import check_integrity_schedule_with_time, check_integrity_schedule_basic
from checkers.tools import common_main_checker


def check_subproblem_results(subproblem_instance, results):
    
    check_results_general_shape(results)

    check_schedule_with_time(results['scheduled'])
    check_schedule_without_window(results['rejected'], None)

    check_integrity_schedule_with_time(results['scheduled'], subproblem_instance, None)
    check_integrity_schedule_basic(results['rejected'], subproblem_instance, None)


def remove_schedule(schedule, patients_requests):

    for schedule_item in schedule:

        patient_name = schedule_item['patient']
        service_name = schedule_item['service']

        if patient_name not in patients_requests:
            raise ValueError(f'patient \'{patient_name}\' do not request service \'{service_name}\'')
        
        if service_name not in patients_requests[patient_name]:
            raise ValueError(f'patient \'{patient_name}\' do not request service \'{service_name}\'')
        patients_requests[patient_name].remove(service_name)
        if len(patients_requests[patient_name]) == 0:
            del patients_requests[patient_name]


def check_integrity_requests_represented(results, instance):

    patients_requests = {}
    for patient_name, patient in instance['patients'].items():
        patients_requests[patient_name] = []
        for service_name in patient['requests']:
            patients_requests[patient_name].append(service_name)
    
    remove_schedule(results['scheduled'], patients_requests)
    remove_schedule(results['rejected'], patients_requests)
    
    if len(patients_requests) > 0:
        raise ValueError(f'some request are not in the results: {patients_requests}')


if __name__ == '__main__':

    common_main_checker(
        command_name='Subproblem results checker',
        function_to_call=check_subproblem_results,
        needs_results=True)