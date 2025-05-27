from pathlib import Path
import argparse
import json
import time
import csv


def get_subproblem_results_value(master_instance, master_results, day_name):

    is_priority = True
    for patient in master_instance['patients'].values():
        if 'priority' not in patient:
            is_priority = False
            break

    value = 0
    for schedule_item in master_results['scheduled'][day_name]:
        
        service_name = schedule_item['service']
        service_duration = master_instance['services'][service_name]['duration']
        
        if is_priority:
            
            patient_name = schedule_item['patient']
            patient_priority = master_instance['patients'][patient_name]['priority']
            
            value += service_duration * patient_priority
        
        else:
            value += service_duration
    
    return value


def get_master_results_value(master_instance, master_results):

    value = 0
    for day_name in master_results['scheduled']:
        value += get_subproblem_results_value(master_instance, master_results, day_name)
    
    return value


def get_satisfied_window_number(master_results):

    satisfied_window_number = 0
    for day in master_results['scheduled'].values():
        satisfied_window_number += len(day)
    
    return satisfied_window_number


def analyze_master_results(master_instance, master_results, instance_path):
    
    data = {}
    data['group'] = instance_path.parent.name
    data['instance'] = instance_path.stem
    data = master_results['info']
    data['satisfied_window_number'] = get_satisfied_window_number(master_results)
    data['rejected_window_number'] = len(master_results['rejected'])
    data['solution_value'] = get_master_results_value(master_instance, master_results)

    return data