from plotters.tools import plot_master_results, common_main_plotter


if __name__ == '__main__':

    common_main_plotter(
        command_name='Master plotter',
        create_plot_function=plot_master_results)