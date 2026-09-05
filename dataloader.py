from __future__ import annotations

##
# @file dataloader.py
# @brief Loading and validation of the experimental current-voltage data files.
#
# This module discovers and reads the unbiased and biased .dat files described
# in the configuration, discarding empty, incomplete, or corrupted acquisitions,
# and builds the voltage vector shared by the rest of the analysis pipeline.

from configreader import ConfigReader

import numpy as np
from pathlib import Path
from typing import List, Tuple
from numpy.typing import NDArray

##
# @class DataLoader
# @brief Class for handling the loading of experimental data.
#
# This class is responsible for reading paths and parameters from the
# configuration file, locating data files in the specified folders,
# loading valid data from the files, discarding corrupted or inconsistent
# files, and generating the associated voltage vector.
class DataLoader:
    ##
    # @brief Constructor of the DataLoader class.
    #
    # Initializes the paths of the biased and unbiased data folders,
    # creates the results folder if it does not exist, and generates
    # the voltage vector based on the configuration parameters.
    #
    # @param config Configuration object used to read parameters.
    # @param directory Optional base directory from which data are read
    #        and results are saved. If None, the directory of the current
    #        file is used.
    def __init__(
        self,
        config: 'ConfigReader',
        directory: None | Path
) -> None:

        ##
        # @brief Access to the configuration file.
        self.config = config
        self.subdirectory: Path | None = directory

        ##
        # @brief Main directory containing the current file.
        if directory is not None:
            self.base_dir: Path = directory
        else:
            self.base_dir: Path = Path('.').resolve()

        ##
        # @brief Name of the folder containing unbiased data.
        unbiased_folder: str = self.config.get('UNBIASED_FOLDER', 'unbiased')

        ##
        # @brief Name of the folder containing biased data.
        biased_folder: str = self.config.get('BIASED_FOLDER', 'biased')

        ##
        # @brief Extension of the data files to load.
        self.file_extension: str = self.config.get('FILE_EXTENSION', '.dat')

        ##
        # @brief Whether informational messages should be printed.
        self.verbose: bool = self.config.get('VERBOSE', False)

        ##
        # @brief Name of the folder where results will be stored.
        results_folder: str = self.config.get('RESULTS_FOLDER', 'results')

        # @brief Path to the folder containing unbiased files.
        self.unbiased_path: Path = self.base_dir / unbiased_folder

        ##
        # @brief Path to the folder containing biased files.
        self.biased_path: Path = self.base_dir / biased_folder

        ##
        # @brief Path to the results folder; created if it does not exist.
        self.results_path: Path = self.base_dir / results_folder
        self.results_path.mkdir(parents=True, exist_ok=True)

        ##
        # @brief Starting value of the voltage range.
        self.voltage_start: int = self.config.get('VOLTAGE_START', -110)

        ##
        # @brief Ending value of the voltage range.
        self.voltage_stop: int = self.config.get('VOLTAGE_STOP', 40)

        ##
        # @brief Voltage vector to be generated linearly.
        self.voltage: NDArray[np.float64] | None = None


    ## @brief Generates the voltage array and calculates the file header offset.
    #
    #  @details Populates `self.voltage` with a linear grid between `self.voltage_start`
    #           and `self.voltage_stop`. Computes the number of header rows (`skipheader`)
    #           to skip when loading raw data files based on the scan start point (120 V)
    #           and metadata text lines.
    #
    #  @return int The number of header rows to skip during data reading.
    def fill_voltage_range(self) -> int:

        voltage_step: int = self.voltage_stop + np.absolute(self.voltage_start) + 1

        voltage: NDArray[np.float64] = np.linspace(
            self.voltage_start,
            self.voltage_stop,
            voltage_step
            )

        self.voltage = voltage

        # 120\,V initial point of the scan
        # 4 avoids the first four raws of the file (pure text)
        skipheader: int = 4 + 120 - np.absolute(self.voltage_start)

        return skipheader

    ##
    # @brief Finds all valid data files inside a folder.
    #
    # Verifies that the folder exists and searches for all files with the
    # configured extension. If no files are found, an exception is raised.
    # If VERBOSE is enabled in the configuration, the discovered files are
    # also logged via _log_discovered_files().
    #
    # @param folderpath Path of the folder to analyze.
    # @return Sorted list of full paths to the discovered files.
    # @exception FileNotFoundError Raised if the folder does not exist
    #            or contains no valid files.
    def discover_data_files(self, folderpath: Path) -> List[Path]:
        ##
        # Check if loaded folder exists
        if not folderpath.exists():
            raise FileNotFoundError(
            f"Error: No folder named {folderpath.name} found."
            )
        ##
        # Load .dat files within folder
        files = sorted(list(folderpath.glob(f"*{self.file_extension}")))

        if not files:
            raise FileNotFoundError(
            f"Error: No files found in {folderpath.absolute()}."
            )
        ##
        # distinguish biased - unbiased folder
        foldername = folderpath.name

        if self.verbose is True:

            self._log_discovered_files(files, foldername)


        return files

    ##
    # @brief Prints the name of the folder and the list of discovered files.
    #
    # Pure logging helper: it has no effect on which files are returned
    # by discover_data_files(). Only invoked when VERBOSE is enabled.
    #
    # @param files List of discovered file paths.
    # @param foldername Name of the folder the files were found in.
    # @return None
    def _log_discovered_files(self, files: List[Path], foldername: str) -> None:

        print(
            f'{foldername} data found: \n'
            )

        for f in files:
            print(f'{f.name}')
        print('\n')

    ##
    # @brief Loads and validates a list of data files.
    #
    # Applies _safe_load() to every file in the list and discards the
    # ones that fail validation (empty, wrong length, or containing NaN).
    #
    # @param files List of file paths to load.
    # @return List of valid data arrays.
    def _load_valid_files(self, files: List[Path]) -> List[NDArray]:

        current_list: List[NDArray | None] = [self._safe_load(f) for f in files]
        current_list_filtered: List[NDArray] = [c for c in current_list if c is not None]

        return current_list_filtered

    ##
    # @brief Loads all unbiased and biased data, excluding corrupted files.
    #
    # Files are first discovered in their respective folders and then loaded
    # safely using the _safe_load() method. Invalid data are discarded.
    #
    # @return Tuple containing the list of valid unbiased arrays and the
    #         list of valid biased arrays.
    def load_all_data(self) -> Tuple[List[NDArray], List[NDArray]]:

        u_files: List[Path] = self.discover_data_files(self.unbiased_path)
        u_raw: List[NDArray] = self._load_valid_files(u_files)

        b_files: List[Path] = self.discover_data_files(self.biased_path)
        b_raw: List[NDArray] = self._load_valid_files(b_files)

        return u_raw, b_raw

    ##
    # @brief Loads a data file while verifying its validity.
    #
    # The method checks that the file is not empty, has the expected
    # length, and does not contain NaN values.
    #
    # If any problem is detected, the file is skipped and None is returned.
    #
    # @param filepath Path of the file to load.
    # @return Data array if valid, otherwise None.
    def _safe_load(self, filepath: Path) -> NDArray[np.float64] | None:
        ##
        # @brief Check if the file is empty.
        if filepath.stat().st_size == 0:
            print(f'WARNING: filename {filepath.name} is empty.')
            return None

        try:
            skipheader = self.fill_voltage_range()
            current = self.load_data(filepath, skipheader)

            ##
            # @brief Check that the data are not empty and have the expected length.
            if current.size == 0 or len(current) != len(self.voltage):
                print(f"WARNING: Missing data points {filepath.name} skipped.")
                return None

            ##
            # @brief Check for NaN values in the loaded data.
            if np.isnan(current).any():
                print(f"WARNING: Corrupted data {filepath.name} contains NaN values.")
                return None

            print(
            f'{filepath.name} loaded correctly.'
            )
            return current

        except Exception as e:

            print(f"Encountered error while loading {filepath.name}: {e}")
            print(f'{filepath.name} skipped.')
            return None

    ##
    # @brief Loads a single .dat file.
    #
    # The file is read while ignoring header lines and comments.
    # The second column of the dataset is returned.
    #
    # @param filename Name or path of the file to load.
    # @param skipheader Number of raws to be skipped while loading the currents.
    #
    # @return NumPy array containing the values of the second column.
    @staticmethod
    def load_data(filename: str, skipheader: int) -> NDArray[np.float64]:

        data = np.genfromtxt(filename, comments="#", skip_header=skipheader, unpack=True)
        return data[1]
