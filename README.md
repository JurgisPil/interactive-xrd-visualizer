# Interactive XRD Visualizer

A fast, interactive Python application for visualizing X-Ray Diffraction (XRD) patterns in real-time. Built with PyQt6 and pyqtgraph for a smooth 60 FPS graphical interface, and powered by `pymatgen` for robust crystallography calculations.

## Features
- **Real-Time Interactive Updates**: Drag sliders or scroll your mouse wheel over values to instantly see changes in the XRD pattern.
- **Full Symmetry Support**: Edit the fractional coordinates of atoms in the asymmetric unit, and the backend automatically generates the full unit cell using crystallographic space group operations.
- **Instrumental Broadening**: Supports loading and adjusting GSAS-II instrumental parameters (TCH pseudo-Voigt `U, V, W, X, Y`).
- **Crystallite Size Broadening**: Simulates peak broadening based on crystallite size (Scherrer approximation).
- **K-Alpha Doublet Splitting**: Accurately simulates K-alpha 1 & 2 doublet splitting for standard laboratory X-ray tubes.
- **Multithreaded Architecture**: Heavy crystallography calculations are decoupled from the UI thread to guarantee a responsive application without freezing.

## Installation

1. Clone or download this repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main application script:
```bash
python main.py
```

## How to Use
- **Load CIF**: Click the top left button to load a standard `.cif` structure file.
- **Load PRM**: In the Instrumental Profile box, load a GSAS or GSAS-II `.prm` or `.instprm` file to accurately set the baseline peak shape.
- **Scroll Values**: Click inside any number box (like `2-Theta Max` or the `X` coordinate of an atom) and use your mouse scroll wheel to dial the value up and down, watching the plot respond in real-time.
- **Antialiasing**: Toggle antialiasing in the Pattern Settings for a smoother visual trace.
