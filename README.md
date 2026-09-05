# MRFEA Negative Ion Analysis Tool

[![Standard README compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/richardlitt/standard-readme)

Data processing and diagnostic analysis pipeline for Magnetized Retarding Field Energy Analyzer (MRFEA) current-voltage (I-V) measurements in low-pressure deuterium plasmas.

## Table of Contents

- [State Of The Art](#state-of-the-art)
- [Install](#install)
- [Sample Data](#sample-data)
- [Usage](#usage)
- [Configuration](#configuration)
- [Examples](#examples)
- [Modules](#modules)

## State Of The Art

In low-pressure hydrogen/deuterium plasmas, surface-produced negative ions are generated when positive ions or neutral species interact with a negatively biased sample surface (V_bias). These negative ions are accelerated across the plasma sheath towards the diagnostic.

The Magnetized Retarding Field Energy Analyzer (MRFEA) isolates surface negative ions by employing a localized rectangular magnetic barrier (B ≈ 450 G). Due to their small Larmor radius, plasma electrons are strongly magnetized and suppressed by the barrier. Conversely, surface-produced negative ions possess a significantly larger Larmor radius, traversing the magnetic barrier to reach the collector across both positive and negative collector bias regimes.

This software pipeline processes raw MRFEA collector current characteristics by comparing biased (sample biased at -60 V) and unbiased (sample kept at ground) acquisitions:

* **Shift Method:** Reconstructs the zero-negative-ion baseline by applying a constant vertical offset to the unbiased curve over a configured voltage range [V_min, V_max].
* **Scale Method:** Reconstructs the baseline by multiplying the unbiased curve by the average ratio, calculated over the range [V_scaling_min, V_scaling_max]:
  $$\frac{I_{\text{biased}}}{I_{\text{unbiased}}}$$
* **Energy Distribution Function (NIEDF):** Calculates the negative ion current derivative using Savitzky-Golay numerical filtering:
  $$\frac{dn_i}{dV}$$
* **Statistical Variability:** Evaluates dispersion distributions using Gaussian fits (μ, σ, χ²/ndof) across collector biases.
* **Positive Ion Flux:** Estimated from the Bohm criterion as

  <a name="eq-piflux"></a>
  $$\Phi_{PI} = 0.6\, n_e \sqrt{T_e c^2 / M_i} \qquad \text{(1)}$$

  where n_e and T_e are the Langmuir-probe electron density and temperature (`ELECTRON_DENSITIES`, `ELECTRON_TEMPERATURES`) and M_i is the ion mass (`ION_MASS`).
* **Pressure Attenuation Correction:** For pressure scans, the -40V negative ion current is corrected for collisional detachment losses via
  $$H^- + H_2 \rightarrow H + H_2 + e^-$$
  over the MRFEA collector distance d (`DISTANCE`) as
  $$I_{\text{corr}} = I \cdot e^{d/\lambda}, \qquad \lambda = \frac{1}{n_{\text{gas}}\,\sigma}, \qquad n_{\text{gas}} = \frac{p}{k_B T_{\text{gas}}}$$
  with σ the detachment cross section (`CROSS_SECTION`, `GAS_TEMPERATURE`, `BOLTZMANN`).


## Install

Clone the repository:

```sh
git clone git@github.com:Forex98/mrfea-analysis-tool.git
cd mrfea-analysis-tool
```

This project requires **Python 3.8+** and standard scientific libraries.

Install all dependencies via `pip`:

```sh
pip install numpy matplotlib scipy gdown
```

## Sample Data

Don't have your own MRFEA acquisitions yet? Two ready-to-use datasets are available for testing the full pipeline, including the comparison mode:

| Scan type | Control parameter | Google Drive link |
| :--- | :--- | :--- |
| Pressure scan | `PRESSURES` | https://drive.google.com/drive/folders/11DwjXjeiXeNJIPMTSH12uOGSi7H4B6j8?usp=drive_link |
| Power scan | `POWERS` | https://drive.google.com/drive/folders/1t2s-ii6JlqrwDrMq75_Y7C-gfdUquRzF?usp=drive_link |

To use one of them, either:
- **let the tool download it automatically** — set `DATA_DRIVE_URL` in `config.txt` to the chosen link and run `python main.py` with no local dataset folders in place (see [Fetching data automatically from Google Drive](#fetching-data-automatically-from-google-drive)); or
- **download it manually** from the link and extract it into the repository root, then run `python main.py` as usual.

Only four keys need to change to switch between the two sample scenarios — everything else in `config.txt` stays the same:

| Key | Power scan sample | Pressure scan sample |
| :--- | :--- | :--- |
| `DATA_DRIVE_URL` | `.../folders/1t2s-ii6JlqrwDrMq75_Y7C-gfdUquRzF` | `.../folders/11DwjXjeiXeNJIPMTSH12uOGSi7H4B6j8` |
| `POWERS` | `[200, 300, 400, 600]` | `[]` |
| `PRESSURES` | `[]` | `[0.2, 1.2, 2, 4, 5]` |
| `ELECTRON_DENSITIES` | `[3.28E15, 8.10E15, 13.5E15, 19.7E15]` | `[2.13E15, 1.65E15, 2.35E15, 2.70E15, 1.64E15]` |
| `ELECTRON_TEMPERATURES` | `[0.11, 0.12, 0.16, 0.19]` | `[0.57, 0.13, 0.12, 0.11, 0.15]` |

`ELECTRON_DENSITIES` and `ELECTRON_TEMPERATURES` must always have the same length and order as whichever of `POWERS`/`PRESSURES` is filled in — each entry is the Langmuir-probe measurement for that experimental condition. Only one of `POWERS`/`PRESSURES` should be non-empty at a time.

## Usage

Run the primary analysis pipeline directly from the repository root:

```sh
python main.py
```

### Execution workflow

- **Dataset Discovery**: Scans the working directory for data folders containing unbiased/ and biased/ subdirectories.
- **Drive Retrieval**: Automatically downloads dataset archives using gdown if local data folders are missing and a valid DATA_DRIVE_URL is provided.
- **Interactive Validation**: Displays baseline I-V plots with interactive GUI checkboxes to disable corrupted or noisy acquisition traces.
- **Export & Comparison**: Generates analysis output plots (PDF format) and evaluates comparatives across varying experimental parameters (such as pressure or RF power).

## Configuration

Analysis parameters, experimental constants, and plot options are configured inside `config.txt`.

| Key | Default / Example | Description |
| :--- | :--- | :--- |
| DATA_DRIVE_URL | Google Drive URL | Remote directory link for dataset download |
| METHOD | 'scaling' | Baseline reconstruction algorithm ('scaling' or 'shifting')|
| VOLTAGE_START |-110 | Minimum collector sweep voltage (V) |
| VOLTAGE_STOP | 40 | Maximum collector sweep voltage (V) |
| V_MIN, V_MAX | -90, -70 | Voltage interval for the shift baseline method (V) |
| SCALING_V_MIN, SCALING_V_MAX | -90, -70 | Voltage interval for the scale baseline method (V) |
| ION_MASS | 1875E6 | Deuterium Mass used for flux calculations (eV/c²) |
| CROSS_SECTION | 4.43E-20 | Cross section for the collisional detachment reaction (see [State Of The Art](#state-of-the-art)), used for pressure attenuation (m²) |
| POWERS, PRESSURES | [200, 300, 400, 600], [] | Experimental control parameter values used to compare datasets (only one of the two should be non-empty) |
| EXCLUDED_FOLDERS | [] | Folder names to skip during dataset discovery, e.g. output or documentation folders |

The remaining keys (plot styling, MRFEA geometry constants, file-loading options) are documented directly as comments inside `config.txt`.

## Examples

### StandardMethod methods

The `StandardMethod` class provides the main analysis steps for processing and interpreting MRFEA measurements. Its methods are organized into four stages: data cleaning, physics and baseline diagnostics, negative-ion current extraction, and statistical verification.

The typical workflow is:

```python
from standardmethod import StandardMethod

sm = StandardMethod(
    loader.voltage,
    unbiased_raw,
    biased_raw,
    loader.results_path,
    style,
    config
)
```

* **1. Data cleaning**

```python
sm.create_plot()
```

Displays the raw I-V characteristics of all acquisitions using an interactive GUI. The checkboxes allow the user to identify and disable corrupted or noisy traces, for example those affected by plasma fluctuations or acquisition problems. The selected traces are then excluded from the subsequent analysis.

* **2. Baseline reconstruction**

The shift method is a vertical rigid translation of the unbiased trace I_u, which approximates the zero-negative ion baseline. It is implemented in the `StandardMethod` class as follows:

```python
sm.shift_curve(cur_unbiased, cur_biased, V_min, V_max)
```

where V_min and V_max define the voltage window over which the unbiased and biased currents are matched.

The second reconstruction procedure is the scaling method. Experimentally, the electron densities are the only plasma parameters which vary between the two operating sample polarization states. The ratio
$$\frac{N_e^b}{N_e^u}$$
is a measure of the discrepancy between I_b and I_u, as the two currents are determined by the PI flux relation [Eq. (1)](#eq-piflux).

```python
sm.plot_ratio()
```

Aiming to assess the validity of the scale method, `sm.plot_ratio()` plots the average ratio
$$\frac{I_{\text{biased}}}{I_{\text{unbiased}}}$$
as a function of collector voltage. In the voltage region where negative ions are not expected to contribute, the ratio should be approximately constant. This provides a physical diagnostic for the multiplicative baseline reconstruction:

```python
sm.scale_curve(cur_unbiased, cur_biased, V_min, V_max)
```

`scale_curve()` applies that average ratio to the unbiased trace, producing the scaled baseline used to extract the negative-ion current.

* **3. Plasma potential**

```python
sm.derivative_unbiased()
```

Calculates and plots the first derivative of the unbiased current characteristic,
$$\frac{dI_u}{dV}$$
using Savitzky-Golay filtering. The resulting derivative represents the Positive Ion Energy Distribution Function (PIEDF) and is used to identify the plasma potential V_p ≈ 3.4 V. Regarding the MRFEA, when the collector is polarised at approximately V_p, all the PI are repelled and only negative particles are detected (electrons and NI).

* **4. Negative ion extraction**

```python
sm.negative_collector()
```

Extracts the negative-ion current at a negative collector bias (nominally -40 V). This is the main negative-ion value used for quantitative comparisons between different experimental conditions, such as RF power or pressure scans.

```python
sm.positive_collector()
```

Evaluates the collector current at a positive collector bias (nominally +20 V). This measurement provides a complementary diagnostic and is used to characterise the positive-bias response of the MRFEA.

* **5. Statistical analysis**

```python
sm.variabilities()
```

Evaluates the statistical variability of the measurements across the multiple acquisitions. The method characterises the dispersion distribution of the extracted negative ion currents and the stability of the reconstructed baselines. The Gaussian fits provides an indication of measurement repeatability and acquisition quality.

* **6. Comparison shift vs scale method**

```python
sm.plot_ni_comparison()
```

Compares the negative-ion current obtained using the two available baseline reconstruction methods: shifting and scaling. This allows the user to assess how sensitive the extracted negative-ion signal is to the choice of baseline method.

### Single dataset, no comparison

If `unbiased/` and `biased/` are found directly in the working directory, the tool offers to analyse just that one dataset:

```
project/
├── main.py
├── config.txt
├── unbiased/
│   ├── acq_001.dat
│   └── ...
└── biased/
    ├── acq_001.dat
    └── ...
```

```sh
$ python main.py
...
Unbiased and Biased directories found in the main folder
Do you want to analyse them? [y/n]
y

Analysis of a single data set:
No comparison will be done
```

This produces, in `results/`:
- `ni_step.pdf` — negative ion current vs voltage, after baseline subtraction
- `dist_func.pdf` — the negative ion energy distribution function (dn_i/dV)

plus a console summary of the negative- and positive-collector NI currents (`_print_collector_summary`).

### Comparing several experimental conditions

To compare, e.g., an RF power scan, put each condition in its own folder (each containing its own `unbiased/`/`biased/`) and list the values under `POWERS` in `config.txt`:

```
project/
├── config.txt
├── 200W/{unbiased,biased}/
├── 300W/{unbiased,biased}/
├── 400W/{unbiased,biased}/
└── 600W/{unbiased,biased}/
```

```
# config.txt
POWERS = [200, 300, 400, 600]
PRESSURES = []
```

Running `python main.py` now analyses every folder individually (same per-folder output as above) and additionally produces comparison plots at the repository root:
- `comparison_ni_curr.pdf` — NI current curves of all conditions overlaid
- `comparison_energy_distribution.pdf` — NIEDF of all conditions overlaid
- `comparison_minus_40V_plus_20V.pdf` — negative/positive collector current vs Power
- `comparison_NI_curr_vs_pi_flux_power.pdf` — NI current vs positive ion flux, only generated when `ELECTRON_DENSITIES`/`ELECTRON_TEMPERATURES` are also configured

The same workflow applies to a pressure scan by filling `PRESSURES` instead of `POWERS` (only one of the two should be non-empty).

### Choosing the baseline reconstruction method

```
# Shift method: constant offset fitted over [V_MIN, V_MAX]
METHOD = 'shifting'
V_MIN = -90
V_MAX = -70
```

```
# Scale method: multiplicative ratio fitted over [SCALING_V_MIN, SCALING_V_MAX]
METHOD = 'scaling'
SCALING_V_MIN = -90
SCALING_V_MAX = -70
```

### Excluding folders from the scan

Any folder name listed here is skipped during dataset discovery, without being asked about interactively:

```
EXCLUDED_FOLDERS = [plots, docs, old_run_2024]
```

### Fetching data automatically from Google Drive

If no valid dataset folder is found locally and `DATA_DRIVE_URL` points to a shared Google Drive folder, the tool downloads it before analysis starts:

```
# config.txt
DATA_DRIVE_URL = https://drive.google.com/drive/folders/<folder_id>
```

```sh
$ python main.py

No local dataset found. Downloading data from Google Drive...

Download completed successfully!
```

## Modules

| Module | Responsibility |
| :--- | :--- |
| `main.py` | Entry point: dataset discovery, Google Drive retrieval trigger, and the overall workflow. |
| `functions.py` | Computation and plotting helpers, plus the orchestration functions (`compute_dataset`, `analysis`, `comparison`, `process_folders`) that `main.py` calls. |
| `style.py` | `PlotStyle`, the styling parameters (figure size, font, line/marker style, grid) shared by every plot. |
| `standardmethod.py` | Core analysis pipeline: baseline reconstruction (shift/scale methods), negative/positive collector currents, NIEDF, and statistical variability, including the interactive checkbox validation. |
| `dataloader.py` | Discovery and validation of the raw `.dat` acquisition files, and construction of the voltage vector. |
| `configreader.py` | Parser for the `key=value` configuration file format used by `config.txt`. |
| `downloader.py` | `GoogleDriveDownloader`, used to fetch missing dataset folders from Google Drive via `gdown`. |

Every module, class, and function is documented following the [Doxygen](https://www.doxygen.nl/) convention (`## @brief` / `@param` / `@return` comment blocks). A browsable HTML reference can be generated from the included `Doxyfile`:

```sh
doxygen Doxyfile
```

The output is written to `html/index.html` (not versioned; regenerate it locally whenever needed).





