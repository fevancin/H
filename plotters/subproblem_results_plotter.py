from plotters.tools import plot_subproblem_results, common_main_plotter


if __name__ == '__main__':

    common_main_plotter(
        command_name='Subproblem plotter',
        create_plot_function=plot_subproblem_results)