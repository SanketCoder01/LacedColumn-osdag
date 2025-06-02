from ..member import Member
from ...Common import *
from ...utils.common.component import ISection, Material
from ...utils.common.common_calculation import *
from ...utils.common.load import Load
from ..tension_member import *
from ...utils.common.Section_Properties_Calculator import BBAngle_Properties
import math
import numpy as np
from ...utils.common import is800_2007
from ...utils.common.component import *
import logging
from ..connection.moment_connection import MomentConnection
from ...utils.common.material import *
from ...Report_functions import *
from ...design_report.reportGenerator_latex import CreateLatex
from pylatex.utils import NoEscape
from ...Common import TYPE_TAB_4, TYPE_TAB_5 
from PyQt5.QtWidgets import QLineEdit, QMainWindow, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QValidator, QDoubleValidator
from ...gui.ui_template import Window
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFormLayout
from PyQt5.QtWidgets import QDialogButtonBox

# NEW: Import calculation class
from .LacedColumnDesign import LacedColumnDesign


class MaterialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Material")
        self.setModal(True)
        self.setup_ui()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove help button

    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Create input fields
        self.grade_input = QLineEdit()
        self.fy_20_input = QLineEdit()
        self.fy_20_40_input = QLineEdit()
        self.fy_40_input = QLineEdit()
        self.fu_input = QLineEdit()
        
        # Add fields to layout
        layout.addRow("Grade:", self.grade_input)
        layout.addRow("Fy (20mm):", self.fy_20_input)
        layout.addRow("Fy (20-40mm):", self.fy_20_40_input)
        layout.addRow("Fy (40mm):", self.fy_40_input)
        layout.addRow("Fu:", self.fu_input)
        
        # Add buttons with proper spacing
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def closeEvent(self, event):
        """Handle dialog close event"""
        self.reject()
        event.accept()

    def get_material_data(self):
        return {
            'grade': self.grade_input.text(),
            'fy_20': self.fy_20_input.text(),
            'fy_20_40': self.fy_20_40_input.text(),
            'fy_40': self.fy_40_input.text(),
            'fu': self.fu_input.text()
        }


class LacedColumn(Member):
    def __init__(self):
        super(LacedColumn, self).__init__()
        self.design_status = False
        self.result = {}
        self.utilization_ratio = 0
        self.area = 0
        self.epsilon = 1.0
        self.fy = 0
        self.section = None
        self.material = {}
        self.weld_size = ''
        self.weld_type = ''
        self.weld_strength = 0
        self.lacing_incl_angle = 0
        self.lacing_section = ''
        self.lacing_type = ''
        self.allowed_utilization = ''
        self.design_pref_dialog = None
        self.logger = None
        self.module = KEY_DISP_COMPRESSION_LacedColumn
        self.mainmodule = 'Member'
        
        # Initialize output_title_fields
        self.output_title_fields = {}
        
        # Initialize design preferences with default values
        self.design_pref_dictionary = {
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
        }
        
        # Initialize validators
        self.double_validator = QDoubleValidator()
        self.double_validator.setNotation(QDoubleValidator.StandardNotation)
        self.double_validator.setDecimals(2)

       ###################################
    # design preference functions start
    ###################################

    def tab_list(self):
        return [
            ("Weld Preferences", TYPE_TAB_4, self.all_weld_design_values),
        ]

    def all_weld_design_values(self, *args):
        return [
            (KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE, "Lacing Profile Type", TYPE_COMBOBOX, ["Angle", "Channel", "Flat"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_LACING_PROFILE, "Lacing Profile Section", TYPE_COMBOBOX_CUSTOMIZED, self.get_lacing_profiles, True, 'No Validator'),
            (KEY_DISP_LACEDCOL_EFFECTIVE_AREA, "Effective Area Parameter", TYPE_COMBOBOX, ["1.0", "0.9", "0.8", "0.7", "0.6", "0.5", "0.4", "0.3", "0.2", "0.1"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_ALLOWABLE_UR, "Allowable Utilization Ratio", TYPE_COMBOBOX, ["1.0", "0.95", "0.9", "0.85"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_BOLT_DIAMETER, "Bolt Diameter", TYPE_COMBOBOX, ["16mm", "20mm", "24mm", "27mm"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_WELD_SIZE, "Weld Size", TYPE_COMBOBOX, ["4mm", "5mm", "6mm", "8mm"], True, 'No Validator')
        ]

    def tab_value_changed(self):
        return [
            ("Weld Preferences", [KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE], [KEY_DISP_LACEDCOL_LACING_PROFILE], TYPE_COMBOBOX_CUSTOMIZED, self.get_lacing_profiles)
        ]

    def edit_tabs(self):
        return []

    def input_dictionary_design_pref(self):
        return [
            ("Weld Preferences", TYPE_COMBOBOX, [
                KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE,
                KEY_DISP_LACEDCOL_LACING_PROFILE,
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA,
                KEY_DISP_LACEDCOL_ALLOWABLE_UR,
                KEY_DISP_LACEDCOL_BOLT_DIAMETER,
                KEY_DISP_LACEDCOL_WELD_SIZE
            ]),
        ]

    def input_dictionary_without_design_pref(self):
        return [
            (None, [
                KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE,
                KEY_DISP_LACEDCOL_LACING_PROFILE,
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA,
                KEY_DISP_LACEDCOL_ALLOWABLE_UR,
                KEY_DISP_LACEDCOL_BOLT_DIAMETER,
                KEY_DISP_LACEDCOL_WELD_SIZE
            ], '')
        ]

    def get_values_for_design_pref(self, key, design_dictionary):
        defaults = {
            KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE: "Angle",
            KEY_DISP_LACEDCOL_LACING_PROFILE: "ISA 40x40x5",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
        }
        if key in design_dictionary:
            return design_dictionary[key]
        if key in defaults:
            return defaults[key]
        return ""

    def get_lacing_profiles(self, *args):
        if not args or not args[0]:
            return ["ISA 40x40x5"]

        profile_type = args[0]
        if profile_type == "Angle":
            return ["ISA 40x40x5", "ISA 50x50x5", "ISA 60x60x5"]
        elif profile_type == "Channel":
            return ["ISMC 75", "ISMC 100", "ISMC 125"]
        elif profile_type == "Flat":
            return ["ISF 100x8", "ISF 120x10"]
        return [""]

    ###################################
    # design preference functions end
    ###################################

    def set_osdaglogger(self, widget):
        """Function to set Logger for LacedColumn Module"""
        key = 'LacedColumn'
        logger = logging.getLogger(f'Osdag.{key}')  
        logger.setLevel(logging.ERROR)
        logger.disabled = True  # Disable all logging

        if not logger.hasHandlers():  # Prevent duplicate handlers
            # Remove all existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                
            # Only add file handler for errors
            file_handler = logging.FileHandler(f'{key.lower()}_log.txt')
            file_handler.setLevel(logging.ERROR)
            formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                        datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Disable propagation to parent loggers
            logger.propagate = False
            
            self.logger = logger
        return logger

    def process_design(self, design_dict):
        """
        Main processing method to invoke laced column calculations.
        Uses LacedColumnDesign for core computations.
        """
        try:
            # Step 1: Call the computational model
            design_obj = LacedColumnDesign(design_dict)
            result = design_obj.design()

            # Step 2: Extract results into current instance
            self.result = result
            self.utilization_ratio = result.get("utilization", 0)
            self.area = design_obj.Ae
            self.section = design_dict.get(KEY_SECTION_SIZE, "")
            self.material = {"grade": design_dict.get(KEY_MATERIAL, "Unknown")}
            
            # Weld details
            self.weld_size = design_dict.get(KEY_WELD_SIZE, "5mm")
            self.weld_type = "Fillet"
            self.weld_strength = round(design_obj.weld_strength_per_mm() * result.get("weld_length_required", 0), 2)
            
            # Lacing details
            self.lacing_incl_angle = result.get("lacing_angle_deg", "")
            self.lacing_section = design_dict.get(KEY_LACING_PROFILE, "")
            self.lacing_type = design_dict.get(KEY_LACING_PATTERN, "")
            self.allowed_utilization = design_dict.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0")

            # Set design status based on utilization and other checks
            self.design_status = result.get("design_safe", False)

        except Exception as e:
            self.design_status = False
            self.result = {"design_safe": False,
                          "message": "Design failed. Please check input parameters.",
                          "Allowed Utilization Ratio": design_dict.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0"),
                          "error": str(e)}
            self.utilization_ratio = 0

    def run_design(self, design_dict):
        self.process_design(design_dict)
        return self.design_status

    def generate_latex_report(self):
        if not self.design_status:
            return "Design not safe. No report generated."
        report = CreateLatex()
        report.add_title("Laced Column Design Report")
        report.add_section("Summary", [
            f"Utilization Ratio: {self.utilization_ratio:.2f}",
            f"Design Status: {'Safe' if self.design_status else 'Unsafe'}",
            f"Lacing Angle: {self.lacing_incl_angle}°",
            f"Required Weld Length: {self.result.get('weld_length_required', 'N/A')} mm"
        ])
        report.compile()
        return "Report generation completed."

    def input_value_changed(self, ui_self=None):
        lst = []

        t8 = ([KEY_LACEDCOL_MATERIAL], KEY_LACEDCOL_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t8)

        t9 = ([KEY_LACEDCOL_SEC_PROFILE], KEY_LACEDCOL_SEC_SIZE, TYPE_COMBOBOX_CUSTOMIZED, self.get_section_sizes)
        lst.append(t9)

        t10 = ([KEY_LYY], KEY_END_COND_YY, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t10)

        t11 = ([KEY_LZZ], KEY_END_COND_ZZ, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t11)
        
        t12 = ([KEY_LACEDCOL_MATERIAL], KEY_LACEDCOL_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t12)


        return lst

    def input_values(self, ui_self=None):
        self.module= KEY_DISP_LACEDCOL
        options_list = []
        
        options_list.append((KEY_DISP_LACEDCOL, "Laced Column", TYPE_MODULE, [], True, 'No Validator'))

        # Section
        options_list.append(("title_Section ", "Section Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_LACEDCOL_SEC_PROFILE, KEY_DISP_LACEDCOL_SEC_PROFILE, TYPE_COMBOBOX, KEY_LACEDCOL_SEC_PROFILE_OPTIONS, True, 'No Validator'))
        options_list.append((KEY_LACEDCOL_SEC_SIZE, KEY_DISP_LACEDCOL_SEC_SIZE, TYPE_COMBOBOX_CUSTOMIZED, KEY_LACEDCOL_SEC_SIZE_OPTIONS, True, 'No Validator'))

        # Conditionally show text field if "Custom" is selected
        if ui_self and isinstance(ui_self, dict) and ui_self.get(KEY_LACEDCOL_SEC_SIZE) == "Custom":
            options_list.append(("custom_sec_size_input", "Enter Custom Section Size", TYPE_TEXTBOX, None, True, 'No Validator'))

        options_list.append((KEY_LACEDCOL_SPACING, KEY_DISP_LACEDCOL_SPACING, TYPE_TEXTBOX, None, False, 'Float Validator'))

        # Material
        options_list.append(("title_Material", "Material Properties", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_LACEDCOL_MATERIAL, KEY_DISP_LACEDCOL_MATERIAL, TYPE_COMBOBOX, KEY_LACEDCOL_MATERIAL_OPTIONS, True, 'No Validator'))

        # Geometry
        options_list.append(("title_Geometry", "Geometry", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, KEY_DISP_LACEDCOL_UNSUPPORTED_LENGTH_YY, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, KEY_DISP_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_LACEDCOL_END_CONDITION_YY, KEY_DISP_LACEDCOL_END_CONDITION_YY, TYPE_COMBOBOX_CUSTOMIZED, VALUES_END_COND, True, 'No Validator'))
        options_list.append((KEY_LACEDCOL_END_CONDITION_ZZ, KEY_DISP_LACEDCOL_END_CONDITION_ZZ, TYPE_COMBOBOX_CUSTOMIZED, VALUES_END_COND, True, 'No Validator'))
        
        # Lacing
        options_list.append((KEY_LACING_PATTERN, "Lacing Pattern", TYPE_COMBOBOX, VALUES_LACING_PATTERN, True, 'No Validator'))
         
        # Connection
        options_list.append((KEY_CONN_TYPE, "Type of Connection", TYPE_COMBOBOX, VALUES_CONNECTION_TYPE, True, 'No Validator'))

        # Load
        options_list.append(("title_Load", "Load Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_AXIAL_LOAD, "Axial Load (kN)", TYPE_TEXTBOX, None, True, 'Float Validator'))

        return options_list
    def module_name(self):
        return KEY_DISP_LACEDCOL

    def customized_input(self, ui_self=None):
        """
        Returns a list of customized input options for the laced column module UI.
        """
        customized_list = []

        # Customize section size options based on selected profile
        customized_list.append((
            KEY_LACEDCOL_SEC_SIZE,
            self.get_section_sizes,
            [],
            "Select the section size based on the chosen profile"
        ))

        # Customize end condition options for y-y axis
        customized_list.append((
            KEY_LACEDCOL_END_CONDITION_YY,
            self.get_end_conditions,
            [],
            "Select the end condition for y-y axis"
        ))

        # Customize end condition options for z-z axis
        customized_list.append((
            KEY_LACEDCOL_END_CONDITION_ZZ,
            self.get_end_conditions,
            [],
            "Select the end condition for z-z axis"
        ))

        # Material customization
        customized_list.append((
            KEY_LACEDCOL_MATERIAL,
            self.new_material,
            [],
            "Material Custom popup"
        ))

        return customized_list

    def new_material(self, *args):
        """
        Handles material selection for laced column.
        If no arguments are provided, returns list of predefined materials.
        If called with arguments, opens custom material popup only if "Custom" is selected.
        """
        if not args:
            return KEY_LACEDCOL_MATERIAL_OPTIONS
            
        try:
            # Only show dialog if "Custom" is selected
            if args[0] == "Custom":
                dialog = MaterialDialog()
                result = dialog.exec_()
                
                if result == QDialog.Accepted:
                    material_data = dialog.get_material_data()
                    if material_data:
                        # Update material properties
                        self.material = {
                            'grade': material_data.get('grade', 'Custom'),
                            'fy_20': float(material_data.get('fy_20', 0)),
                            'fy_20_40': float(material_data.get('fy_20_40', 0)),
                            'fy_40': float(material_data.get('fy_40', 0)),
                            'fu': float(material_data.get('fu', 0))
                        }
                        return self.material['grade']
            return None
        except Exception as e:
            logger = self.set_osdaglogger(None)
            logger.error(f"Error in new_material: {str(e)}")
            return None

    def get_section_sizes(self, *args):
        """
        Returns available section sizes based on the selected profile.
        Includes a "Custom" option for user-defined sections.
        """
        if not args or not args[0]:
            return ["ISMB 100", "ISMB 125", "ISMB 150", "ISMB 175", "ISMB 200", "Custom"]

        profile = args[0]
        if profile == "ISMB":
            return ["ISMB 100", "ISMB 125", "ISMB 150", "ISMB 175", "ISMB 200", "Custom"]
        elif profile == "ISMC":
            return ["ISMC 75", "ISMC 100", "ISMC 125", "ISMC 150", "ISMC 175", "Custom"]
        elif profile == "ISWB":
            return ["ISWB 300", "ISWB 350", "ISWB 400", "ISWB 450", "ISWB 500", "Custom"]
        elif profile == "Custom":
            return ["Custom"]
        else:
            return ["Custom"]

    def get_end_conditions(self, *args):
        """
        Returns available end conditions.
        """
        return VALUES_END_COND if "VALUES_END_COND" in globals() else ["Fixed", "Hinged", "Free"]

    def get_lacing_profiles(self, *args):
        """
        Returns lacing profile options based on selected lacing pattern.
        """
        if not args or not args[0]:
            return ["ISA 40x40x5", "ISA 50x50x5", "ISA 60x60x5"]

        pattern = args[0]
        if pattern == "Single Lacing":
            return ["ISA 40x40x5", "ISA 50x50x5", "ISA 60x60x5"]
        elif pattern == "Double Lacing":
            return ["ISA 30x30x4", "ISA 35x35x4", "ISA 40x40x4"]
        elif pattern == "Flat Bar":
            return ["ISF 100x8", "ISF 120x10"]
        else:
            return []

    def module_name(self):
        return KEY_DISP_LACEDCOL

    def spacing(self, status):
        spacing = []

        # Informative Note
        spacing.append((None, "", TYPE_NOTE, "Representative Image for Laced Column Spacing Details"))

        # Image section – update image path as per your resource location
        spacing.append((
            None,
            'Laced Column Spacing Pattern',
            TYPE_SECTION,
            [str(files("osdag.data.ResourceFiles.images").joinpath("laced_spacing_image.png")), 400, 300, ""]
        ))

        # Spacing & Geometry Inputs
        spacing.append((
            KEY_LACEDCOL_LACE_PITCH,
            KEY_DISP_LACEDCOL_LACE_PITCH,
            TYPE_TEXTBOX,
            self.lace_pitch if status else ''
        ))
        spacing.append((
            KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY,
            KEY_DISP_LACEDCOL_UNSUPPORTED_LENGTH_YY,
            TYPE_TEXTBOX,
            self.unsupported_length_yy if status else ''
        ))
        spacing.append((
            KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ,
            KEY_DISP_LACEDCOL_UNSUPPORTED_LENGTH_ZZ,
            TYPE_TEXTBOX,
            self.unsupported_length_zz if status else ''
        ))

        # End Condition Dropdowns
        spacing.append((
            KEY_LACEDCOL_END_CONDITION_YY,
            KEY_DISP_LACEDCOL_END_CONDITION_YY,
            TYPE_COMBOBOX,
            KEY_LACEDCOL_END_CONDITION_YY_OPTIONS if status else ''
        ))
        spacing.append((
            KEY_LACEDCOL_END_CONDITION_ZZ,
            KEY_DISP_LACEDCOL_END_CONDITION_ZZ,
            TYPE_COMBOBOX,
            KEY_LACEDCOL_END_CONDITION_ZZ_OPTIONS if status else ''
        ))

        return spacing

    def output_values(self, flag):
        out_list = []

        # SECTION & MATERIAL
        out_list.append((None, "Section and Material", TYPE_TITLE, None, True))
        out_list.append((KEY_LACEDCOL_SEC_SIZE, "Main Column Section", TYPE_TEXTBOX, 
                        self.section if flag else '', True))
        out_list.append((KEY_LACEDCOL_MATERIAL, "Material Grade", TYPE_TEXTBOX, 
                        self.material['grade'] if flag else '', True))
        out_list.append((KEY_LACEDCOL_EFFECTIVE_AREA, "Effective Area (mm²)", TYPE_TEXTBOX, 
                        f"{self.area:.2f}" if flag and self.area else '', True))
        out_list.append((KEY_EFFECTIVE_AREA_PARAM, "Effective Area Factor", TYPE_TEXTBOX, 
                        f"{self.result.get('effective_area_factor', ''):.2f}" if flag and self.result.get('effective_area_factor') else '', True))

        # DESIGN PARAMETERS
        out_list.append((None, "Design Parameters", TYPE_TITLE, None, True))
        out_list.append((KEY_OUT_SLENDERNESS, "Slenderness Ratio", TYPE_TEXTBOX, 
                        f"{self.result.get('slenderness', ''):.2f}" if flag and self.result.get('slenderness') else '', True))
        out_list.append((KEY_OUT_DESIGN_STRENGTH, "Design Compressive Strength (kN)", TYPE_TEXTBOX, 
                        f"{self.result.get('design_strength', ''):.2f}" if flag and self.result.get('design_strength') else '', True))
        out_list.append((KEY_UTILIZATION_RATIO, KEY_DISP_UTILIZATION_RATIO, TYPE_TEXTBOX, 
                        f"{self.utilization_ratio:.3f}" if flag and self.utilization_ratio else '', True))
        out_list.append((KEY_ALLOWED_UTILIZATION, "Allowed Utilization Ratio", TYPE_TEXTBOX, 
                        self.allowed_utilization if flag else '1.0', True))

        # WELDING DETAILS
        out_list.append((None, "Welding Details", TYPE_TITLE, None, True))
        out_list.append((KEY_WELD_SIZE, "Weld Size (mm)", TYPE_TEXTBOX, 
                        self.weld_size if flag else '', True))
        out_list.append((KEY_WELD_TYPE, "Weld Type", TYPE_TEXTBOX, 
                        self.weld_type if flag else '', True))
        out_list.append((KEY_WELD_STRENGTH, "Weld Strength (kN)", TYPE_TEXTBOX, 
                        f"{self.weld_strength:.2f}" if flag and self.weld_strength else '', True))
        weld_length = self.result.get('weld_length_required')
        out_list.append((KEY_WELD_LENGTH, "Required Weld Length (mm)", TYPE_TEXTBOX, 
                        f"{weld_length:.2f}" if flag and weld_length is not None else '', True))

        # LACING DETAILS
        out_list.append((None, "Lacing Details", TYPE_TITLE, None, True))
        out_list.append((KEY_LACING_TYPE, "Lacing Pattern", TYPE_TEXTBOX, 
                        self.lacing_type if flag else '', True))
        out_list.append((KEY_LACING_SECTION, "Lacing Section", TYPE_TEXTBOX, 
                        self.lacing_section if flag else '', True))
        out_list.append((KEY_LACING_INCL_ANGLE, "Inclination Angle (°)", TYPE_TEXTBOX, 
                        f"{self.lacing_incl_angle:.2f}" if flag and self.lacing_incl_angle else '', True))
        out_list.append((KEY_LACING_SPACING, "Lacing Spacing (mm)", TYPE_TEXTBOX, 
                        f"{self.result.get('L0', ''):.2f}" if flag and self.result.get('L0') else '', True))
        out_list.append((KEY_LACING_FORCE, "Lacing Force (kN)", TYPE_TEXTBOX, 
                        f"{self.result.get('Fcl', ''):.2f}" if flag and self.result.get('Fcl') else '', True))

        # TIE PLATE DETAILS
        out_list.append((None, "Tie Plate Details", TYPE_TITLE, None, True))
        out_list.append((KEY_TIE_PLATE_D, "Depth (mm)", TYPE_TEXTBOX, 
                        f"{self.result.get('tie_plate_D', ''):.2f}" if flag and self.result.get('tie_plate_D') else '', True))
        out_list.append((KEY_TIE_PLATE_L, "Length (mm)", TYPE_TEXTBOX, 
                        f"{self.result.get('tie_plate_L', ''):.2f}" if flag and self.result.get('tie_plate_L') else '', True))
        out_list.append((KEY_TIE_PLATE_T, "Thickness (mm)", TYPE_TEXTBOX, 
                        f"{self.result.get('tie_plate_t', ''):.2f}" if flag and self.result.get('tie_plate_t') else '', True))

        # DESIGN SUMMARY
        out_list.append((None, "Design Summary", TYPE_TITLE, None, True))
        out_list.append((KEY_DESIGN_STATUS, "Design Status", TYPE_TEXTBOX, 
                        "Safe" if self.design_status else "Unsafe" if flag else '', True))

        return out_list

    def select_bolt_dia_and_grade(self, design_dictionary):
        """
        For laced columns, this stores bolt diameter and grade as selected,
        without performing grip length or capacity checks.
        """
        self.selected_bolt_diameter = design_dictionary.get(KEY_BOLT_DIAMETER, 16)
        self.selected_bolt_grade = design_dictionary.get(KEY_BOLT_GRADE, "4.6")

        # Store in bolt object if needed
        self.bolt.bolt_diameter_provided = self.selected_bolt_diameter
        self.bolt.bolt_grade_provided = self.selected_bolt_grade

        # You may add default min/max pitch or edge distances later
        self.dia_available = True
        self.bolt_dia_grade_status = True

        self.design_status = True

        # Optional safe rounding of known values
        if hasattr(self.bolt, 'bolt_type') and self.bolt.bolt_type == 'Bearing Bolt':
            self.bolt.bolt_bearing_capacity = None  # placeholder, no calc

        self.bolt.bolt_shear_capacity = None  # placeholder
        self.bolt.bolt_capacity = None        # placeholder

        # Skip bolt count logic entirely

    def welded_laced_connection_check(self, design_dict, count=0):
        """
        Placeholder method for welded laced column connection design check.

        Intended to later handle:
        - Weld strength evaluation
        - Lacing angle compliance (40°–70°)
        - Effective area parameter check
        - Utilization check

        Currently: No calculations performed.
        """
        # Store input references
        self.checked_weld_size = self.weld_size
        self.checked_lacing_angle = self.lacing_angle
        self.checked_effective_area_param = self.effective_area_param

        # Placeholder status
        self.weld_required_length = None
        self.weld_strength_status = None

        # Simply mark status as successful unless validation rules are needed
        self.design_status = True

    def check_capacity_reduction_1_welded(self, design_dictionary):
        """
        Placeholder for capacity reduction check for welded laced columns.
        No calculations performed at this stage.
        """

        self.cap_red = False
        self.design_status = True
        self.Ae = self.area  # Assume full effective area temporarily

        # Call next phase placeholder
        if hasattr(self, "check_capacity_reduction_2_welded"):
            self.check_capacity_reduction_2_welded(design_dictionary)

    def check_capacity_reduction_2_welded(self, design_dictionary):
        """
        Placeholder for checking weld-based reduction on area/capacity.
        Actual logic deferred for later stages.
        """
        
        self.cap_red = False
        self.design_status = True

        # Proceed to formatting for summary/debug
        self.final_formatting_welded(design_dictionary)

    def run_design(self, design_dict):
        """
        Public method to be called by UI or automation to run full design.
        """
        self.process_design(design_dict)
        return self.design_status

    def generate_latex_report(self):
        """
        Generates LaTeX report using the computed results.
        Only if design status is OK.
        """
        if not self.design_status:
            return "Design not safe. No report generated."

        # Placeholder report generation
        report = CreateLatex()
        report.add_title("Laced Column Design Report")
        report.add_section("Summary", [
            f"Utilization Ratio: {self.utilization_ratio:.2f}",
            f"Design Status: {'Safe' if self.design_status else 'Unsafe'}",
            f"Lacing Angle: {self.lacing_incl_angle}°",
            f"Required Weld Length: {self.result.get('weld_length_required', 'N/A')} mm"
        ])
        report.compile()

        return "Report generation completed."

    def final_formatting_welded(self, design_dictionary):
        """
        Final reporting placeholder for welded laced column summary.
        Only logs assumed placeholder values — no calculations.
        """

        self.utilization_ratio = 0.0
        self.weld_required_length = 0
        self.weld_length = 0
        self.weld_capacity = 0
        self.Ae = self.area
        self.design_status = True
        
    def func_for_validation(self, design_dictionary):
        """
        Validates input fields for Laced Column Design.
        Checks for missing or invalid values (like zero/negative).
        Returns a list of error messages if validation fails.
        """
        all_errors = []
        missing_fields_list = []
        flag_positive_values = True

        # 1. Check for missing required inputs
        required_keys = [
            KEY_LACEDCOL_SEC_SIZE,
            KEY_LACEDCOL_MATERIAL,
            KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY,
            KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ,
            KEY_LACEDCOL_END_CONDITION_YY,
            KEY_LACEDCOL_END_CONDITION_ZZ,
            KEY_AXIAL_LOAD
        ]

        for key in required_keys:
            value = design_dictionary.get(key, "")
            if value == "":
                missing_fields_list.append(key)
            else:
                try:
                    if key in [KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 
                             KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, KEY_AXIAL_LOAD]:
                        if float(value) <= 0:
                            all_errors.append(f"{key} must be greater than zero.")
                            flag_positive_values = False
                except Exception:
                    all_errors.append(f"{key} must be a valid number.")
                    flag_positive_values = False

        # 2. Special handling for custom section size
        if design_dictionary.get(KEY_LACEDCOL_SEC_SIZE) == "Custom":
            custom_size = design_dictionary.get("custom_sec_size_input", "")
            if not custom_size:
                all_errors.append("Please enter a custom section size.")
            else:
                try:
                    # Validate custom section size format
                    parts = custom_size.split()
                    if len(parts) != 2:
                        all_errors.append("Custom section size must be in format 'Section Size' (e.g., 'ISMB 100')")
                except Exception:
                    all_errors.append("Invalid custom section size format.")

        # 3. If missing fields
        if missing_fields_list:
            msg = self.generate_missing_fields_error_string(missing_fields_list)
            all_errors.append(msg)

        # 4. Final decision
        if not all_errors and flag_positive_values:
            return []  # No errors
        else:
            return all_errors

    def generate_missing_fields_error_string(self, missing_fields_list):
        """
        Generates a user-friendly string listing all missing fields.
        """
        message = "Please input the following required field"
        if len(missing_fields_list) > 1:
            message += "s"
        message += ": " + ", ".join(missing_fields_list) + "."
        return message

    # Constants for calculations
    IMPERFECTION_FACTOR = 0.49

    def effective_length_parameter_K(self):
        """Get effective length parameter K based on end conditions"""
        # Referring IS800:2007 table 11
        pass

    def effective_slenderness_ratio_main(self, K, L, r):
        """Calculate effective slenderness ratio for main member"""
        return 1.05 * (K * L / r)

    def design_compressive_stress(self, fy, gamma_m0, chi):
        """Calculate design compressive stress"""
        return chi * fy / gamma_m0

    def phi_value_main(self, alpha, lambda_nondim):
        """Calculate phi value for main member"""
        return 0.5 * (1 + alpha * (lambda_nondim - 0.2) + lambda_nondim**2)

    def nondimensional_slenderness_main(self, fy, fcc):
        """Calculate non-dimensional slenderness ratio for main member"""
        return math.sqrt(fy / fcc)

    def euler_buckling_stress_main(self, E, lambda_e):
        """Calculate Euler buckling stress for main member"""
        return (math.pi**2 * E) / (lambda_e**2)

    def stress_reduction_factor(self, phi, lambda_nondim):
        """Calculate stress reduction factor"""
        return 1 / (phi + math.sqrt(phi**2 - lambda_nondim**2))

    def design_strength_check(self, P, Pd):
        """Check if design strength is adequate"""
        return P <= Pd

    def design_compressive_strength(self, Ae, fcd):
        """Calculate design compressive strength"""
        return Ae * fcd

    def spacing_back_to_back(self, Iyy, A, Cyy, Izz):
        """Calculate spacing for back-to-back channels"""
        S = math.sqrt(((Izz / 2) - Iyy) / A) - Cyy
        return 2 * S

    def spacing_front_to_front(self, Iyy, A, Cyy, Izz):
        """Calculate spacing for front-to-front channels"""
        S = math.sqrt(((Izz / 2) - Iyy) / A) + Cyy
        return 2 * S

    def spacing_for_2_girders(self, Iyy, A, Cyy, Izz, flange_width, clear_spacing):
        """Calculate spacing for two girders"""
        front_spacing = self.spacing_front_to_front(Iyy, A, Cyy, Izz)
        return max(front_spacing, flange_width + clear_spacing)

    def tie_plate_back_to_back(self, S, Cyy, bf, g):
        """Calculate tie plate dimensions for back-to-back arrangement"""
        De = S + 2 * Cyy
        De = max(De, 2 * bf)
        D = De + 2 * g
        L = S + 2 * g
        t = (1 / 50) * (S + 2 * g)
        return De, D, L, t

    def tie_plate_front_to_front(self, S, Cyy, g):
        """Calculate tie plate dimensions for front-to-front arrangement"""
        De = S - 2 * Cyy
        D = De + 2 * g
        L = S + 2 * g
        t = (1 / 50) * (S + 2 * g)
        return De, D, L, t

    def tie_plate_girders(self, S, bf, g):
        """Calculate tie plate dimensions for girders"""
        De = S
        De = max(De, 2 * bf)
        D = De + 2 * g
        L = S + 2 * g
        t = (1 / 50) * (S + 2 * g)
        return De, D, L, t

    def initial_lacing_spacing(self, S, g):
        """Calculate initial lacing spacing"""
        return 2 * (S + 2 * g)

    def number_of_lacings(self, L, Dt, L0i):
        """Calculate number of lacings"""
        return int(round((L - 2 * Dt - 80) / L0i + 1))

    def actual_lacing_spacing(self, L, Dt, NL):
        """Calculate actual lacing spacing"""
        return (L - 2 * Dt - 80) / (NL - 1)

    def lacing_angle_check(self, L0, S, g):
        """Check if lacing angle is within permissible range"""
        angle_deg = math.degrees(math.atan(2 * (S + 2 * g) / L0))
        is_valid = 40 <= angle_deg <= 70
        return is_valid

    def check_lacing_slenderness(self, L0, rmin, lambda_e):
        """Check lacing slenderness"""
        slenderness = L0 / rmin
        limit = min(50, 0.7 * lambda_e)
        return slenderness <= limit

    def transverse_shear_in_single_laced(self, AF):
        """Calculate transverse shear in single laced member"""
        return 0.025 * AF

    def compressive_force_in_single_laced(self, Vt, theta):
        """Calculate compressive force in single laced member"""
        return Vt / math.sin(math.radians(theta))

    def transverse_shear_in_double_laced(self, AF):
        """Calculate transverse shear in double laced member"""
        return 2 * 0.025 * AF

    def compressive_force_in_double_laced(self, Vt, theta):
        """Calculate compressive force in double laced member"""
        return 0.5 * Vt / math.sin(math.radians(theta))

    def effective_length_lacing(self, S, g, theta):
        """Calculate effective length of lacing"""
        return (S + 2 * g) / math.sin(math.radians(theta))

    def lacing_thickness_single_laced(self, effective_length):
        """Calculate lacing thickness for single laced member"""
        return effective_length / 40

    def lacing_thickness_double_laced(self, effective_length):
        """Calculate lacing thickness for double laced member"""
        return effective_length / 60

    def min_radius_of_gyration(self, t):
        """Calculate minimum radius of gyration"""
        return t / math.sqrt(12)

    def effective_slenderness_ratio(self, effective_length, rmin):
        """Calculate effective slenderness ratio"""
        return effective_length / rmin

    def compressive_design_stress(self, fy, gamma_m0, alpha, lambda_nondim):
        """Calculate compressive design stress"""
        phi = self.phi_value(alpha, lambda_nondim)
        chi = self.chi(phi, lambda_nondim)
        fcd = chi * fy / gamma_m0
        return fcd

    def phi_value(self, alpha, lambda_nondim):
        """Calculate phi value"""
        return 0.5 * (1 + alpha * (lambda_nondim - 0.2) + lambda_nondim**2)

    def nondimensional_slenderness(self, fy, fcc):
        """Calculate non-dimensional slenderness ratio"""
        return (fy / fcc)**0.5

    def euler_buckling_stress(self, E, lambda_e):
        """Calculate Euler buckling stress"""
        return (math.pi**2 * E) / (lambda_e**2)

    def chi(self, phi, lambda_nondim):
        """Calculate chi value"""
        return 1 / (phi + ((phi**2 - lambda_nondim**2)**0.5))

    def compressive_strength_check(self, Ae, fcd, Pcal):
        """Check compressive strength"""
        Pd = Ae * fcd
        return Pd >= Pcal

    def tension_yield_check(self, Ag, fy, gamma_m0, Pcal):
        """Check tension yield strength"""
        Tdg = Ag * fy / gamma_m0
        return Tdg >= Pcal

    def tension_rupture_check(self, Anc, fu, gamma_m1, beta, Ag, fy, gamma_m0, Pcal):
        """Check tension rupture strength"""
        Tdn = (0.9 * Anc * fu / gamma_m1) + (beta * Ag * fy / gamma_m0)
        return Tdn >= Pcal

    def shear_lag_factor(self, w, t, fy, fu, bs, Lc, gamma_m0, gamma_m1):
        """Calculate shear lag factor"""
        beta = 1.4 - 0.076 * (w / t) * (fy / fu) * (bs / Lc)
        beta_max = 0.9 * (fu * gamma_m0) / (fy * gamma_m1)
        beta = min(beta, beta_max)
        beta = max(beta, 0.7)
        return beta

    def bolt_shear_strength(self, fu, nn, Anb, ns, Asb, gamma_mb):
        """Calculate bolt shear strength"""
        Vnsb = (fu / (3**0.5)) * (nn * Anb + ns * Asb)
        Vdsb = Vnsb / gamma_mb
        return Vdsb

    def bolt_bearing_strength(self, kb, d, t, fu, gamma_mb):
        """Calculate bolt bearing strength"""
        Vnpb = 2.5 * kb * d * t * fu
        Vdpb = Vnpb / gamma_mb
        return Vdpb

    def bolt_value(self, Vdsb, Vdpb):
        """Calculate bolt value"""
        return min(Vdsb, Vdpb)

    def force_on_lacing(self, Vt, N, theta_deg):
        """Calculate force on lacing"""
        theta_rad = math.radians(theta_deg)
        return 2 * (Vt / N) * (1 / math.tan(theta_rad))

    def number_of_bolts(self, F, Vbv):
        """Calculate number of bolts required"""
        return math.ceil(F / Vbv)

    def weld_strength_fu(self, fu, gamma_mw):
        """Calculate weld strength based on ultimate strength"""
        return fu / (3**0.5 * gamma_mw)

    def weld_design_strength(self, s, fup):
        """Calculate weld design strength"""
        return 0.7 * s * fup

    def required_weld_length(self, Pcal, fwd):
        """Calculate required weld length"""
        return Pcal / fwd

    def validate_design_preferences(self, design_dictionary):
        """
        Validates design preferences values.
        Returns (is_valid, error_message) tuple.
        """
        try:
            # Check effective area parameter
            effective_area = float(design_dictionary.get(KEY_DISP_LACEDCOL_EFFECTIVE_AREA, "1.0"))
            if not (0.0 < effective_area <= 1.0):
                return False, "Effective Area Parameter must be between 0 and 1"

            # Check allowable utilization ratio
            allowable_ur = float(design_dictionary.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0"))
            if not (0.0 < allowable_ur <= 1.0):
                return False, "Allowable Utilization Ratio must be between 0 and 1"

            # Check lacing pattern
            lacing_pattern = design_dictionary.get(KEY_LACING_PATTERN)
            if lacing_pattern not in ["Single Lacing", "Double Lacing"]:
                return False, "Invalid Lacing Pattern selected"

            # Check lacing profile
            lacing_profile = design_dictionary.get(KEY_LACING_PROFILE)
            if lacing_profile not in ["Angle", "Channel", "Flat"]:
                return False, "Invalid Lacing Profile selected"

            # Check weld size
            weld_size = design_dictionary.get(KEY_DISP_LACEDCOL_WELD_SIZE)
            if not weld_size or not weld_size.endswith("mm"):
                return False, "Invalid Weld Size format"

            # Check bolt diameter
            bolt_diameter = design_dictionary.get(KEY_DISP_LACEDCOL_BOLT_DIAMETER)
            if not bolt_diameter or not bolt_diameter.endswith("mm"):
                return False, "Invalid Bolt Diameter format"

            return True, ""

        except Exception as e:
            return False, f"Error validating design preferences: {str(e)}"

    def show_design_preferences(self):
        try:
            # If dialog already exists and is visible, just return
            if self.design_pref_dialog is not None and self.design_pref_dialog.isVisible():
                return True
                
            # If dialog exists but is not visible, show it
            if self.design_pref_dialog is not None:
                self.design_pref_dialog.show()
                return True
                
            # Create new dialog if none exists
            from ...gui.UI_DESIGN_PREFERENCE import DesignPreferences
            self.design_pref_dialog = DesignPreferences(self, None, {})
            
            # Set validators for numeric fields
            for key in [KEY_CONNECTOR_FU, KEY_CONNECTOR_FY_20, KEY_CONNECTOR_FY_20_40, KEY_CONNECTOR_FY_40]:
                if hasattr(self.design_pref_dialog, key):
                    field = getattr(self.design_pref_dialog, key)
                    if isinstance(field, QLineEdit):
                        field.setValidator(self.double_validator)
                        
            # Connect dialog close event to cleanup
            self.design_pref_dialog.finished.connect(self.cleanup_design_pref_dialog)
            
            self.design_pref_dialog.show()
            return True
            
        except Exception as e:
            logger = self.set_osdaglogger(None)
            logger.error(f"Error showing design preferences: {str(e)}")
            return False
            
    def cleanup_design_pref_dialog(self):
        """Clean up design preference dialog when closed"""
        if self.design_pref_dialog is not None:
            self.design_pref_dialog.deleteLater()
            self.design_pref_dialog = None
            # Clear design preferences
            self.design_pref_dictionary = {}
            # Reset default values
            self.design_pref_dictionary = {
                KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
                KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
                KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
            }

    def output_title_change(self):
        """Handle output title changes and return visibility settings"""
        try:
            # Initialize default values
            visible_fields = []
            key = "laced_column_output"
            titles = []
            title_repeat = 1
            
            # Get titles from output_values
            output_list = self.output_values(True)
            if output_list:
                titles = [item[1] for item in output_list if item[2] == TYPE_TITLE]
                visible_fields = [True] * len(titles)
            
            # Initialize output_title_fields if not exists
            if not hasattr(self, 'output_title_fields'):
                self.output_title_fields = {}
            
            # Initialize key if not exists
            if key not in self.output_title_fields:
                self.output_title_fields[key] = []
            
            # Ensure we have enough fields
            while len(self.output_title_fields[key]) < len(titles):
                self.output_title_fields[key].append(None)
            
            return visible_fields, key, titles, title_repeat
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in output_title_change: {str(e)}")
            return [], None, [], 1

    def closeEvent(self, event):
        """Clear all input values when window is closed"""
        # Clear all input fields
        for key in self.input_dictionary:
            if key in self.design_inputs:
                self.design_inputs[key] = None
        
        # Clear design preferences
        self.design_pref = {}
        
        # Clear output values
        self.result = {}
        
        # Accept the close event
        event.accept()



class LacedColumnWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laced Column")
        # TODO: Add your layout or widget loading here
        # Example: self.setCentralWidget(SomeCustomWidget())




