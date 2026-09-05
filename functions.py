##
# @file functions.py
# @brief Computation and plotting functions for the negative ion current analysis.
#
# This module contains the pure-computation helpers, the plotting helpers, and
# the functions (compute_dataset, analysis, comparison,
# process_folders) that main.py calls to run the full analysis workflow. It
# also defines PlotStyle, the styling parameters shared by every plot.

# Libraries
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

# Third part libraries
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray
from scipy.signal import savgol_filter

# Project modules
from configreader import ConfigReader
from dataloader import DataLoader
from standardmethod import StandardMethod
from style import PlotStyle


##
# @brief Iterates over dataset results, plots series, formats axes, and saves the figure safely.
#
# Generates a standard figure, executes the plot callback for each valid dataset,
# applies unified styling parameters, and safely exports the PDF file.
#
# @param inputlist List of dataset result dictionaries.
# @param plot_func Callback routine with signature `func(ax, data_dict)` defining how to plot data.
# @param xlabel Horizontal axis label.
# @param ylabel Vertical axis label.
# @param title Figure title.
# @param filename Output destination path for the saved plot figure.
# @param style Styling parameters (figure size, grid).
# @return None
def _plot_dataset_series(
    inputlist: list,
    plot_func: Callable[[plt.Axes, dict], None],
    xlabel: str,
    ylabel: str,
    title: str,
    filename: str,
    style: PlotStyle,
) -> None:
    fig, ax = plt.subplots(figsize=style.figsize)

    for data in inputlist:
        if data.get('voltage') is not None and len(data['voltage']) > 0:
            plot_func(ax, data)
        else:
            print(f'\nWARNING: {data.get("label", "Dataset")} skipped - Data empty or missing values.')

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=style.grid_transparency, ls=style.grid_linestyle)
    ax.legend()

    try:
        fig.savefig(filename, dpi=300)
        print(f'{title} correctly compared!')
    except Exception as e:
        print(f'\nERROR: failed to save plot "{filename}": {e}')
    plt.close(fig)


##
# @brief Plots the two per-dataset figures (NI current step, distribution function).
#
# Pure plotting: utilizes the dictionary produced by compute_dataset() and
# only draws/saves figures. Does not compute anything.
#
# @param data Dictionary produced by compute_dataset(), or None.
# @param style Styling parameters (figure size, grid).
# @return None
def _plot_dataset(data: dict | None, style: PlotStyle) -> None:
    if data is None:
        return

    results_path = data['results_path']

    #plt.rcParams.update({'font.size': 12})

    fig, ax = plt.subplots()
    ax.set_xlabel('Voltage [V]')
    ax.set_ylabel('Current [nA]')
    ax.set_title('Negative Ion Current')
    ax.grid(True, alpha=style.grid_transparency, ls=style.grid_linestyle)
    ax.set_xlim(data['voltage'].min(), -5)
    ax.errorbar(data['voltage'], data['nicurr'], data['dnicurr'], marker=style.marker, ls='')
    fig.savefig(results_path / 'ni_step.pdf', dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.set_xlabel(r'E [eV]')
    ax.set_ylabel('dni/dV')
    ax.set_title('Negative Ion Dist Func')
    ax.grid(True, alpha=style.grid_transparency, ls=style.grid_linestyle)
    ax.plot(-data['voltage_nc'], data['dni/dv'], ls=style.linestyle_1, lw=style.linewidth)
    fig.savefig(results_path / 'dist_func.pdf')
    plt.close(fig)


##
# @brief Plots collector currents (neg/pos) against the experimental control parameter (power/pressure).
#
# @param metrics Dict of per-dataset collector current arrays, as returned by
#        _extract_collector_metrics().
# @param x_vals Values of the control parameter (pressure or power) for each dataset.
# @param x_label Horizontal axis label (with units).
# @param param_name Name of the control parameter, used in the plot title.
# @param style Styling parameters (figure size, grid).
# @param filename Output destination path for the saved plot figure.
# @return None
def _plot_collector_vs_parameter(
    metrics: dict,
    x_vals: NDArray,
    x_label: str,
    param_name: str,
    style: PlotStyle,
    filename: str,
) -> None:
    fig, ax = plt.subplots(figsize=style.figsize)
    ax.set_ylabel('Current [nA]')
    ax.set_xlabel(x_label)
    ax.set_xticks(x_vals)
    ax.set_title(f'NI Current vs {param_name}')
    ax.grid(True, alpha=style.grid_transparency, ls=style.grid_linestyle)

    ax.errorbar(x_vals, metrics['ni_minus40V'], yerr=metrics['dni_minus40V'], label='neg coll', marker=style.marker, ls='')
    ax.errorbar(x_vals, metrics['ni_plus20V'], yerr=metrics['dni_plus20V'], label='pos coll', marker=style.marker_2, ls='')
    ax.legend()

    fig.savefig(filename, dpi=300)
    plt.close(fig)


##
# @brief Plots NI current against positive ion flux.
#
# @param pi_fluxes Positive ion flux values, one per dataset.
# @param ni_plot_data Negative ion current values (at -40V), one per dataset,
#        already corrected for pressure attenuation when applicable.
# @param dni_minus40V Uncertainty on ni_plot_data, used as the error bar.
# @param style Styling parameters (figure size, grid).
# @param filename Output destination path for the saved plot figure.
# @return None
def _plot_ni_vs_pi_flux(
    pi_fluxes: NDArray,
    ni_plot_data: NDArray,
    dni_minus40V: NDArray,
    style: PlotStyle,
    filename: str,
) -> None:
    fig, ax = plt.subplots(figsize=style.figsize)
    ax.set_xlabel(r'$\Phi_{PI} [m^{-2} s^{-1}]$')
    ax.set_ylabel('Current [nA]')
    ax.set_title('NI Current vs PI flux')
    ax.grid(True, alpha=style.grid_transparency, ls=style.grid_linestyle)
    ax.errorbar(pi_fluxes, ni_plot_data, yerr=dni_minus40V, marker=style.marker, ls='')

    fig.savefig(filename, dpi=300)
    plt.close(fig)


##
# @brief Picks negative-collector NI current/uncertainty according to the configured method.
#
# @param sm StandardMethod instance already run (negative_collector() executed).
# @param method Either 'scaling' or 'shifting', as configured under METHOD.
# @param current_scale Multiplicative factor applied to convert currents (e.g. A to nA).
# @return Tuple (negative-collector NI current array, its uncertainty array).
# @exception ValueError Raised if `method` is neither 'scaling' nor 'shifting'.
def _select_method_currents(sm: StandardMethod, method: str, current_scale: float) -> tuple:
    if method == 'scaling':
        print("-> Applying SCALING method for analysis")
        return sm.ni_avg_nc_scaling * current_scale, sm.ni_std_nc_scaling * current_scale
    if method == 'shifting':
        print("-> Applying SHIFTING for analysis")
        return sm.ni_avg_nc_shifting * current_scale, sm.ni_std_nc_shifting * current_scale
    raise ValueError(f"Unknown METHOD '{method}' in config.txt (expected 'scaling' or 'shifting').")


##
# @brief Merges negative- and positive-collector regions into a single NI current curve.
# Transition region (near plasma potential) avoided.
#
# @param voltage Full voltage array.
# @param nicurr_nc Negative-collector NI current array.
# @param dnicurr_nc Negative-collector NI current uncertainty array.
# @param nicurr_pc Positive-collector NI current array.
# @param dnicurr_pc Positive-collector NI current uncertainty array.
# @param threshold_negative Voltage at/below which the negative-collector region is used.
# @param threshold_positive Voltage at/above which the positive-collector region is used.
# @return Tuple (merged NI current array, merged uncertainty array, combined
#         boolean mask over `voltage`, negative-collector-only boolean mask).
def _merge_collector_regions(
    voltage: NDArray,
    nicurr_nc: NDArray, dnicurr_nc: NDArray,
    nicurr_pc: NDArray, dnicurr_pc: NDArray,
    threshold_negative: float, threshold_positive: float,
) -> tuple:
    mask_nc = voltage <= threshold_negative
    mask_pc = voltage >= threshold_positive
    mask = mask_nc | mask_pc

    nicurr = np.concatenate((nicurr_nc[mask_nc], nicurr_pc[mask_pc]))
    dnicurr = np.concatenate((dnicurr_nc[mask_nc], dnicurr_pc[mask_pc]))

    return nicurr, dnicurr, mask, mask_nc


##
# @brief Extracts current/uncertainty at the voltage closest to a target value.
#
# @param voltage Voltage array to search in.
# @param nicurr NI current array, same length as `voltage`.
# @param dnicurr NI current uncertainty array, same length as `voltage`.
# @param target_voltage Voltage value to locate the closest match for.
# @return Tuple (current, uncertainty) at the closest matching voltage index.
def _extract_current_at_voltage(
    voltage: NDArray, nicurr: NDArray, dnicurr: NDArray, target_voltage: float
) -> tuple:
    idx = np.argmin(np.abs(voltage - target_voltage))
    return nicurr[idx], dnicurr[idx]


##
# @brief Computes the (smoothed) negative ion energy distribution function dni/dV.
#
# @param nicurr_nc_masked Negative-collector NI current array (already restricted
#        to the negative-collector voltage mask).
# @return Smoothed dni/dV array.
def _compute_distribution_function(nicurr_nc_masked: NDArray) -> NDArray:
    dni_dv = savgol_filter(nicurr_nc_masked, window_length=11, polyorder=2, deriv=1, delta=1)
    return savgol_filter(dni_dv, window_length=11, polyorder=2, delta=1)


##
# @brief Prints a summary of the positive- and negative-collector NI currents.
#
# @param nicurr_plus20V NI current at +20V (positive collector).
# @param dnicurr_plus20V Uncertainty on nicurr_plus20V.
# @param nicurr_minus40V NI current at -40V (negative collector).
# @param dnicurr_minus40V Uncertainty on nicurr_minus40V.
# @return None
def _print_collector_summary(nicurr_plus20V, dnicurr_plus20V, nicurr_minus40V, dnicurr_minus40V) -> None:
    print('\nPrinting NI currents:')
    print('Positive Collector:')
    print(f'- {nicurr_plus20V: .2f} +- {dnicurr_plus20V: .2f}')
    print('Negative Collector:')
    print(f'- {nicurr_minus40V: .2f} +- {dnicurr_minus40V: .2f}')


##
# @brief Determines the experimental control parameter (pressure or power) to compare against.
#
# @return (x_vals, x_label, param_name, is_pressure) or (None, None, None, None) if
#         neither PRESSURES nor POWERS is configured.
def _determine_control_parameter(config: ConfigReader) -> tuple:
    pressures = np.array(config.get('PRESSURES', []))
    powers = np.array(config.get('POWERS', []))

    if len(pressures) > 0:
        return pressures, 'Pressure [Pa]', 'pressure', True
    if len(powers) > 0:
        return powers, 'Power [W]', 'power', False
    return None, None, None, None


##
# @brief Extracts the collector current arrays across all analysed datasets.
#
# @param inputlist List of dataset result dictionaries produced by analysis().
# @return dict with keys 'ni_minus40V', 'dni_minus40V', 'ni_plus20V', 'dni_plus20V',
#         each a NumPy array with one entry per dataset in `inputlist`.
def _extract_collector_metrics(inputlist: list) -> dict:
    return {
        'ni_minus40V': np.array([d['ni_minus40V'] for d in inputlist]),
        'dni_minus40V': np.array([d['dni_minus40V'] for d in inputlist]),
        'ni_plus20V': np.array([d['ni_plus20V'] for d in inputlist]),
        'dni_plus20V': np.array([d['dni_plus20V'] for d in inputlist]),
    }


##
# @brief Computes the positive ion flux from electron density/temperature.
#
# @param ne_list Electron density values (one per experimental condition).
# @param te_list Electron temperature values (one per experimental condition).
# @param ion_mass Ion mass, as configured under ION_MASS.
# @param speed_light Speed of light, as configured under SPEED_LIGHT.
# @return Positive ion flux array, one value per experimental condition.
def _compute_pi_flux(ne_list: NDArray, te_list: NDArray, ion_mass: float, speed_light: float) -> NDArray:
    return 0.6 * ne_list * np.sqrt(te_list * speed_light ** 2 / ion_mass)


##
# @brief Computes the mean-free-path attenuation correction for pressure scans.
#
# @param pressures Pressure values, one per experimental condition.
# @param cross_section Collision cross section, as configured under CROSS_SECTION.
# @param distance MRFEA collector distance, as configured under DISTANCE.
# @param boltzmann Boltzmann constant, as configured under BOLTZMANN.
# @param gas_temperature Neutral gas temperature, as configured under GAS_TEMPERATURE.
# @return Attenuation correction factor array, one value per experimental condition.
def _compute_pressure_correction(
    pressures: NDArray, cross_section: float, distance: float, boltzmann: float, gas_temperature: float
) -> NDArray:
    gas_density = pressures / (boltzmann * gas_temperature)
    mean_free_path = 1 / (gas_density * cross_section)
    return np.exp(-distance / mean_free_path)


##
# @brief Loads one dataset and computes every derived quantity (no plotting).
#
# @param directory Directory containing the dataset to analyse.
#        If `None`, the standard folder structure in the working directory is used.
# @param config Configuration object (explicit dependency, not read from a global).
# @return dict Dictionary with the processed results ('label', 'voltage',
#         'nicurr', 'dnicurr', 'ni_minus40V', 'dni/dv', ...), including
#         'results_path' and 'voltage_nc' needed only for plotting.
def compute_dataset(directory: None | Path, config: ConfigReader, style: PlotStyle) -> dict:
    threshold_negative = config.get('THRESHOLD_VOLTAGE_NEGATIVE', -5)
    threshold_positive = config.get('THRESHOLD_VOLTAGE_POSITIVE', 10)
    minus_40v = config.get('MINUS_40V', -40)
    plus_20v = config.get('PLUS_20V', 20)
    current_scale = config.get('CURRENT_SCALE', 1e9)
    method = config.get('METHOD')

    loader = DataLoader(config, directory)
    unbiased_raw, biased_raw = loader.load_all_data()

    sm = StandardMethod(loader.voltage, unbiased_raw, biased_raw, loader.results_path, style, config)
    sm.create_plot()
    plt.show(block=True)
    sm.plot_ratio()
    sm.derivative_unbiased()
    sm.negative_collector()
    sm.plot_ni_comparison()
    sm.positive_collector()
    sm.variabilities()

    voltage = sm.voltage
    nicurr_nc, dnicurr_nc = _select_method_currents(sm, method, current_scale)
    nicurr_pc = sm.ni_avg_pc * current_scale
    dnicurr_pc = sm.ni_std_pc * current_scale

    nicurr, dnicurr, mask, mask_nc = _merge_collector_regions(
        voltage, nicurr_nc, dnicurr_nc, nicurr_pc, dnicurr_pc,
        threshold_negative, threshold_positive,
    )

    nicurr_minus40V, dnicurr_minus40V = _extract_current_at_voltage(voltage, nicurr, dnicurr, minus_40v)
    nicurr_plus20V, dnicurr_plus20V = _extract_current_at_voltage(voltage, nicurr, dnicurr, plus_20v)
    dni_dv_smooth = _compute_distribution_function(nicurr_nc[mask_nc])

    _print_collector_summary(nicurr_plus20V, dnicurr_plus20V, nicurr_minus40V, dnicurr_minus40V)

    return {
        'label': directory.name if directory else None,
        'results_path': loader.results_path,
        'voltage': voltage[mask],
        'voltage_nc': voltage[mask_nc],
        'nicurr': nicurr,
        'dnicurr': dnicurr,
        'ni_minus40V': nicurr_minus40V,
        'dni_minus40V': dnicurr_minus40V,
        'ni_plus20V': nicurr_plus20V,
        'dni_plus20V': dnicurr_plus20V,
        'dni/dv': dni_dv_smooth,
    }


##
# @brief Computes and plots a single dataset.
#
# Thin orchestrator: delegates to compute_dataset() for the numbers and
# to _plot_dataset() for the figures, so each concern can be tested and
# reasoned about on its own (SRP / Separation of Concerns).
#
# @param directory Directory containing the dataset to analyse (or `None`).
# @param config Configuration object (explicit dependency).
# @param style Styling parameters shared by every plot.
# @return dict Dictionary with the processed results, as returned by compute_dataset().
def analysis(directory: None | Path, config: ConfigReader, style: PlotStyle) -> dict:
    data = compute_dataset(directory, config, style)
    _plot_dataset(data, style)
    return data


##
# @brief Compares results from multiple analysed datasets.
#
# Generates comparison plots across multiple datasets, including:
# - Negative ion current curves vs voltage
# - Energy distribution functions (dni/dV)
# - Collector currents vs experimental control parameter (Pressure or Power)
# - Negative ion current vs positive ion flux (corrected for pressure if applicable)
#
# Does nothing if fewer than two datasets are provided, since a comparison
# needs at least two points.
#
# @param inputlist List of dataset result dictionaries produced by analysis().
# @param config Configuration object (explicit dependency).
# @param style Styling parameters shared by every plot.
# @return None
def comparison(inputlist: list, config: ConfigReader, style: PlotStyle) -> None:
    if len(inputlist) <= 1:
        return

    _plot_dataset_series(
        inputlist=inputlist,
        plot_func=lambda ax, d: ax.scatter(d['voltage'], d['nicurr'], marker=style.marker, label=f"{d['label']}"),
        xlabel='Voltage [V]', ylabel='Current [nA]', title='NI currents comparison',
        filename='comparison_ni_curr.pdf', style=style,
    )

    def _plot_niedf(ax: plt.Axes, d: dict) -> None:
        mask = d['voltage'] < 0
        ax.plot(-d['voltage'][mask], d['dni/dv'], label=f"{d['label']}", lw=style.linewidth, ls=style.linestyle_1)

    _plot_dataset_series(
        inputlist=inputlist, plot_func=_plot_niedf,
        xlabel=r'E [eV]', ylabel='dni/dV', title='NIEDF',
        filename='comparison_energy_distribution.pdf', style=style,
    )

    x_vals, x_label, param_name, is_pressure = _determine_control_parameter(config)
    if x_vals is None:
        print('\nWARNING: No pressures or powers in the config file.')
        print('No comparison NI vs pressure/power will be done.')
        plt.show()
        return

    metrics = _extract_collector_metrics(inputlist)
    _plot_collector_vs_parameter(
        metrics, x_vals, x_label, param_name, style, 'comparison_minus_40V_plus_20V.pdf'
    )
    print(f'\nComparison negative vs positive collector done ({param_name}).')

    te_list = np.array(config.get('ELECTRON_TEMPERATURES', []))
    ne_list = np.array(config.get('ELECTRON_DENSITIES', []))

    if len(te_list) > 0 and len(ne_list) > 0:
        ion_mass = config.get('ION_MASS')
        speed_light = config.get('SPEED_LIGHT', 3e8)
        pi_fluxes = _compute_pi_flux(ne_list, te_list, ion_mass, speed_light)

        ni_plot_data = metrics['ni_minus40V']
        if is_pressure:
            correction = _compute_pressure_correction(
                x_vals,
                config.get('CROSS_SECTION'),
                config.get('DISTANCE'),
                config.get('BOLTZMANN'),
                config.get('GAS_TEMPERATURE'),
            )
            ni_plot_data = metrics['ni_minus40V'] / correction

        _plot_ni_vs_pi_flux(
            pi_fluxes, ni_plot_data, metrics['dni_minus40V'], style,
            f'comparison_NI_curr_vs_pi_flux_{param_name}.pdf',
        )

        print(f'Positive Ion Flux / m-2: {pi_fluxes}')
        if is_pressure:
            print(f'Corrected Neg Ion Curr: {ni_plot_data}')

    plt.show()


##
# @brief Process one or multiple dataset folders.
#
# @param folders Path to the dataset directory or a list of directories.
#        If `None`, a single dataset analysis is executed and nothing is
#        collected for comparison.
# @param config Configuration object (explicit dependency).
# @param style Styling parameters shared by every plot.
# @return list List of dictionaries returned by analysis() (empty in
#         single-dataset mode).
def process_folders(folders: None | list[Path], config: ConfigReader, style: PlotStyle) -> list[dict]:
    if folders is None:
        analysis(None, config, style)
        print('\nAnalysis concluded.')
        return []

    total = len(folders)
    results = []
    for i, folder in enumerate(folders, start=1):
        print(f'\n--- Analysing {folder.name} ({i}/{total}) ---')
        results.append(analysis(folder, config, style))

    return results
