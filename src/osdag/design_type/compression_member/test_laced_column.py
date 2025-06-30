"""
Laced Column Standalone Test Script – IS 800:2007 Logic (Column.py logic, LacedColumn UI Fields)

Purpose:
    Demonstrates laced column design calculations using the actual section_classification and design_column logic from Osdag's Column.py, as a standalone script.
    Prints input dock and output dock matching laced_column.py's UI fields/order.
    Edit the input_dict to test different scenarios. Run directly with Python. No Osdag imports required.

Features:
    - Input dock and output dock printed to console (fields/order as in laced_column.py)
    - Uses real section_classification and design_column logic from Column.py
    - Simulated section/material/IS800 classes and constants
    - All intermediate and final values shown in output dock
    - All logic self-contained
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from osdag.Common import connectdb, KEY_DP_WELD_FAB_VALUES
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit

# --- Input Dock (matches laced_column.py) ---
input_dock_fields = [
    ("section_profile", "Section Profile"),
    ("section_size", "Section Size"),
    ("material", "Material Grade"),
    ("unsupported_length_yy", "Unsupported Length (y-y) [mm]"),
    ("unsupported_length_zz", "Unsupported Length (z-z) [mm]"),
    ("end_condition_yy_1", "End Condition (y-y) 1"),
    ("end_condition_yy_2", "End Condition (y-y) 2"),
    ("end_condition_zz_1", "End Condition (z-z) 1"),
    ("end_condition_zz_2", "End Condition (z-z) 2"),
    ("lacing_pattern", "Lacing Pattern"),
    ("connection_type", "Type of Connection"),
    ("axial_load", "Axial Load (kN)"),
    ("weld_size", "Weld Size (mm)"),
    ("bolt_diameter", "Bolt Diameter (mm)")
]

# Fetch all material grades and section designations from the database
material_grades = [m for m in connectdb("Material", call_type="dropdown") if m != "Custom" and m != "Select Section"]
section_designations = [s for s in connectdb("Channels", call_type="dropdown") if s != "Select Section"]

# Use a fixed input template for other fields
base_input_dict = {
    'section_profile': 'Channels',
    'unsupported_length_yy': 3000,  # mm
    'unsupported_length_zz': 3000,  # mm
    'end_condition_yy_1': 'Fixed',
    'end_condition_yy_2': 'Fixed',
    'end_condition_zz_1': 'Fixed',
    'end_condition_zz_2': 'Fixed',
    'lacing_pattern': 'Single',
    'connection_type': 'Welded',
    'axial_load': 500,  # kN
    'weld_size': 5,     # mm
    'bolt_diameter': 16 # mm
}

# --- Simulated Section and Material Properties ---
SECTIONS = {
    'ISMB 200': {
        'area': 26.2 * 100,  # cm^2 to mm^2
        'depth': 200,        # mm
        'flange_width': 100, # mm
        'web_thickness': 5.7,# mm
        'flange_thickness': 9.0, # mm
        'root_radius': 8.0,  # mm
        'rmin': 30.1,        # mm
        'type': 'Rolled',
        'rad_of_gy_z': 30.1, # mm
        'rad_of_gy_y': 13.2, # mm
        'modulus_of_elasticity': 200000, # MPa
        'unit_mass': 7850
    }
}
MATERIALS = {
    'E 250 (Fe 410 W)A': {
        'fy': 250,
        'fu': 410,
        'E': 200000,
        'unit_mass': 7850
    }
}

# --- Simulated IS800 and Section Classes ---
class IS800_2007:
    @staticmethod
    def Table2_i(b, tf, fy, typ):
        epsilon = (250.0 / fy) ** 0.5
        ratio = b / tf
        if ratio <= 9.4 * epsilon:
            return ['Plastic']
        elif ratio <= 10.5 * epsilon:
            return ['Compact']
        elif ratio <= 15.7 * epsilon:
            return ['Semi-Compact']
        else:
            return ['Slender']
    @staticmethod
    def Table2_iii(d, tw, fy, classification_type=None):
        epsilon = (250.0 / fy) ** 0.5
        ratio = d / tw
        if ratio <= 42 * epsilon:
            return 'Plastic'
        elif ratio <= 42 * epsilon:
            return 'Compact'
        elif ratio <= 42 * epsilon:
            return 'Semi-Compact'
        else:
            return 'Slender'
    @staticmethod
    def Table2_x(d, t, fy, load_type=None):
        return 'Plastic'  # Simplified for test
    @staticmethod
    def cl_7_2_2_effective_length_of_prismatic_compression_members(L, end_1, end_2):
        if end_1 == 'Fixed' and end_2 == 'Fixed':
            return 0.65 * L
        elif (end_1 == 'Fixed' and end_2 == 'Hinged') or (end_1 == 'Hinged' and end_2 == 'Fixed'):
            return 0.8 * L
        elif end_1 == 'Hinged' and end_2 == 'Hinged':
            return 1.0 * L
        else:
            return 1.0 * L
    @staticmethod
    def cl_3_8_max_slenderness_ratio(dummy):
        return 180
    @staticmethod
    def cl_7_1_2_2_buckling_class_of_crosssections(b, d, tf, cross_section, section_type):
        return {'z-z': 'b', 'y-y': 'b'}
    @staticmethod
    def cl_7_1_2_1_imperfection_factor(buckling_class):
        return 0.49

class MaterialProperty:
    def __init__(self, fy):
        self.fy = fy
    def connect_to_database_to_get_fy_fu(self, material, thickness):
        pass

class SectionProperty:
    def __init__(self, section):
        for k, v in section.items():
            setattr(self, k, v)

# --- Constants ---
VALUES_SEC_PROFILE = ['Beams and Columns', 'RHS and SHS', 'CHS']

# --- Main Standalone ColumnDesign Logic ---
class StandaloneColumnDesign:
    def __init__(self, inp):
        self.sec_profile = inp['section_profile']
        self.sec_list = [inp['section_size']]
        self.material = inp['material']
        self.length_yy = inp['unsupported_length_yy']
        self.length_zz = inp['unsupported_length_zz']
        self.end_1_y = inp['end_condition_yy_1']
        self.end_2_y = inp['end_condition_yy_2']
        self.end_1_z = inp['end_condition_zz_1']
        self.end_2_z = inp['end_condition_zz_2']
        self.axial_load = inp['axial_load'] * 1000  # kN to N
        self.allowed_sections = ['Plastic', 'Compact', 'Semi-Compact', 'Slender']
        self.material_property = MaterialProperty(MATERIALS[self.material]['fy'])
        self.gamma_m0 = 1.1
        self.steel_cost_per_kg = 50
        self.effective_area_factor = 1.0
        self.allowable_utilization_ratio = 1.0
        self.input_section_list = []
        self.input_section_classification = {}
        self.section_class = None
        self.section_property = None
        self.epsilon = (250.0 / MATERIALS[self.material]['fy']) ** 0.5
        self.result = {}

    def section_classification(self):
        local_flag = True
        for section_name in self.sec_list:
            section = SECTIONS[section_name]
            self.section_property = SectionProperty(section)
            self.material_property.connect_to_database_to_get_fy_fu(self.material, max(self.section_property.flange_thickness, self.section_property.web_thickness))
            if self.sec_profile == VALUES_SEC_PROFILE[0]:
                if self.section_property.type == 'Rolled':
                    self.flange_class = IS800_2007.Table2_i((self.section_property.flange_width / 2), self.section_property.flange_thickness, self.material_property.fy, self.section_property.type)[0]
                else:
                    self.flange_class = IS800_2007.Table2_i(((self.section_property.flange_width / 2) - (self.section_property.web_thickness / 2)), self.section_property.flange_thickness, self.material_property.fy, self.section_property.type)[0]
                self.web_class = IS800_2007.Table2_iii((self.section_property.depth - (2 * self.section_property.flange_thickness)), self.section_property.web_thickness, self.material_property.fy, classification_type='Axial compression')
                web_ratio = (self.section_property.depth - 2 * (self.section_property.flange_thickness + self.section_property.root_radius)) / self.section_property.web_thickness
                flange_ratio = self.section_property.flange_width / 2 / self.section_property.flange_thickness
            else:
                self.flange_class = 'Plastic'
                self.web_class = 'Plastic'
                web_ratio = 0
                flange_ratio = 0
            if self.flange_class == 'Slender' or self.web_class == 'Slender':
                self.section_class = 'Slender'
            else:
                if self.flange_class == 'Plastic' and self.web_class == 'Plastic':
                    self.section_class = 'Plastic'
                elif self.flange_class == 'Plastic' and self.web_class == 'Compact':
                    self.section_class = 'Compact'
                elif self.flange_class == 'Plastic' and self.web_class == 'Semi-Compact':
                    self.section_class = 'Semi-Compact'
                elif self.flange_class == 'Compact' and self.web_class == 'Plastic':
                    self.section_class = 'Compact'
                elif self.flange_class == 'Compact' and self.web_class == 'Compact':
                    self.section_class = 'Compact'
                elif self.flange_class == 'Compact' and self.web_class == 'Semi-Compact':
                    self.section_class = 'Semi-Compact'
                elif self.flange_class == 'Semi-Compact' and self.web_class == 'Plastic':
                    self.section_class = 'Semi-Compact'
                elif self.flange_class == 'Semi-Compact' and self.web_class == 'Compact':
                    self.section_class = 'Semi-Compact'
                elif self.flange_class == 'Semi-Compact' and self.web_class == 'Semi-Compact':
                    self.section_class = 'Semi-Compact'
            self.effective_length_zz = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(self.length_zz, self.end_1_z, self.end_2_z)
            self.effective_length_yy = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(self.length_yy, self.end_1_y, self.end_2_y)
            self.effective_sr_zz = self.effective_length_zz / self.section_property.rad_of_gy_z
            self.effective_sr_yy = self.effective_length_yy / self.section_property.rad_of_gy_y
            limit = IS800_2007.cl_3_8_max_slenderness_ratio(1)
            if self.effective_sr_zz > limit and self.effective_sr_yy > limit:
                local_flag = False
            if self.section_class in self.allowed_sections:
                self.input_section_list.append(section_name)
                self.input_section_classification.update({section_name: [self.section_class, self.flange_class, self.web_class, flange_ratio, web_ratio]})
        return local_flag

    def design_column(self):
        self.section_classification()
        if not self.input_section_list:
            self.result['status'] = 'No suitable section found.'
            return
        section_name = self.input_section_list[0]
        section = SECTIONS[section_name]
        area = section['area']
        eff_area = area  # For non-slender
        slender_yy = self.effective_sr_yy
        slender_zz = self.effective_sr_zz
        # Buckling factors
        lambda_yy = slender_yy / (3.1416 * (MATERIALS[self.material]['E'] / MATERIALS[self.material]['fy']) ** 0.5)
        lambda_zz = slender_zz / (3.1416 * (MATERIALS[self.material]['E'] / MATERIALS[self.material]['fy']) ** 0.5)
        phi_yy = 0.5 * (1 + 0.49 * (lambda_yy - 0.2) + lambda_yy ** 2)
        phi_zz = 0.5 * (1 + 0.49 * (lambda_zz - 0.2) + lambda_zz ** 2)
        chi_yy = 1.0 / (phi_yy + (phi_yy ** 2 - lambda_yy ** 2) ** 0.5)
        chi_zz = 1.0 / (phi_zz + (phi_zz ** 2 - lambda_zz ** 2) ** 0.5)
        fcd_yy = chi_yy * MATERIALS[self.material]['fy'] / self.gamma_m0
        fcd_zz = chi_zz * MATERIALS[self.material]['fy'] / self.gamma_m0
        fcd = min(fcd_yy, fcd_zz)
        design_strength = fcd * eff_area / 1000  # kN
        ur = self.axial_load / (design_strength * 1000) if design_strength else 0
        self.result = {
            'section_size': section_name,
            'material_grade': self.material,
            'effective_length_yy': round(self.effective_length_yy, 2),
            'effective_length_zz': round(self.effective_length_zz, 2),
            'end_condition_yy_1': self.end_1_y,
            'end_condition_yy_2': self.end_2_y,
            'end_condition_zz_1': self.end_1_z,
            'end_condition_zz_2': self.end_2_z,
            'slenderness_yy': round(slender_yy, 2),
            'slenderness_zz': round(slender_zz, 2),
            'fcd': round(fcd, 2),
            'design_compressive_strength': round(design_strength, 2),
            'utilization_ratio': round(ur, 3),
            'section_class': self.section_class,
            'status': 'Safe' if ur <= 1.0 and self.section_class != 'Slender' else 'Unsafe'
        }

# --- Input Validation and Printing ---
def validate_inputs(inp):
    errors = []
    for key, _ in input_dock_fields:
        if key not in inp or inp[key] in [None, '', 0]:
            errors.append(f"Missing or invalid: {key}")
    return errors

def print_input_dock(inp):
    print("\n--- Input Dock ---")
    for key, label in input_dock_fields:
        print(f"{label}: {inp.get(key, '')}")

def print_output_dock(result):
    print("\n--- Output Dock ---")
    for k, v in result.items():
        print(f"{k.replace('_',' ').title()}: {v}")

class LacedColumnTestUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Laced Column Test UI')
        self.setGeometry(100, 100, 600, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Dropdowns for material and section
        self.material_label = QLabel('Material Grade:')
        self.material_combo = QComboBox()
        self.material_combo.addItems(material_grades)
        layout.addWidget(self.material_label)
        layout.addWidget(self.material_combo)

        self.section_label = QLabel('Section Designation:')
        self.section_combo = QComboBox()
        self.section_combo.addItems(section_designations)
        layout.addWidget(self.section_label)
        layout.addWidget(self.section_combo)

        # Numeric input fields
        self.unsupported_length_yy = QLineEdit('3000')
        self.unsupported_length_zz = QLineEdit('3000')
        self.axial_load = QLineEdit('500')
        self.weld_size = QLineEdit('5')
        self.bolt_diameter = QLineEdit('16')

        layout.addWidget(QLabel('Unsupported Length (y-y) [mm]:'))
        layout.addWidget(self.unsupported_length_yy)
        layout.addWidget(QLabel('Unsupported Length (z-z) [mm]:'))
        layout.addWidget(self.unsupported_length_zz)
        layout.addWidget(QLabel('Axial Load (kN):'))
        layout.addWidget(self.axial_load)
        layout.addWidget(QLabel('Weld Size (mm):'))
        layout.addWidget(self.weld_size)
        layout.addWidget(QLabel('Bolt Diameter (mm):'))
        layout.addWidget(self.bolt_diameter)

        # Weld fabrication dropdown
        self.weld_fab_label = QLabel('Weld Fabrication:')
        self.weld_fab_combo = QComboBox()
        self.weld_fab_combo.addItems(KEY_DP_WELD_FAB_VALUES)
        layout.addWidget(self.weld_fab_label)
        layout.addWidget(self.weld_fab_combo)

        # End conditions
        self.end_condition_yy_1 = QComboBox(); self.end_condition_yy_1.addItems(['Fixed', 'Hinged', 'Free'])
        self.end_condition_yy_2 = QComboBox(); self.end_condition_yy_2.addItems(['Fixed', 'Hinged', 'Free'])
        self.end_condition_zz_1 = QComboBox(); self.end_condition_zz_1.addItems(['Fixed', 'Hinged', 'Free'])
        self.end_condition_zz_2 = QComboBox(); self.end_condition_zz_2.addItems(['Fixed', 'Hinged', 'Free'])
        layout.addWidget(QLabel('End Condition (y-y) 1:'))
        layout.addWidget(self.end_condition_yy_1)
        layout.addWidget(QLabel('End Condition (y-y) 2:'))
        layout.addWidget(self.end_condition_yy_2)
        layout.addWidget(QLabel('End Condition (z-z) 1:'))
        layout.addWidget(self.end_condition_zz_1)
        layout.addWidget(QLabel('End Condition (z-z) 2:'))
        layout.addWidget(self.end_condition_zz_2)

        # Lacing pattern and connection type
        self.lacing_pattern = QComboBox(); self.lacing_pattern.addItems(['Single', 'Double'])
        self.connection_type = QComboBox(); self.connection_type.addItems(['Welded', 'Bolted'])
        layout.addWidget(QLabel('Lacing Pattern:'))
        layout.addWidget(self.lacing_pattern)
        layout.addWidget(QLabel('Type of Connection:'))
        layout.addWidget(self.connection_type)

        # Button to run design
        self.run_button = QPushButton('Run Design')
        self.run_button.clicked.connect(self.run_design)
        layout.addWidget(self.run_button)

        # Output area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        layout.addWidget(QLabel('Output:'))
        layout.addWidget(self.output_area)

        self.setLayout(layout)

    def run_design(self):
        # Gather input values from UI
        input_dict = {
            'section_profile': 'Channels',
            'section_size': self.section_combo.currentText(),
            'material': self.material_combo.currentText(),
            'unsupported_length_yy': float(self.unsupported_length_yy.text()),
            'unsupported_length_zz': float(self.unsupported_length_zz.text()),
            'end_condition_yy_1': self.end_condition_yy_1.currentText(),
            'end_condition_yy_2': self.end_condition_yy_2.currentText(),
            'end_condition_zz_1': self.end_condition_zz_1.currentText(),
            'end_condition_zz_2': self.end_condition_zz_2.currentText(),
            'lacing_pattern': self.lacing_pattern.currentText(),
            'connection_type': self.connection_type.currentText(),
            'axial_load': float(self.axial_load.text()),
            'weld_size': float(self.weld_size.text()),
            'bolt_diameter': float(self.bolt_diameter.text()),
            'weld_fabrication': self.weld_fab_combo.currentText(),
        }
        errors = validate_inputs(input_dict)
        if errors:
            self.output_area.setPlainText('Input errors:\n' + '\n'.join(errors))
            return
        try:
            design = StandaloneColumnDesign(input_dict)
            design.design_column()
            output_lines = [f"{k.replace('_',' ').title()}: {v}" for k, v in design.result.items()]
            output_lines.append(f"Weld Fabrication: {input_dict['weld_fabrication']}")
            self.output_area.setPlainText('\n'.join(output_lines))
        except Exception as ex:
            self.output_area.setPlainText(f"Exception during design: {ex}")

if __name__ == "__main__":
    app = QApplication([])
    window = LacedColumnTestUI()
    window.show()
    app.exec_() 