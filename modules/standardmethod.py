from __future__ import annotations

##
# @file standardmethod.py
# @brief Implements the StandardMethod class for loading, plotting, scaling,
#        and analyzing current-voltage characteristics.
#
# This module provides utilities to compare unbiased and biased current
# acquisitions. It reconstructs the baseline with no negative ions by using two procedures:
# - shift method
# - scale method
# The module estimates negative ion currents,
# and generates the a plot to accept only the correct measurements; plots the negative ion current
# and the avg ratio over the scanned voltage range.
#

# Standard libraries
from pathlib import Path
from typing import Tuple, List, Any

# Third part libraries
import matplotlib.pyplot as plt
from matplotlib.widgets import CheckButtons
import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit

# Poject modules
from modules.configreader import ConfigReader
from modules.style import PlotStyle

##
# @class StandardMethod
# @brief Encapsulates the standard analysis workflow for current-voltage data.
#
# The class stores raw unbiased and biased current acquisitions, allows the user
# to interactively disable bad measurements, computes averaged currents, shifting step,
# scaling ratios, and derives negative ion current estimates for different
# collector configurations.
class StandardMethod:
    ##
    # @brief Construct a StandardMethod analysis object.
    #
    # @param voltage Voltage array associated with all current measurements.
    # @param unbiased_currents_raw List of raw unbiased current arrays.
    # @param biased_currents_raw List of raw biased current arrays.
    # @param results_path Directory where output plots and results are saved.
    # @param config Configuration reader used to retrieve analysis parameters.
    def __init__(
        self,
        voltage: NDArray[np.float64],
        unbiased_currents_raw: List[NDArray[np.float64]],
        biased_currents_raw: List[NDArray[np.float64]],
        directory_path: Path,
        style: PlotStyle,
        config: 'ConfigReader'
    ) -> None:

        # Fundamental attributes
        self.config = config
        self.voltage = voltage
        self.unbiased_currents_raw = unbiased_currents_raw
        self.biased_currents_raw = biased_currents_raw

        # Define shifting range for analysis
        self.v_min = self.config.get('V_MIN', -90)
        self.v_max = self.config.get('V_MAX', -70)

        # Define scaling range for analysis
        self.scaling_v_min = self.config.get('SCALING_V_MIN', -100)
        self.scaling_v_max = self.config.get('SCALING_V_MAX', -80)

        # Define reference voltages
        self.minus_90V = self.config.get('MINUS_90V', -90)
        self.minus_40V = self.config.get('MINUS_40V', -40)
        self.plus_20V = self.config.get('PLUS_20V', 20)

        # Plotting settings
        self.current_scale: str = self.config.get('CURRENT_SCALE', 1e9)
        self.threshold_voltage_negative: int = self.config.get('THRESHOLD_VOLTAGE_NEGATIVE', -5)
        self.threshold_voltage_positive: int = self.config.get('THRESHOLD_VOLTAGE_POSITIVE', 10)
        self.style = style


        # Active mask
        self.unbiased_active: List[bool] = [True]*len(self.unbiased_currents_raw)
        self.biased_active: List[bool] = [True]*len(self.biased_currents_raw)

        # Plot handles
        self.unbiased_lines = []
        self.biased_lines = []

        # Avg currents
        self.ucurrent_avg: NDArray[np.float64] | None = None
        self.bcurrent_avg: NDArray[np.float64] | None = None

        # Outputs
        self.ni_avg_nc_scaling: NDArray[np.float64] | None = None
        self.ni_std_nc_scaling: NDArray[np.float64] | None = None
        self.all_ni_minus_40V_scaling: NDArray[np.float64] | None = None
        self.all_slopes_minus_40V_scaling: NDArray[np.float64] | None = None
        self.ni_avg_nc_shifting: NDArray[np.float64] | None = None
        self.ni_std_nc_shifting: NDArray[np.float64] | None = None
        self.all_ni_minus_40V_shifting: NDArray[np.float64] | None = None
        self.all_slopes_minus_40V_shifting: NDArray[np.float64] | None = None
        self.ni_avg_pc: NDArray[np.float64] | None = None
        self.ni_std_pc: NDArray[np.float64] | None = None
        self.all_ni_plus_20V: NDArray[np.float64] | None = None
        self.pi_avg: float = 0.0
        self.pi_std: float = 0.0

        # Save results
        self.results_path: Path = directory_path

    ##
    # @brief Return the list of active unbiased current acquisitions.
    #
    # Only currents whose corresponding activity flag is set to True are
    # returned. In this way currents selected by the users can be processed.
    #
    # @return List of enabled unbiased current arrays.
    @property
    def unbiased_currents(self):
        return [
            cur for cur, ok in zip(self.unbiased_currents_raw, self.unbiased_active)
            if ok
        ]

    ##
    # @brief Return the list of active biased current acquisitions.
    #
    # Only currents whose corresponding activity flag is set to True are
    # returned. In this way currents selected by the users can be processed.
    #
    # @return List of enabled biased current arrays.
    @property
    def biased_currents(self):
        return [
            cur for cur, ok in zip(self.biased_currents_raw, self.biased_active)
            if ok
        ]

    ##
    # @brief Create and save the current-voltage plots for unbiased and biased data.
    #
    # The method generates a two-panel figure, one for unbiased currents and one
    # for biased currents. Interactive checkboxes are added to allow hiding or
    # showing individual acquisitions. Only flagged acquisitions are processed.
    #
    # @return None
    def create_plot(self) -> None:
        """Plot any current"""

        # Create plot frame
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=self.style.figsize)

        self.unbiased_lines = []
        self.biased_lines = []

        # Plot unbiased currents
        for i, ucurrent in enumerate(self.unbiased_currents):
            line, = ax1.plot(
            self.voltage,
            ucurrent*self.current_scale,
            marker = self.style.marker,
            ls = '',
            alpha = self.style.grid_transparency,
            label = f'U_{i+1}'
            )

            self.unbiased_lines.append(line)

        for i, bcurrent in enumerate(self.biased_currents):
            line, = ax2.plot(
            self.voltage,
            bcurrent*self.current_scale,
            marker = self.style.marker,
            ls = '',
            alpha = self.style.grid_transparency,
            label = f'B_{i+1}'
            )

            self.biased_lines.append(line)

        # Add plot properties
        ax1.set_xlabel('Voltage [V]')
        ax1.set_ylabel('Current [nA]')
        ax1.set_title('Unbiased Currents')
        ax1.grid(True, alpha=self.style.grid_transparency, ls=self.style.grid_linestyle)

        # Add plot properties
        ax2.set_xlabel('Voltage [V]')
        ax2.set_ylabel('Current [nA]')
        ax2.set_title('Biased Currents')
        ax2.grid(True, alpha=self.style.grid_transparency, ls=self.style.grid_linestyle)

        # Add title
        pathsplitted = self.results_path.parts
        title = pathsplitted[-1]
        fig.suptitle(f'{title}', fontweight='bold')

        fig.tight_layout()
        self._add_checkboxes(fig)

        figurename = self.results_path / 'I-V-characteristic.pdf'
        plt.savefig(figurename, dpi=300)

    ##
    # @brief Add interactive checkboxes to enable or disable plotted acquisitions.
    #
    # Two checkbox groups are created: one for unbiased current traces and one
    # for biased current traces. Toggling a checkbox updates the visibility of
    # the corresponding line in the figure.
    #
    # @param fig Matplotlib figure to which the checkbox widgets are added.
    # @return None
    def _add_checkboxes(self, fig: Any) -> None:
        """Create interactive legend to deactivate
            bad acquisitions"""

        # Unbiased checkboxes
        # Coordinate ax: [left, bottom, width, height]
        # Fractions of figure sizes
        ax_u = fig.add_axes([0.15, 0.3, 0.12, 0.3], frameon=False)
        labels_u = [l.get_label() for l in self.unbiased_lines]

        self.check_u = CheckButtons(ax_u, labels_u, self.unbiased_active)

        for i, (lab, line) in enumerate(zip(self.check_u.labels, self.unbiased_lines)):
            lab.set_color(line.get_color())
            lab.set_fontweight('bold')
            lab.set_fontsize(9)

        def toggle_unbiased(label):
            idx = labels_u.index(label)
            self.unbiased_active[idx] = not self.unbiased_active[idx]
            self.unbiased_lines[idx].set_visible(self.unbiased_active[idx])
            fig.canvas.draw_idle()

        self.check_u.on_clicked(toggle_unbiased)

        # Biased checkboxes
        ax_b = fig.add_axes([0.65, 0.3, 0.12, 0.3], frameon=False)
        labels_b = [l.get_label() for l in self.biased_lines]

        self.check_b = CheckButtons(ax_b, labels_b, self.biased_active)

        for i, (lab, line) in enumerate(zip(self.check_b.labels, self.biased_lines)):
            lab.set_color(line.get_color())
            lab.set_fontweight('bold')
            lab.set_fontsize(9)

        def toggle_biased(label):
            idx = labels_b.index(label)
            self.biased_active[idx] = not self.biased_active[idx]
            self.biased_lines[idx].set_visible(self.biased_active[idx])
            fig.canvas.draw_idle()

        self.check_b.on_clicked(toggle_biased)

    ##
    # @brief Compute the average biased-to-unbiased current ratio.
    #
    # Average unbiased and biased currents are first computed, scaled according
    # to the configured current scale, and then divided element-wise to form the
    # ratio array. Plotting is not performed here: see plot_ratio(), which calls
    # this method and then draws the resulting ratio
    #(used as an estimate of the electron density ratio)
    #
    # @return Tuple (array of biased-to-unbiased current ratios over the full
    #         voltage range, average ratio over the voltage scaling range).
    def _calculate_ratio(self) -> Tuple[NDArray[np.float64], np.float64]:

        # Averaging currents [nA]
        self.ucurrent_avg = np.mean(self.unbiased_currents, axis = 0)*self.current_scale
        self.bcurrent_avg = np.mean(self.biased_currents, axis = 0)*self.current_scale

        # Calculate the ratio over the entire voltage range
        ratio: NDArray[np.float64] = self.bcurrent_avg/self.ucurrent_avg

        # Calculate the ratio over the voltage scaling range
        mask: bool = (self.voltage >= self.scaling_v_min) & (self.voltage <= self.scaling_v_max)

        # Calcola la media direttamente sui valori filtrati
        ratio_avg: np.float64 = np.mean(ratio[mask])

        return ratio, ratio_avg

    ##
    # @brief Computes and plots the biased-to-unbiased current ratio vs voltage.
    #
    # Calls _calculate_ratio() to obtain the ratio curve, then draws it against
    # voltage restricted to the region below -10 V (the ratio is not meaningful
    # near the plasma potential), and saves the figure to the results directory.
    #
    # @return None
    def plot_ratio(self) -> None:

        ratio, ratio_avg = self._calculate_ratio()

        # Plot the ratio vs voltage
        fig, ax = plt.subplots(figsize=self.style.figsize)

        ax.scatter(self.voltage, ratio, marker = '.')
        ax.set_xlabel('Voltage [V]')
        ax.set_ylabel('Ratio')
        ax.set_title(r'$I_b/I_u$')
        ax.set_xlim(self.voltage.min(), -10)
        ax.set_ylim(0.7, 1)
        ax.grid(ls = self.style.grid_linestyle, alpha = self.style.grid_transparency)

        figurename_ratio = self.results_path / 'ratio.pdf'
        plt.savefig(figurename_ratio, dpi=300)
        plt.close(fig)

    ##
    # @brief Computes the smoothed derivative of a current trace and locates its peak.
    #
    # Applies a Savitzky-Golay filter to obtain the first derivative of the
    # input current with respect to voltage, then finds the voltage at which
    # the derivative is maximal (used as an estimate of the plasma potential).
    #
    # @param current Current array to differentiate.
    # @return Tuple (derivative array, voltage at the derivative's maximum).
    def _derivative_current(self, current: NDArray[np.float64]) -> Tuple[NDArray[np.float64], float]:

        cderivated = savgol_filter(current, window_length=12, polyorder=2, delta=1, deriv=1)
        idx_max = np.argmax(cderivated)
        voltage_max = self.voltage[idx_max]

        return cderivated, voltage_max

    ##
    # @brief Plots the derivative of the unbiased current and marks the plasma potential.
    #
    # @param cderivated Derivative array to plot.
    # @param voltage_max Voltage at which the derivative is maximal (plasma potential estimate).
    # @return None
    def _plot_derivative(self, cderivated: NDArray[np.float64], voltage_max: float) -> None:

        fig, ax = plt.subplots(figsize=self.style.figsize)

        ax.plot(
        self.voltage,
        cderivated,
        lw = self.style.linewidth,
        color='black'
        )
        ax.scatter([], [], label=rf'Plasma potential: {voltage_max}\,V ')

        ax.set_xlabel('Voltage [V]')
        ax.set_ylabel('dI/dV')
        ax.set_title('Derivative: unbiased')
        ax.grid(ls = self.style.grid_linestyle, alpha = self.style.grid_transparency)

        figurename_derivative = self.results_path / 'derivative_unbiased.pdf'
        plt.savefig(figurename_derivative, dpi=300)
        plt.close(fig)

    ##
    # @brief Computes and plots the derivative of the averaged unbiased current.
    #
    # Orchestrates _derivative_current() (computation) and _plot_derivative()
    # (visualization) to estimate and display the plasma potential from the
    # averaged unbiased current curve.
    #
    # @return None
    def derivative_unbiased(self) -> None:

        uderivated, voltage_max = self._derivative_current(self.ucurrent_avg)

        self._plot_derivative(uderivated, voltage_max)


    ##
    # @brief Scales an unbiased current curve to match a biased one.
    #
    # The scaling factor is computed as the average ratio between the biased
    # and unbiased currents over the voltage window [V_min, V_max], then
    # applied to the whole unbiased curve.
    #
    # @param cur_unbiased Unbiased current array to be scaled.
    # @param cur_biased Biased current array used as the matching reference.
    # @param V_min Lower bound of the voltage window used to compute the scaling
    #        factor. Defaults to `self.scaling_v_min` when omitted.
    # @param V_max Upper bound of the voltage window used to compute the scaling
    #        factor. Defaults to `self.scaling_v_max` when omitted.
    # @return Scaled unbiased current array.
    def scale_curve(
        self,
        cur_unbiased: NDArray[np.float64],
        cur_biased: NDArray[np.float64],
        V_min: float = None,
        V_max: float = None
    )  -> NDArray[np.float64]:

        """
        Scale unbiased curve to match the biased one
        """
        # Assign defaults if no value is provided
        if V_min is None:
            V_min = self.scaling_v_min
        if V_max is None:
            V_max = self.scaling_v_max

        mask = (self.voltage > V_min) & (self.voltage < V_max)
        cur_unbiased_masked: NDArray[np.float64] = cur_unbiased[mask]
        cur_biased_masked: NDArray[np.float64] = cur_biased[mask]

        ratio: np.float64 = np.mean(cur_biased_masked/cur_unbiased_masked)

        return cur_unbiased*ratio

    ##
    # @brief Shift an unbiased current curve by a given voltage range.
    #
    # This method calculates the averaged distance between unbiased and biased traces.
    #
    # @param cur_unbiased Unbiased current array to be shifted.
    # @param cur_biased Biased current to be matched.
    # @param V_min Minimum value of the voltage window.
    # @param V_max Maximum value of the voltage window.
    # @return Shifted unbiased current array.
    def shift_curve(
        self,
        cur_unbiased: NDArray[np.float64],
        cur_biased: NDArray[np.float64],
        V_min: float = None,
        V_max: float = None
    )  -> NDArray[np.float64]:

        """
        Shift unbiased curve to match the biased one
        in the specified range
        """

        # Assign defaults if no value is provided
        if V_min is None:
            V_min = self.v_min
        if V_max is None:
            V_max = self.v_max

        mask = (self.voltage > V_min) & (self.voltage < V_max)
        cur_unbiased_masked: NDArray[np.float64] = cur_unbiased[mask]
        cur_biased_masked: NDArray[np.float64] = cur_biased[mask]

        shift: float = np.mean(cur_biased_masked - cur_unbiased_masked)

        return cur_unbiased + shift

    ##
    # @brief Compute the -40V slope and negative ion current for a reconstructed
    #        unbiased curve (obtained either via scaling or shifting).
    #
    # This helper factors out the computation shared by the scaling and
    # shifting branches of negative_collector(): it does not care how
    # current_reconstructed was obtained, only that it represents an
    # unbiased curve already brought to the same reference as bcurrent.
    #
    # @param current_reconstructed Unbiased current after scaling/shifting.
    # @param bcurrent Biased current being compared against.
    # @param idx_minus_40V Index of the -40V point in the voltage array.
    # @return Tuple (value of current_reconstructed at -40V,
    #         full negative ion current array, negative ion current at -40V).
    def _helper_computation(
        self,
        current_reconstructed: NDArray[np.float64],
        bcurrent: NDArray[np.float64],
        idx_minus_40V: int
    ) -> Tuple[np.float64, NDArray[np.float64], np.float64]:

        c_unb_reconstructed_minus_40V: np.float64 = current_reconstructed[idx_minus_40V]
        ni_current: NDArray[np.float64] = bcurrent - current_reconstructed
        ni_minus_40V: np.float64 = ni_current[idx_minus_40V]

        return c_unb_reconstructed_minus_40V, ni_current, ni_minus_40V

    ##
    # @brief Compute negative ion current for the negative collector configuration.
    #
    # Each biased current is then compared with each scaled/shifted
    # unbiased current, and all resulting negative ion current estimates are
    # aggregated into mean and standard deviation arrays.
    #
    # The biased current at the configured -90 V reference point is also used to
    # estimate the positive ion current statistics.
    #
    # @return None
    def negative_collector(self) -> None:
        """
        Subtract any shifted unbiased curve to any biased one to measure the negative ion current
        """

        all_ni_results_scaling: List[np.float64] = []
        all_ni_results_shifting: List[np.float64] = []
        all_ni_minus_40V_shifting: list[np.float64] = []
        all_ni_minus_40V_scaling: list[np.float64] = []
        all_slopes_minus_40V_scaling: list[np.float64] = []
        all_slopes_minus_40V_shifting: list[np.float64] = []
        pi_values: List[np.float64] = []
        idx_90v: int = np.argmin(np.abs(self.voltage - (self.minus_90V)))
        idx_minus_40V: int = np.argmin(np.abs(self.voltage - (self.minus_40V)))

        for bcurrent in self.biased_currents:

            pi_values.append(bcurrent[idx_90v])

            for ucurrent in self.unbiased_currents:

                # Scale/shift and subtract unbiased currents
                c_unb_scaled: NDArray[np.float64] = self.scale_curve(ucurrent, bcurrent)
                c_unb_scaled_minus_40V, ni_current_scaled, ni_scaled_minus_40V = self._helper_computation(
                    c_unb_scaled, bcurrent, idx_minus_40V
                )
                all_slopes_minus_40V_scaling.append(c_unb_scaled_minus_40V)
                all_ni_results_scaling.append(ni_current_scaled)
                all_ni_minus_40V_scaling.append(ni_scaled_minus_40V)

                c_unb_shifted: NDArray[np.float64] = self.shift_curve(ucurrent, bcurrent)
                c_unb_shifted_minus_40V, ni_current_shifted, ni_shifted_minus_40V = self._helper_computation(
                    c_unb_shifted, bcurrent, idx_minus_40V
                )
                all_slopes_minus_40V_shifting.append(c_unb_shifted_minus_40V)
                all_ni_results_shifting.append(ni_current_shifted)
                all_ni_minus_40V_shifting.append(ni_shifted_minus_40V)

        # Saving results
        self.ni_avg_nc_scaling = np.mean(all_ni_results_scaling, axis=0)
        self.ni_std_nc_scaling = np.abs(np.max(all_ni_results_scaling, axis=0) - np.min(all_ni_results_scaling, axis=0))/2
        self.all_slopes_minus_40V_scaling = np.array(all_slopes_minus_40V_scaling)
        self.all_ni_minus_40V_scaling = np.array(all_ni_minus_40V_scaling)

        self.ni_avg_nc_shifting = np.mean(all_ni_results_shifting, axis=0)
        self.ni_std_nc_shifting = np.abs(np.max(all_ni_results_shifting, axis=0) - np.min(all_ni_results_shifting, axis=0))/2
        self.all_slopes_minus_40V_shifting = np.array(all_slopes_minus_40V_shifting)
        self.all_ni_minus_40V_shifting = np.array(all_ni_minus_40V_shifting)

        self.pi_avg = np.mean(pi_values)
        self.pi_std = np.std(pi_values)

     ##
    # @brief Compute negative ion current for the positive collector configuration.
    #
    # Each biased current is subtracted from each unscaled unbiased current and
    # the resulting current differences are combined into mean and standard
    # deviation arrays.
    #
    # @return None
    def positive_collector(self) -> None:

        idx_plus_20V: int = np.argmin(np.abs(self.voltage - (self.plus_20V)))
        all_ni_results_pc: List[np.float64] = []
        all_ni_plus_20V: List[np.float64] = []


        for bcurrent in self.biased_currents:

            for ucurrent in self.unbiased_currents:

                all_ni_results_pc.append(bcurrent - ucurrent)
                all_ni_plus_20V.append(bcurrent[idx_plus_20V] - ucurrent[idx_plus_20V])

        # Saving results
        self.ni_avg_pc: NDArray[np.float64] = np.mean(all_ni_results_pc, axis=0)
        self.ni_std_pc: NDArray[np.float64] = np.std(all_ni_results_pc, axis=0, ddof = 1)
        self.all_ni_plus_20V: NDArray[np.float64] = np.array(all_ni_plus_20V)

    ##
    # @brief Visualizes the discrepancy between the negative ion current
    #        estimated via the scaling and shifting methods.
    #
    # The average negative ion (NI) current computed with the scaling approach is
    # compared to the one obtained with the shifting approach (both previously
    # produced by `negative_collector`). The method plots both curves as a
    # function of collector voltage and displays the uncertainty band associated
    # with the scaling method.
    #
    # A figure showing both curves and the scaling uncertainty envelope is saved
    # to the results directory.
    #
    # @return None
    def plot_ni_comparison(self) -> None:
        """
        Compares NI current obtained via Scaling vs Shifting.
        Visualizes the discrepancy to check for equality.
        """
        if self.ni_avg_nc_scaling is None or self.ni_avg_nc_shifting is None:
            raise ValueError("Run negative_collector() first!")

        fig, ax = plt.subplots(figsize=self.style.figsize)
        ax.plot(self.voltage, self.ni_avg_nc_scaling*self.current_scale, label='Scaling Method', color='green', ls = self.style.linestyle_1)
        ax.plot(self.voltage, self.ni_avg_nc_shifting*self.current_scale, label='Shifting Method', color='red', ls = self.style.linestyle_2)
        ax.fill_between(self.voltage,
                        self.ni_avg_nc_scaling*self.current_scale - self.ni_std_nc_scaling*self.current_scale,
                        self.ni_avg_nc_scaling*self.current_scale + self.ni_std_nc_scaling*self.current_scale,
                        color='green', alpha=0.2)

        ax.set_title("NI Current Comparison: Scaling vs Shifting")
        ax.set_xlabel("Collector Voltage (V)")
        ax.set_ylabel("Current (nA)")
        # -10 avoids the region near the plasma potential
        ax.set_xlim(self.voltage.min(), self.threshold_voltage_negative)
        ax.legend()
        ax.grid(alpha = self.style.grid_transparency, ls = self.style.grid_linestyle)

        figurename = self.results_path / 'ni_shift_vs_scale.pdf'

        plt.savefig(figurename, dpi=300)
        plt.close(fig)

    ##
    # @brief Gaussian probability density function.
    #
    # @param x Point(s) at which to evaluate the density.
    # @param mu Mean of the distribution.
    # @param sigma Standard deviation of the distribution.
    # @return Value(s) of the Gaussian PDF at x.
    @staticmethod
    def normal_distribution(x: float, mu: float, sigma: float) -> float:
        return np.exp(-((x-mu)/sigma)**2/2)/(sigma*np.sqrt(2*np.pi))

    ##
    # @brief Fits a Gaussian distribution to the input data and computes the
    #        chi-square goodness-of-fit statistic. Performs no plotting.
    #
    # The dispersion of `data` around its mean is computed and sorted. A
    # histogram is built twice on identical bins: once with raw counts (used
    # for the chi-square test) and once normalized to a density (used to fit
    # the Gaussian, since curve_fit compares against a probability density,
    # not raw counts). The Gaussian is fit to the density histogram via
    # scipy.optimize.curve_fit, which additionally provides the covariance
    # matrix of the fitted parameters. Expected bin counts for the
    # chi-square test are obtained by exact integration of the fitted
    # Gaussian over each bin (via the CDF).
    #
    # @param data Current array (scaled) to analyze.
    # @return Tuple (sorted dispersion array, bin edges used for the
    #         histogram, fitted parameters [mu, sigma], covariance matrix
    #         of the fit, chi-square statistic, number of degrees of freedom).
    def _fit_distribution(
        self,
        data: NDArray[np.float64]
    ) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], float, int]:

        mean_val: np.float64 = float(np.mean(data))
        dispersion: NDArray[np.float64] = data - mean_val
        dispersion.sort()

        # raw counts for chi-square
        observed_counts, bin_edges = np.histogram(dispersion, bins='auto')
        # densities for fitting
        observed_density: NDArray[np.float64]
        observed_density, _ = np.histogram(dispersion, bins=bin_edges, density=True)

        centers = (0.5*(bin_edges[1:]+bin_edges[:-1]))
        pars: NDArray[np.float64]
        cov: NDArray[np.float64]
        pars, cov = curve_fit(self.normal_distribution, centers, observed_density, p0=[0,1])

        cdf_upper = norm.cdf(bin_edges[1:], loc=pars[0], scale=pars[1])
        cdf_lower = norm.cdf(bin_edges[:-1], loc=pars[0], scale=pars[1])
        bin_probabilities = cdf_upper - cdf_lower
        expected_counts = bin_probabilities * len(dispersion)
        ddof_adjustment = len(pars)
        chi2: float = np.sum((observed_counts - expected_counts)**2/expected_counts)

        ndof: int = len(observed_counts) - ddof_adjustment - 1

        return dispersion, bin_edges, pars, cov, chi2, ndof

    ##
    # @brief Plots a diagnostic histogram of an already-fitted Gaussian distribution.
    #
    # Draws the dispersion histogram together with the fitted Gaussian curve
    # and annotates the figure with the fitted parameters (mu, sigma) and the
    # chi-square goodness-of-fit statistic. Fitting itself is performed
    # beforehand by _fit_distribution(); this method only visualizes the
    # result and saves it to disk.
    #
    # @param fit_result Tuple (dispersion, bin_edges, pars, cov, chi2, ndof)
    #        as returned by _fit_distribution().
    # @param xlabel Label for the horizontal plot axis.
    # @param filename Target file path where the plot figure is saved.
    # @return None
    def _plot_distribution(
        self,
        fit_result: Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], float, int],
        xlabel: str,
        filename: Path
        ) -> None:

        dispersion, bin_edges, pars, cov, chi2, ndof = fit_result

        x = np.linspace(dispersion.min(), dispersion.max(), 100)
        y = self.normal_distribution(x, pars[0], pars[1])

        fig, ax = plt.subplots(figsize=self.style.figsize)

        ax.set_xlabel(xlabel)
        ax.set_ylabel("Probability Density")
        ax.plot(x, y, color='red', ls=self.style.linestyle_2, label='Normal distribution')
        ax.hist(dispersion, bins=bin_edges, density=True)
        ax.plot([], [], ' ', label=rf'$\mu={pars[0]:.2f} \pm {np.sqrt(cov[0,0]):.2f}$')
        ax.plot([], [], ' ', label=rf'$\sigma={pars[1]:.2f} \pm {np.sqrt(cov[1,1 ]):.2f}$')
        ax.plot([], [], ' ', label=rf'$\chi^2/ndof$ = {chi2:.1f}/{ndof}')
        ax.legend()
        ax.grid(axis='y', alpha=self.style.grid_transparency, ls=self.style.grid_linestyle)

        plt.tight_layout()
        plt.savefig(filename, dpi=300)
        plt.close(fig)

    ##
    # @brief Plots a histogram comparison of the -40V slope estimates (scaling vs shifting).
    #
    # Draws overlapping histograms of the slope values obtained with the
    # scaling and shifting methods, marks their respective means with
    # vertical lines, and saves the comparison figure to disk.
    #
    # @return None
    def _plot_slope_comparison(self) -> None:

        fig, ax = plt.subplots(figsize=self.style.figsize)

        ax.hist(
            self.all_slopes_minus_40V_scaling * self.current_scale,
            bins='auto',
            alpha=self.style.grid_transparency,
            label='Scaling'
        )

        ax.hist(
            self.all_slopes_minus_40V_shifting * self.current_scale,
            bins='auto',
            alpha=self.style.grid_transparency,
            label='Shifting'
        )

        mean_slope_sc = float(np.mean(self.all_slopes_minus_40V_scaling) * self.current_scale)
        mean_slope_sh = float(np.mean(self.all_slopes_minus_40V_shifting) * self.current_scale)

        ax.axvline(mean_slope_sc, color='blue', linestyle=self.style.linestyle_2, label=f'Mean Scaling: {mean_slope_sc:.2e}')
        ax.axvline(mean_slope_sh, color='orange', linestyle=self.style.linestyle_2, label=f'Mean Shifting: {mean_slope_sh:.2e}')
        ax.set_title(f"Slope distribution at {self.minus_40V}V - {self.results_path.name}")
        ax.set_xlabel("NI Current [nA]")
        ax.legend()
        ax.grid(axis='y', alpha=self.style.grid_transparency, ls=self.style.grid_linestyle)

        plt.tight_layout()
        plt.savefig(self.results_path / "comparison_slope_distribution.pdf", dpi=300)
        plt.close(fig)



    ##
    # @brief Displays and exports statistical distributions of NI measurements.
    #
    # Evaluates the statistical variability and dispersion of negative ion current
    # acquisitions at specific collector biases (-40 V for negative collector and
    # +20 V for positive collector) alongside slope distributions. Generates histogram
    # comparison plots and exports dispersion data to a text file.
    #
    # @return None
    def variabilities(self) -> None:

        # Negative Collector (-40V) Distribution
        if len(self.all_ni_minus_40V_scaling) == 0 or len(self.all_ni_minus_40V_shifting) == 0:
            print("\nInsufficient data to compute the distributions.")
            print("Please run negative_collector(ratio) first.")
            return

        # Negative ion distribution at -40V with shift method
        data_nc_shift = self.all_ni_minus_40V_shifting * self.current_scale
        fit_result_nc_shift = self._fit_distribution(data_nc_shift)
        self._plot_distribution(
                                fit_result_nc_shift,
                                xlabel="Dispersion [nA]",
                                filename=self.results_path / "distribution_NI_40V_shift.pdf"
                            )
        dispersion_nc_shift = fit_result_nc_shift[0]

        # Negative ion distribution at -40V with scale method
        data_nc_scale = self.all_ni_minus_40V_scaling * self.current_scale
        fit_result_nc_scale = self._fit_distribution(data_nc_scale)
        self._plot_distribution(
                                fit_result_nc_scale,
                                xlabel="Dispersion [nA]",
                                filename=self.results_path / "distribution_NI_40V_scale.pdf"
                            )
        dispersion_nc_scale = fit_result_nc_scale[0]

        # Slope Distribution (-40V)
        if len(self.all_slopes_minus_40V_scaling) == 0 or len(self.all_slopes_minus_40V_shifting) == 0:
            print("\nInsufficient data to compute the slope distributions.")
            return

        # Distribution of the slope at -40V with shift method
        data_slope_shift = self.all_slopes_minus_40V_shifting * self.current_scale
        fit_result_slope_shift = self._fit_distribution(data_slope_shift)
        self._plot_distribution(
                                fit_result_slope_shift,
                                xlabel="Dispersion [nA]",
                                filename=self.results_path / "distribution_slope_40V_shift.pdf"
                            )
        dispersion_slope_shift = fit_result_slope_shift[0]

        # Distribution of the slope at -40V with scale method
        data_slope_scale = self.all_slopes_minus_40V_scaling * self.current_scale
        fit_result_slope_scale = self._fit_distribution(data_slope_scale)
        self._plot_distribution(
                                fit_result_slope_scale,
                                xlabel="Dispersion [nA]",
                                filename=self.results_path / "distribution_slope_40V_scale.pdf"
                            )
        dispersion_slope_scale = fit_result_slope_scale[0]

        # Plot slope comparison: scale vs shift

        self._plot_slope_comparison()

        # Positive Collector (+20V) Distribution
        if self.all_ni_plus_20V is None or len(self.all_ni_plus_20V) == 0:
            print("\nInsufficient data to compute positive collector distributions.")
            print("Please run positive_collector() first.")
            return

        data_pc = self.all_ni_plus_20V * self.current_scale
        fit_result_pc = self._fit_distribution(data_pc)
        self._plot_distribution(
            fit_result_pc,
            xlabel="Dispersion [nA]",
            filename=self.results_path / "distribution_NI_pc.pdf"
        )
        dispersion_pc = fit_result_pc[0]

        # Save dispersion output file
        filename_dispersion = self.results_path / 'dispersion_ni.txt'
        with open(filename_dispersion, 'w') as f:
            for d_nc_sh, d_nc_sc, d_pc in zip(dispersion_nc_shift, dispersion_nc_scale, dispersion_pc):
                f.write(f"{d_nc_sh} {d_nc_sc} {d_pc}\n")





