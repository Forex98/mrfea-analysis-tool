##
# @file main.py
# @brief Main analysis module.
#
# This script performs the complete analysis workflow for the negative ion
# current measurements. It loads data, processes them using the StandardMethod
# analysis pipeline, generates plots, and optionally compares multiple datasets.
#
# @section main_features Main features
# - Automatic loading of experimental data
# - Negative and positive collector current analysis
# - Distribution function computation
# - Comparison between multiple datasets
# - Plot generation and PDF export
#
# @section dependencies Dependencies
# The module relies on the following components:
# - DataLoader: handles loading experimental data
# - StandardMethod: performs the main data analysis
# - ConfigReader: reads configuration parameters from file
# - functions: computation/plotting helpers and process functions
#
# Install the following third part libraries:
# - numpy
# - matplotlib
# - scipy
# - gdown
#
# @section main_usage Typical usage
# Run the script directly:
#
# @code{.sh}
# python main.py
# @endcode
#
# The program will automatically detect data folders and guide the user
# through the analysis process.
# If data are not detected locally, they will be downloaded from
# Google Drive, provided that the folder URL is written
# in the configuration file.

# @author
# Alessandro Forese

from pathlib import Path
from modules.configreader import ConfigReader
from modules.downloader import GoogleDriveDownloader
from modules.functions import process_folders, comparison
from modules.style import PlotStyle

import numpy as np
import matplotlib

##
# @brief Ensures experimental dataset directories exist locally, fetching them from Google Drive if missing.
#
# Scans the base directory for valid data folders (excluding standard non-data
# directories and user-excluded folders). If no valid dataset folders are found,
# it retrieves the Google Drive URL from the configuration object and automatically
# downloads the required data structure.
#
# @param config Configuration reader instance holding parameters (e.g., DATA_DRIVE_URL).
# @param base_path Root directory path where dataset folders are expected to reside.
# @param bad_names Set of system or output folder names to ignore (e.g., '__pycache__', '.git', 'results').
# @param excluded_folders List of user-defined directory names to exclude from the search.
# @return None
def ensure_data_available(config: ConfigReader, base_path: Path, bad_names: set, excluded_folders: list) -> None:

    existing = [
        d for d in base_path.iterdir()
        if d.is_dir() and d.name not in bad_names and d.name not in excluded_folders
    ]

    if not existing:
        drive_url = config.get('DATA_DRIVE_URL')
        if not drive_url:
            print('\nWARNING: No dataset found and no DATA_DRIVE_URL configured.')
            return

        print('\nNo local dataset found. Downloading data from Google Drive...')
        try:

            downloader = GoogleDriveDownloader(output_dir=base_path)
            downloader.download_all(drive_url)
            print('Download completed successfully!')
        except Exception as e:
            print(f'\nERROR: failed to download data from Google Drive: {e}')

##
# @brief Entry point of the analysis program.
#
# Scans the working directory, detects available datasets (excluding the
# folders listed under EXCLUDED_FOLDERS in config.txt). If no folder is detected
# the software will download data from Google Drive.
# The main function manages the full analysis workflow through minimal user interaction.
#
# @param config Configuration object (explicit dependency, injected by the caller).
# @return int Exit status code (`0` if execution completes successfully).
def main(config: ConfigReader) -> int:
    style = PlotStyle.from_config(config)

    base_path = Path('.')
    bad_names = ['__pycache__', '.git', 'results', 'latex', 'html', 'modules']
    excluded_folders: list = config.get('EXCLUDED_FOLDERS', [])
    measurements_folder: str = config.get('MEASUREMENTS_FOLDER', 'measurements')
    measurements_path = base_path / measurements_folder
    measurements_path.mkdir(parents=True, exist_ok=True)


    ensure_data_available(config, measurements_path, bad_names, excluded_folders)

    print('\nLoading directories...')

    directories = [
        d for d in measurements_path.iterdir()
        if d.is_dir() and d.name not in bad_names and d.name not in excluded_folders
    ]
    directories.sort()

    if len(directories) == 0:
        print('\nWARNING: your folder is empty')
        print('No directory found.')
        return 0

    for directory in directories:
        print(f'{directory.name} found.')

    unbiased_path = measurements_path / 'unbiased'
    biased_path = measurements_path / 'biased'

    if unbiased_path in directories and biased_path in directories:
        print('\nUnbiased and Biased directories found in the main folder')
        print('Do you want to analyse them? [y/n]')

        if input() == 'y':
            print('\nAnalysis of a single data set:')
            print('No comparison will be done')
            process_folders(folders=None, config=config, style=style)
            return 0

        directories.remove(unbiased_path)
        directories.remove(biased_path)
        print('\nBiased and Unbiased folders ignored.')

    print('\nThe following folders will be analysed:')
    for directory in directories:
        print(f'{directory.name}')

    try:
        results_list = process_folders(folders=directories, config=config, style=style)
        comparison(results_list, config, style)
        print(f'\n=== Analysis complete: {len(results_list)} dataset(s) processed. ===')
        print("Per-dataset plots: each dataset's results/ subfolder.")
        if len(results_list) > 1:
            print('Comparison plots: repository root (comparison_*.pdf).')
    except Exception as e:
        print(f'\nERROR: analysis failed: {e}')
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    print(f'numpy version: {np.__version__}')
    print(f'matplotlib version: {matplotlib.__version__}')

    config = ConfigReader('config.txt')
    main(config)
