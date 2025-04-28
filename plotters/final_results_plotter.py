from plotters.tools import plot_master_results, plot_subproblem_results, common_main_plotter


def plot_final_results(master_instance, final_results, plot_file_path):
    plot_master_results(master_instance, final_results, plot_file_path)


if __name__ == '__main__':

    common_main_plotter(
        command_name='Final plotter',
        create_plot_function=plot_final_results,
        create_subproblem_plot_function=plot_subproblem_results)