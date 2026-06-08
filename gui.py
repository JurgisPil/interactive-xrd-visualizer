from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QDoubleSpinBox, QFileDialog, QScrollArea, 
                             QGroupBox, QFormLayout, QComboBox, QLineEdit,
                             QTableWidget, QTableWidgetItem, QHeaderView, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
import pyqtgraph as pg
from xrd_model import XRDModel

class CalcThread(QThread):
    result_ready = pyqtSignal(object, object, object)
    
    def __init__(self, model):
        super().__init__()
        self.model = model
        
    def run(self):
        try:
            x, y, peaks = self.model.calculate_pattern()
            self.result_ready.emit(x, y, peaks)
        except Exception as e:
            print(f"Error calculating pattern in thread: {e}")

class XRDGui(QWidget):
    def __init__(self):
        super().__init__()
        self.model = XRDModel()
        
        self.calc_thread = CalcThread(self.model)
        self.calc_thread.result_ready.connect(self.on_calc_finished)
        self._calc_queued = False
        
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(16)  # ~60 FPS
        self.refresh_timer.timeout.connect(self._do_refresh_plot)
        
        self.init_ui()
        self.populate_from_model()
        self._do_refresh_plot()
        
    def init_ui(self):
        self.setWindowTitle("Interactive XRD Visualizer")
        self.resize(1200, 800)
        
        main_layout = QHBoxLayout(self)
        
        # Plot area
        self.plot_widget = pg.PlotWidget(title="XRD Pattern")
        self.plot_widget.setLabel('left', 'Intensity (a.u.)')
        self.plot_widget.setLabel('bottom', '2 Theta (degrees)')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen('cyan', width=2), antialias=False)
        self.sticks = self.plot_widget.plot(x=[], y=[], pen=pg.mkPen('r', width=1))
        self.text_items = []
        
        main_layout.addWidget(self.plot_widget, stretch=7)
        
        # Control panel area
        control_splitter = QSplitter(Qt.Orientation.Vertical)
        
        upper_scroll = QScrollArea()
        upper_scroll.setWidgetResizable(True)
        upper_widget = QWidget()
        self.control_layout = QVBoxLayout(upper_widget)
        
        # File section (Top row)
        file_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load CIF")
        self.load_btn.clicked.connect(self.load_cif)
        file_layout.addWidget(self.load_btn)
        self.control_layout.addLayout(file_layout)
        
        # Broadening params (Moved to top)
        broad_group = QGroupBox("Instrumental Profile (GSAS-II TCH)")
        broad_layout = QFormLayout()
        
        inst_btn_layout = QHBoxLayout()
        self.load_inst_btn = QPushButton("Load PRM")
        self.load_inst_btn.clicked.connect(self.load_inst_params)
        inst_btn_layout.addWidget(self.load_inst_btn)
        self.reset_inst_btn = QPushButton("Reset PRM")
        self.reset_inst_btn.clicked.connect(self.reset_inst_params)
        inst_btn_layout.addWidget(self.reset_inst_btn)
        broad_layout.addRow(inst_btn_layout)
        
        self.broad_spins = {}
        for p in ['U', 'V', 'W', 'X', 'Y']:
            spin = QDoubleSpinBox()
            spin.setRange(-1000.0, 1000.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.1)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self.on_param_changed)
            self.broad_spins[p] = spin
            broad_layout.addRow(QLabel(p), spin)
        broad_group.setLayout(broad_layout)
        self.control_layout.addWidget(broad_group)

        # Columns layout for Lattice and Pattern/Sample
        cols_layout = QHBoxLayout()
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        cols_layout.addLayout(col1)
        cols_layout.addLayout(col2)
        
        # Lattice section (Col 1)
        self.lattice_group = QGroupBox("Lattice Parameters")
        lattice_layout = QVBoxLayout()
        
        self.reset_lattice_btn = QPushButton("Reset Lattice")
        self.reset_lattice_btn.clicked.connect(self.reset_lattice)
        lattice_layout.addWidget(self.reset_lattice_btn)
        
        self.lattice_form = QFormLayout()
        self.lattice_spins = {}
        for p in ['a', 'b', 'c', 'alpha', 'beta', 'gamma']:
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 180.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.01)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self.on_param_changed)
            self.lattice_spins[p] = spin
            self.lattice_form.addRow(QLabel(p), spin)
        lattice_layout.addLayout(self.lattice_form)
        self.lattice_group.setLayout(lattice_layout)
        col1.addWidget(self.lattice_group)
        col1.addStretch()
        
        # Settings section (Col 2)
        settings_group = QGroupBox("Pattern Settings")
        settings_layout = QFormLayout()
        
        self.wav_combo = QComboBox()
        self.wav_combo.setEditable(True)
        self.wav_combo.addItems(["CuKa", "CuKa1", "CuKa2", "MoKa", "AgKa", "FeKa", "CoKa"])
        self.wav_combo.currentTextChanged.connect(self.on_wav_changed)
        settings_layout.addRow("Wavelength:", self.wav_combo)
        
        self.tth_min_spin = QDoubleSpinBox()
        self.tth_min_spin.setRange(0.0, 180.0)
        self.tth_min_spin.setValue(10.0)
        self.tth_min_spin.valueChanged.connect(self.on_param_changed)
        settings_layout.addRow("2-Theta Min:", self.tth_min_spin)
        
        self.tth_max_spin = QDoubleSpinBox()
        self.tth_max_spin.setRange(0.0, 180.0)
        self.tth_max_spin.setValue(90.0)
        self.tth_max_spin.valueChanged.connect(self.on_param_changed)
        settings_layout.addRow("2-Theta Max:", self.tth_max_spin)
        
        self.aa_btn = QPushButton("Antialiasing: OFF")
        self.aa_btn.setCheckable(True)
        self.aa_btn.clicked.connect(self.toggle_aa)
        settings_layout.addRow("Graphics:", self.aa_btn)
        
        self.show_indices_btn = QPushButton("Miller Indices: OFF")
        self.show_indices_btn.setCheckable(True)
        self.show_indices_btn.clicked.connect(self.toggle_indices)
        settings_layout.addRow("Sticks:", self.show_indices_btn)
        
        settings_group.setLayout(settings_layout)
        col2.addWidget(settings_group)
        
        # Sample Params section (Col 2)
        sample_group = QGroupBox("Sample Parameters")
        sample_layout = QFormLayout()
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(1.0, 10000.0)
        self.size_spin.setDecimals(1)
        self.size_spin.setSingleStep(5.0)
        self.size_spin.setValue(1000.0)
        self.size_spin.setKeyboardTracking(False)
        self.size_spin.valueChanged.connect(self.on_param_changed)
        sample_layout.addRow("Size (nm):", self.size_spin)
        sample_group.setLayout(sample_layout)
        col2.addWidget(sample_group)
        col2.addStretch()
        
        self.control_layout.addLayout(cols_layout)

        # Sites section (Bottom)
        self.sites_group = QGroupBox("Sites (Asymmetric Unit)")
        self.sites_layout = QVBoxLayout()
        
        site_btn_layout = QHBoxLayout()
        self.add_site_btn = QPushButton("Add Site")
        self.add_site_btn.clicked.connect(self.add_site)
        site_btn_layout.addWidget(self.add_site_btn)
        
        self.reset_sites_btn = QPushButton("Reset Sites")
        self.reset_sites_btn.clicked.connect(self.reset_sites)
        site_btn_layout.addWidget(self.reset_sites_btn)
        
        self.sites_layout.addLayout(site_btn_layout)
        
        self.sites_table = QTableWidget()
        self.sites_table.setColumnCount(6)
        self.sites_table.setHorizontalHeaderLabels(["El", "Occ", "X", "Y", "Z", "Del"])
        self.sites_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sites_layout.addWidget(self.sites_table)
        
        self.sites_group.setLayout(self.sites_layout)
        
        upper_scroll.setWidget(upper_widget)
        control_splitter.addWidget(upper_scroll)
        control_splitter.addWidget(self.sites_group)
        control_splitter.setSizes([300, 500])
        
        main_layout.addWidget(control_splitter, stretch=3)
        
    def load_cif(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open CIF", "", "CIF Files (*.cif)")
        if filepath:
            success, msg = self.model.load_cif(filepath)
            if success:
                self.populate_from_model()
                self.refresh_plot()
            else:
                print(f"Error loading CIF: {msg}")
                
    def reset_lattice(self):
        self.model.reset_lattice()
        self.populate_from_model()
        self.refresh_plot()
        
    def reset_sites(self):
        self.model.reset_sites()
        self.populate_from_model()
        self.refresh_plot()
                
    def load_inst_params(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Parameter File", "", "Parameter Files (*.prm *.instprm *.txt);;All Files (*)")
        if filepath:
            success, msg = self.model.load_inst_params(filepath)
            if success:
                self.populate_from_model()
                self.refresh_plot()
            else:
                print(f"Error loading parameters: {msg}")
                
    def reset_inst_params(self):
        self.model.reset_inst_params()
        self.populate_from_model()
        self.refresh_plot()
                
    def populate_from_model(self):
        # Update broadening
        self.broad_spins['U'].blockSignals(True)
        self.broad_spins['V'].blockSignals(True)
        self.broad_spins['W'].blockSignals(True)
        self.broad_spins['X'].blockSignals(True)
        self.broad_spins['Y'].blockSignals(True)
        self.broad_spins['U'].setValue(self.model.U)
        self.broad_spins['V'].setValue(self.model.V)
        self.broad_spins['W'].setValue(self.model.W)
        self.broad_spins['X'].setValue(self.model.X)
        self.broad_spins['Y'].setValue(self.model.Y)
        self.broad_spins['U'].blockSignals(False)
        self.broad_spins['V'].blockSignals(False)
        self.broad_spins['W'].blockSignals(False)
        self.broad_spins['X'].blockSignals(False)
        self.broad_spins['Y'].blockSignals(False)
        
        self.update_lattice_spins()
        self.update_sites_ui()
        
    def update_lattice_spins(self):
        params = self.model.get_lattice_params()
        sys = params['system']
        self.lattice_group.setTitle(f"Lattice Parameters ({sys})")
        
        # Block signals to avoid infinite loops during programmatic updates
        for spin in self.lattice_spins.values():
            spin.blockSignals(True)
            
        for p in ['a', 'b', 'c', 'alpha', 'beta', 'gamma']:
            self.lattice_spins[p].setValue(params[p])
            self.lattice_spins[p].setEnabled(True)
            
        # Apply symmetry constraints to UI (disable fields determined by symmetry)
        if sys == "cubic":
            self.lattice_spins['b'].setEnabled(False)
            self.lattice_spins['c'].setEnabled(False)
            self.lattice_spins['alpha'].setEnabled(False)
            self.lattice_spins['beta'].setEnabled(False)
            self.lattice_spins['gamma'].setEnabled(False)
        elif sys == "tetragonal":
            self.lattice_spins['b'].setEnabled(False)
            self.lattice_spins['alpha'].setEnabled(False)
            self.lattice_spins['beta'].setEnabled(False)
            self.lattice_spins['gamma'].setEnabled(False)
        elif sys == "orthorhombic":
            self.lattice_spins['alpha'].setEnabled(False)
            self.lattice_spins['beta'].setEnabled(False)
            self.lattice_spins['gamma'].setEnabled(False)
        elif sys == "hexagonal" or sys == "trigonal":
            self.lattice_spins['b'].setEnabled(False)
            self.lattice_spins['alpha'].setEnabled(False)
            self.lattice_spins['beta'].setEnabled(False)
            self.lattice_spins['gamma'].setEnabled(False) # Gamma is fixed to 120
        elif sys == "monoclinic":
            self.lattice_spins['alpha'].setEnabled(False)
            self.lattice_spins['gamma'].setEnabled(False)
            
        for spin in self.lattice_spins.values():
            spin.blockSignals(False)
            
    def update_sites_ui(self):
        self.sites_table.setRowCount(0)
        self.site_inputs = []
        sites = self.model.get_sites()
        
        for site in sites:
            self.add_table_row(site['element'], site['occupancy'], site['coords'])
            
    def add_table_row(self, el, occ, coords):
        row = self.sites_table.rowCount()
        self.sites_table.insertRow(row)
        
        el_input = QLineEdit(el)
        el_input.editingFinished.connect(self.on_param_changed)
        self.sites_table.setCellWidget(row, 0, el_input)
        
        occ_spin = QDoubleSpinBox()
        occ_spin.setRange(0.0, 1.0)
        occ_spin.setSingleStep(0.05)
        occ_spin.setValue(occ)
        occ_spin.setKeyboardTracking(False)
        occ_spin.valueChanged.connect(self.on_param_changed)
        self.sites_table.setCellWidget(row, 1, occ_spin)
        
        coord_spins = []
        for i, val in enumerate(coords):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.01)
            spin.setValue(val)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self.on_param_changed)
            self.sites_table.setCellWidget(row, 2 + i, spin)
            coord_spins.append(spin)
            
        rm_btn = QPushButton("Del")
        rm_btn.clicked.connect(lambda _, btn=rm_btn: self.remove_site(btn))
        self.sites_table.setCellWidget(row, 5, rm_btn)
        
        self.site_inputs.append({
            'element': el_input,
            'occupancy': occ_spin,
            'coords': coord_spins
        })
        
    def add_site(self):
        self.add_table_row("C", 1.0, [0.0, 0.0, 0.0])
        self.on_param_changed()
        
    def remove_site(self, item_widget):
        for i in range(self.sites_table.rowCount()):
            if self.sites_table.cellWidget(i, 5) == item_widget:
                self.sites_table.removeRow(i)
                self.site_inputs.pop(i)
                self.on_param_changed()
                break
            
    def read_params(self):
        # Read lattice
        lattice_params = {p: self.lattice_spins[p].value() for p in ['a', 'b', 'c', 'alpha', 'beta', 'gamma']}
        
        # Read sites
        sites_data = []
        for inputs in self.site_inputs:
            sites_data.append({
                'element': inputs['element'].text(),
                'occupancy': inputs['occupancy'].value(),
                'coords': [s.value() for s in inputs['coords']]
            })
            
        # Read 2Theta Range
        if self.model.two_theta_max != self.tth_max_spin.value():
            if self.tth_max_spin.value() > getattr(self.model, '_cached_max', 0):
                self.model._structure_changed = True
                
        self.model.two_theta_min = self.tth_min_spin.value()
        self.model.two_theta_max = self.tth_max_spin.value()
            
        # Read broadening & size
        self.model.U = self.broad_spins['U'].value()
        self.model.V = self.broad_spins['V'].value()
        self.model.W = self.broad_spins['W'].value()
        self.model.X = self.broad_spins['X'].value()
        self.model.Y = self.broad_spins['Y'].value()
        self.model.crystallite_size_nm = self.size_spin.value()
        
        return lattice_params, sites_data

    def on_wav_changed(self, wav_text):
        if self.model.set_wavelength(wav_text):
            self.refresh_plot()

    def toggle_indices(self, checked):
        if checked:
            self.show_indices_btn.setText("Miller Indices: ON")
        else:
            self.show_indices_btn.setText("Miller Indices: OFF")
        self.refresh_plot()

    def toggle_aa(self, checked):
        if checked:
            self.aa_btn.setText("Antialiasing: ON")
            is_aa = True
        else:
            self.aa_btn.setText("Antialiasing: OFF")
            is_aa = False
            
        # Recreate the curve to apply antialiasing setting
        self.plot_widget.clear()
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen('cyan', width=2), antialias=is_aa)
        self.sticks = self.plot_widget.plot(x=[], y=[], pen=pg.mkPen('r', width=1))
        self.text_items.clear()
        self.refresh_plot()

    def on_param_changed(self):
        lattice_params, sites_data = self.read_params()
        self.model.update_structure(lattice_params, sites_data)
        
        # The crystal system constraints in update_structure might have changed dependent parameters
        # e.g., if we changed 'a' in a cubic system, 'b' and 'c' are updated in the model
        # So we should update the UI spins silently to reflect the new state.
        self.update_lattice_spins()
        
        self.refresh_plot()

    def refresh_plot(self):
        # Debounce the plot refresh to keep UI responsive
        self.refresh_timer.start()
        
    def _do_refresh_plot(self):
        if not self.calc_thread.isRunning():
            self.calc_thread.start()
        else:
            self._calc_queued = True
            
    def on_calc_finished(self, x, y, peaks):
        self.plot_curve.setData(x, y)
        
        if self.show_indices_btn.isChecked():
            valid_peaks = [(pos, intensity, txt) for pos, intensity, txt in peaks 
                           if self.model.two_theta_min <= pos <= self.model.two_theta_max]
                           
            sx = []
            sy = []
            max_int = 1.0
            
            for p in valid_peaks:
                h = p[1] * 0.8
                sx.extend([p[0], p[0], float('nan')])
                sy.extend([0, h, float('nan')])
                if h > max_int: max_int = h
                
            self.sticks.setData(x=sx, y=sy)
            
            # Remove old text
            for t in self.text_items:
                self.plot_widget.removeItem(t)
            self.text_items.clear()
            
            # Add new text for significant peaks (e.g. > 2% of max to avoid clutter)
            for pos, intensity, txt in valid_peaks:
                scaled_intensity = intensity * 0.8
                if txt and scaled_intensity > 0.02 * max_int:
                    ti = pg.TextItem(text=txt, color='y', angle=-90, anchor=(0, 0.5))
                    ti.setPos(pos, scaled_intensity)
                    self.plot_widget.addItem(ti)
                    self.text_items.append(ti)
        else:
            self.sticks.setData(x=[], y=[])
            for t in self.text_items:
                self.plot_widget.removeItem(t)
            self.text_items.clear()
            
        if self._calc_queued:
            self._calc_queued = False
            self.calc_thread.start()

