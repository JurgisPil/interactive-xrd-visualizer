import numpy as np
from pymatgen.core import Structure, Lattice
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import warnings

class XRDModel:
    def __init__(self, wavelength="CuKa"):
        self.wavelength = wavelength
        self.calculators = []
        self._structure_changed = True
        self._cached_patterns = []
        self.set_wavelength(wavelength)
        
        self.original_structure = None
        self.sg_symbol = None
        self.equivalent_indices = None
        self.asym_species = None
        self.asym_coords = None
        
        # Instrumental Broadening parameters (TCH pseudo-Voigt)
        self.default_inst_params = {'U': 5.0, 'V': -5.0, 'W': 5.0, 'X': 1.0, 'Y': 1.0}
        self.U = self.default_inst_params['U']
        self.V = self.default_inst_params['V']
        self.W = self.default_inst_params['W']
        self.X = self.default_inst_params['X']
        self.Y = self.default_inst_params['Y']
        
        # Sample parameters
        self.crystallite_size_nm = 1000.0  # Large value = no broadening
        
        # 2Theta range
        self.two_theta_min = 10.0
        self.two_theta_max = 90.0
        self.two_theta_step = 0.02
        
        # Load default
        self.load_default()
        
    def set_wavelength(self, wavelength):
        try:
            # If it's a float string, convert it, otherwise pass the string (e.g. 'CuKa')
            try:
                wav = float(wavelength)
            except ValueError:
                wav = wavelength
                
            self.wavelength = wav
            self.calculators = []
            self._structure_changed = True
            
            # Check for doublet
            if isinstance(wav, str) and not wav.endswith("1") and not wav.endswith("2"):
                try:
                    calc1 = XRDCalculator(wavelength=wav + "1")
                    calc2 = XRDCalculator(wavelength=wav + "2")
                    # Ka1 weight 1.0, Ka2 weight 0.5
                    self.calculators = [(calc1, 1.0), (calc2, 0.5)]
                except Exception:
                    self.calculators = [(XRDCalculator(wavelength=wav), 1.0)]
            else:
                self.calculators = [(XRDCalculator(wavelength=wav), 1.0)]
                
            return True
        except Exception:
            return False
        
    def load_default(self):
        # Default to Silicon
        lattice = Lattice.cubic(5.431)
        self.original_structure = Structure.from_spacegroup("Fd-3m", lattice, ["Si"], [[0, 0, 0]])
        self._analyze_symmetry()
        self._structure_changed = True
        
    def load_cif(self, filepath):
        try:
            self.original_structure = Structure.from_file(filepath)
            self._analyze_symmetry()
            self._structure_changed = True
            return True, "Loaded successfully"
        except Exception as e:
            return False, str(e)
            
    def reset_lattice(self):
        if hasattr(self, 'original_lattice'):
            self.lattice = self.original_lattice
            self._structure_changed = True
            
    def reset_sites(self):
        if hasattr(self, 'original_asym_species'):
            import copy
            self.asym_species = copy.deepcopy(self.original_asym_species)
            self.asym_coords = copy.deepcopy(self.original_asym_coords)
            self._structure_changed = True
            
    def load_inst_params(self, filepath):
        try:
            import re
            with open(filepath, 'r') as f:
                content = f.read()
                
            for param in ['U', 'V', 'W', 'X', 'Y']:
                # Matches "U 0.005", "U=0.005", "INS 1 U  0.005", "U: 4.578"
                match = re.search(fr'\b{param}\s*[:=]?\s*([+-]?\d*\.\d+(?:[eE][+-]?\d+)?|\d+)', content)
                if match:
                    val = float(match.group(1))
                    setattr(self, param, val)
                    self.default_inst_params[param] = val
            return True, "Instrument parameters loaded"
        except Exception as e:
            return False, str(e)
            
    def reset_inst_params(self):
        for param in ['U', 'V', 'W', 'X', 'Y']:
            setattr(self, param, self.default_inst_params[param])
            
    def _analyze_symmetry(self):
        sga = SpacegroupAnalyzer(self.original_structure)
        sym_struct = sga.get_symmetrized_structure()
        self.sg_symbol = sga.get_space_group_symbol()
        
        # Extract asymmetric unit sites
        self.lattice = sym_struct.lattice
        self.original_lattice = self.lattice
        
        self.asym_species = []
        self.asym_coords = []
        for site in sym_struct.equivalent_sites:
            rep = site[0]
            self.asym_species.append(rep.species.as_dict())
            self.asym_coords.append(rep.frac_coords)
            
        import copy
        self.original_asym_species = copy.deepcopy(self.asym_species)
        self.original_asym_coords = copy.deepcopy(self.asym_coords)
            
        self.crystal_system = sga.get_crystal_system()

    def get_lattice_params(self):
        return {
            'a': self.lattice.a,
            'b': self.lattice.b,
            'c': self.lattice.c,
            'alpha': self.lattice.alpha,
            'beta': self.lattice.beta,
            'gamma': self.lattice.gamma,
            'system': self.crystal_system
        }
        
    def get_sites(self):
        sites = []
        for i, spec in enumerate(self.asym_species):
            # For simplicity, take the first element in the species if it's mixed
            # Pymatgen species is a Composition dict
            el = list(spec.keys())[0]
            occ = spec[el]
            el_str = el.symbol if hasattr(el, 'symbol') else str(el)
            sites.append({
                'index': i,
                'element': el_str,
                'occupancy': occ,
                'coords': self.asym_coords[i].tolist() if hasattr(self.asym_coords[i], 'tolist') else self.asym_coords[i]
            })
        return sites

    def update_structure(self, lattice_params, sites_data):
        # Build new lattice based on crystal system constraints
        a = lattice_params.get('a', self.lattice.a)
        b = lattice_params.get('b', self.lattice.b)
        c = lattice_params.get('c', self.lattice.c)
        alpha = lattice_params.get('alpha', self.lattice.alpha)
        beta = lattice_params.get('beta', self.lattice.beta)
        gamma = lattice_params.get('gamma', self.lattice.gamma)
        
        sys = self.crystal_system
        if sys == "cubic":
            b = c = a
            alpha = beta = gamma = 90
        elif sys == "tetragonal":
            b = a
            alpha = beta = gamma = 90
        elif sys == "orthorhombic":
            alpha = beta = gamma = 90
        elif sys == "hexagonal" or sys == "trigonal":
            b = a
            alpha = beta = 90
            gamma = 120
        elif sys == "monoclinic":
            alpha = gamma = 90
        
        new_lattice = Lattice.from_parameters(a, b, c, alpha, beta, gamma)
        self.lattice = new_lattice
        
        # Update species and coords
        new_species = []
        new_coords = []
        for site in sites_data:
            new_species.append({site['element']: site['occupancy']})
            new_coords.append(site['coords'])
        self.asym_species = new_species
        self.asym_coords = new_coords
        self._structure_changed = True
            
    def calculate_pattern(self):
        # Reconstruct structure from asymmetric unit and spacegroup if changed
        if getattr(self, '_structure_changed', True):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    structure = Structure.from_spacegroup(
                        self.sg_symbol, 
                        self.lattice, 
                        self.asym_species, 
                        self.asym_coords
                    )
            except Exception:
                # Fallback if symmetry breaks
                structure = self.original_structure
                
            self._cached_patterns = []
            calc_max = self.two_theta_max + 5.0
            for calc, weight in self.calculators:
                try:
                    pattern = calc.get_pattern(structure, two_theta_range=(0.0, calc_max))
                    self._cached_patterns.append((calc, weight, pattern))
                except ValueError:
                    continue
            self._structure_changed = False
            self._cached_max = calc_max
            
        # Calculate continuous profile
        x = np.arange(self.two_theta_min, self.two_theta_max, self.two_theta_step)
        y = np.zeros_like(x)
        
        # TCH pseudo-Voigt profile
        pi = np.pi
        sqrt_ln2 = np.sqrt(np.log(2))
        
        for calc, weight, pattern in self._cached_patterns:
            
            # Calculate size broadening contribution to X
            lambda_A = calc.wavelength
            lambda_nm = lambda_A / 10.0
            X_size = (180.0 / pi) * (0.94 * lambda_nm / self.crystallite_size_nm)
            X_eff = self.X + X_size
            
            for two_theta_0, intensity in zip(pattern.x, pattern.y):
                if intensity < 0.1: continue
                
                theta = np.radians(two_theta_0 / 2.0)
                tan_theta = np.tan(theta)
                
                # Instrumental broadening (GSAS uses centi-degrees)
                U_deg2 = self.U / 10000.0
                V_deg2 = self.V / 10000.0
                W_deg2 = self.W / 10000.0
                X_deg = self.X / 100.0
                Y_deg = self.Y / 100.0
                
                Gamma_G_sq = max(1e-8, U_deg2 * tan_theta**2 + V_deg2 * tan_theta + W_deg2)
                Gamma_G = np.sqrt(Gamma_G_sq)
                
                Gamma_L_inst = X_deg * tan_theta + Y_deg / np.cos(theta)
                Gamma_L = max(1e-6, Gamma_L_inst + X_size / np.cos(theta))
                
                # TCH Approximation
                Gamma_G5 = Gamma_G**5
                Gamma_L5 = Gamma_L**5
                Gamma = (Gamma_G5 + 2.69269 * Gamma_G**4 * Gamma_L + 2.42843 * Gamma_G**3 * Gamma_L**2 + 
                         4.47163 * Gamma_G**2 * Gamma_L**3 + 0.07842 * Gamma_G * Gamma_L**4 + Gamma_L5)**0.2
                
                if Gamma < 1e-6:
                    Gamma = 1e-6
                    
                phi = Gamma_L / Gamma
                eta = 1.36603 * phi - 0.47719 * phi**2 + 0.11116 * phi**3
                
                # Localized peak profile calculation (Slice optimization)
                half_width_idx = int((20.0 * Gamma) / self.two_theta_step)
                idx_center = int((two_theta_0 - self.two_theta_min) / self.two_theta_step)
                idx_start = max(0, idx_center - half_width_idx)
                idx_end = min(len(x), idx_center + half_width_idx + 1)
                
                if idx_start >= len(x) or idx_end <= 0:
                    continue  # Peak is entirely outside the plotting window
                
                delta_2theta = x[idx_start:idx_end] - two_theta_0
                
                # Lorentzian component
                L = (2.0 / (pi * Gamma)) / (1.0 + (2.0 * delta_2theta / Gamma)**2)
                
                # Gaussian component
                G = (2.0 * sqrt_ln2 / (Gamma * np.sqrt(pi))) * np.exp(-4.0 * np.log(2) * (delta_2theta / Gamma)**2)
                
                # Pseudo-Voigt
                V = eta * L + (1.0 - eta) * G
                
                y[idx_start:idx_end] += weight * intensity * V
            
        # Normalize to 100 for max peak
        if len(y) > 0 and np.max(y) > 0:
            y = y / np.max(y) * 100.0
            
        return x, y

