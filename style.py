##
# @file style.py
#
# @brief PlotStyle defines the styling parameters shared by every plot.
from dataclasses import dataclass
import matplotlib.pyplot as plt
from configreader import ConfigReader

##
# @class PlotStyle
# @brief Bundles the figure/axis styling parameters shared by every plot.
#
# Passed explicitly to plotting functions instead of letting them read the
# global config object: a plotting function only needs styling, not the
# whole configuration. The user can decide the plot characteristic editing the
# configuration file.

@dataclass(frozen=True)
class PlotStyle:
    figsize: tuple
    fontsize: int
    linewidth: float
    linestyle_1: str
    linestyle_2: str
    marker: str
    marker_2: str
    grid_transparency: float
    grid_linestyle: str

    ##
    # @brief Builds a PlotStyle from a configuration object and applies it globally.
    #
    # Reads the styling-related keys from config (with sensible defaults) and
    # immediately applies the font size to matplotlib's global rcParams via
    # apply_font(). It applies figsize, linewidth, linestyle, marker,
    # grid_transparency (alpha) as well.
    #
    # @param config Configuration object to read styling parameters from.
    # @return PlotStyle instance built from the configuration.
    @classmethod
    def from_config(cls, config: ConfigReader) -> 'PlotStyle':
        style = cls(
            figsize=config.get('FIGSIZE', (10, 8)),
            fontsize=config.get('FONTSIZE', 14),
            linewidth=config.get('LINE_WIDTH', 1.0),
            linestyle_1=config.get('LINE_STYLE_1', '-'),
            linestyle_2=config.get('LINE_STYLE_2', '--'),
            marker=config.get('MARKER', '.'),
            marker_2=config.get('MARKER_2', '*'),
            grid_transparency=config.get('GRID_TRANSPARENCY', 0.7),
            grid_linestyle=config.get('GRID_LINESTYLE', 'dashdot'),
        )
        style.apply_font()

        return style

    ##
    # @brief Applies this style's font size to matplotlib's global rcParams.
    #
    # @return None
    def apply_font(self) -> None:
        # Apply global fontsize
        plt.rcParams.update({'font.size': self.fontsize})
