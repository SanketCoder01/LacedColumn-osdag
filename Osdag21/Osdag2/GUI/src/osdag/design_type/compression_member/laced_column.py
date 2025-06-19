"""
Main module: Design of Compression Member
Sub-module:  Design of column (loaded axially)

@author:Sanket Gaikwad

Reference:
            1) IS 800: 2007 General construction in steel - Code of practice (Third revision)

"""
import logging
import math
import numpy as np
from PyQt5.QtWidgets import QTextEdit, QMessageBox, QLineEdit, QComboBox, QDialog, QVBoxLayout, QListWidget, QDialogButtonBox
from PyQt5.QtCore import QObject, pyqtSignal
from ...Common import *
from ..connection.moment_connection import MomentConnection
from ...utils.common.material import *
from ...utils.common.load import Load
from ...utils.common.component import ISection, Material
from ...utils.common.component import *
from ..member import Member
from ...Report_functions import *
from ...design_report.reportGenerator_latex import CreateLatex
from pylatex.utils import NoEscape
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
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFormLayout, QTableWidget, QTableWidgetItem, QListWidget, QHBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
import sqlite3
from functools import partial
import os
from .LacedColumnDesign import LacedColumnDesign
from ...utils.common.component import Material

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

class QTextEditLogger(QObject, logging.Handler):
    """Custom logging handler that writes to a QTextEdit widget"""
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit

    def emit(self, record):
        msg = self.format(record)
        self.text_edit.append(msg)

class LacedColumn(Member):
    def __init__(self):
        super(LacedColumn, self).__init__()
        self.logger = logging.getLogger('Osdag')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        handler = logging.FileHandler('logging_text.log')
        self.logger.addHandler(handler)
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
        self.module = KEY_DISP_COMPRESSION_LacedColumn
        self.mainmodule = 'Member'
        self.section_designation = None
        self.design_pref_dialog = None
        self.output_title_fields = {}
        self.double_validator = QDoubleValidator()
        self.double_validator.setNotation(QDoubleValidator.StandardNotation)
        self.double_validator.setDecimals(2)
        self.design_pref_dictionary = {
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
        }
        self.design_pref = {}  # Ensure design_pref is always defined
        # Define input line edits for unsupported lengths and axial load
        self.unsupported_length_yy_lineedit = QLineEdit()
        self.unsupported_length_zz_lineedit = QLineEdit()
        self.axial_load_lineedit = QLineEdit()
        # Define combo boxes for dropdowns
        self.material_combo = QComboBox()
        self.connection_combo = QComboBox()
        self.lacing_pattern_combo = QComboBox()
        self.section_profile_combo = QComboBox()
        self.section_designation_combo = QComboBox()

    def validate_inputs(self):
        required_fields = [
            ("Unsupported Length (y-y)", self.unsupported_length_yy_lineedit),
            ("Unsupported Length (z-z)", self.unsupported_length_zz_lineedit),
            ("Axial Load", self.axial_load_lineedit),
        ]
        missing_fields = []
        zero_fields = []
        for label, widget in required_fields:
            if widget is None:
                continue
            text = widget.text().strip()
            if not text:
                missing_fields.append(label)
            elif self.safe_float(text) <= 0:
                zero_fields.append(label)
        if missing_fields:
            QMessageBox.warning(None, "Missing Input",
                "Please fill the following required fields:\n" + "\n".join(missing_fields))
            return False
        if zero_fields:
            QMessageBox.warning(None, "Invalid Input",
                "The following fields must be greater than zero:\n" + "\n".join(zero_fields))
            return False
        return True


    def on_design_button_clicked(self):
        if not self.validate_inputs():
            return 
        try:
            self.design_column()
            self.results()
            self.output_values(self.design_status)
        except Exception as e:
            self.design_status = False
            self.failed_design_dict = {'error': str(e)}
            self.design_log.append(f"Design failed: {e}")

    def safe_float(self, val, default=0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def design_column(self):
        """Perform full welded laced column design per IS800, with all required outputs and checks."""
        self.design_log = []
        self.failed_design_dict = {}
        self.design_status = True
        try:
            # Collect all input values robustly
            material_grade = self.material_combo.currentText() if self.material_combo else "E 250 (Fe 410 W)C"
            print("[DEBUG] material_grade:", material_grade, type(material_grade))
            lacing_pattern = self.lacing_pattern_combo.currentText() if self.lacing_pattern_combo else "Single"
            print("[DEBUG] lacing_pattern:", lacing_pattern, type(lacing_pattern))
            section_profile = self.section_profile_combo.currentText() if self.section_profile_combo else "BackToBackChannelLaced"
            print("[DEBUG] section_profile:", section_profile, type(section_profile))
            section_designation = self.section_designation_combo.currentText() if self.section_designation_combo else ""
            print("[DEBUG] section_designation:", section_designation, type(section_designation))
            unsupported_length_yy = self.safe_float(self.unsupported_length_yy_lineedit.text()) if self.unsupported_length_yy_lineedit else 0
            print("[DEBUG] unsupported_length_yy:", unsupported_length_yy, type(unsupported_length_yy))
            unsupported_length_zz = self.safe_float(self.unsupported_length_zz_lineedit.text()) if self.unsupported_length_zz_lineedit else 0
            print("[DEBUG] unsupported_length_zz:", unsupported_length_zz, type(unsupported_length_zz))
            axial_load = self.safe_float(self.axial_load_lineedit.text()) if self.axial_load_lineedit else 0
            print("[DEBUG] axial_load:", axial_load, type(axial_load))
            weld_size = self.safe_float(str(self.design_pref_dictionary.get(KEY_DISP_LACEDCOL_WELD_SIZE, "5")).replace("mm", ""))
            print("[DEBUG] weld_size:", weld_size, type(weld_size))
            allowable_ur = self.safe_float(self.design_pref_dictionary.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0"))
            print("[DEBUG] allowable_ur:", allowable_ur, type(allowable_ur))

            # Section and material objects
            if section_profile == "BackToBackChannelLaced":
                section_obj = BackToBackChannelLaced(section_designation, material_grade)
            elif section_profile == "FrontToFrontChannelLaced":
                section_obj = ToeToToeLaced(section_designation, material_grade)
            elif section_profile == "DoubleGirderLaced":
                section_obj = DoubleGirderLaced(section_designation, material_grade)
            else:
                section_obj = BackToBackChannelLaced(section_designation, material_grade)
            print("[DEBUG] section_obj.area:", getattr(section_obj, 'area', None))
            print("[DEBUG] section_obj.depth:", getattr(section_obj, 'depth', None))
            print("[DEBUG] section_obj.flange_width:", getattr(section_obj, 'flange_width', None))
            print("[DEBUG] section_obj.web_thickness:", getattr(section_obj, 'web_thickness', None))
            print("[DEBUG] section_obj.rmin:", getattr(section_obj, 'rmin', None))
            material_obj = Material(material_grade, getattr(section_obj, 'web_thickness', 0))
            print("[DEBUG] material_obj.fy:", getattr(material_obj, 'fy', None))
            print("[DEBUG] material_obj.fu:", getattr(material_obj, 'fu', None))
            if (getattr(section_obj, 'area', 0) == 0 or getattr(material_obj, 'fy', 0) == 0 or unsupported_length_yy == 0 or unsupported_length_zz == 0 or axial_load == 0):
                print("[FATAL] One or more critical values are zero! Calculation will not proceed.")
                self.result = {}
                self.design_status = False
                self.failed_design_dict = {'reason': 'Critical input or section/material property is zero. Check your input values and section/material selection.'}
                print("[FATAL] failed_design_dict:", self.failed_design_dict)
                return

            # Prepare input dictionary for LacedColumnDesign with correct keys
            design_dict = {
                KEY_SECTION_SIZE: section_designation,
                KEY_MATERIAL: material_grade,
                KEY_AXIAL_LOAD: axial_load,
                KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY: unsupported_length_yy,
                KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ: unsupported_length_zz,
                'lacing_pattern': lacing_pattern,
                'section_profile': section_profile,
                'weld_size': weld_size,
                'allowable_ur': allowable_ur,
            }
            print("[DEBUG] design_dict passed to LacedColumnDesign:", design_dict)
            lcd = LacedColumnDesign(design_dict)
            lcd_result = lcd.design()
            print("[DEBUG] lcd_result from LacedColumnDesign:", lcd_result)
            # Only set self.result if calculation is successful
            if lcd_result and lcd_result.get(KEY_DESIGN_STATUS, False):
                self.result = lcd_result
                self.design_status = True
            else:
                self.result = {}
                self.design_status = False
                self.failed_design_dict = {'reason': 'Design failed or invalid input', 'lcd_result': lcd_result}
                print("[ERROR] Design failed. failed_design_dict:", self.failed_design_dict)
        except Exception as e:
            self.design_status = False
            self.failed_design_dict = {'error': str(e)}
            self.design_log.append(f"Design failed: {e}")
            print(f"[EXCEPTION] Design failed: {e}")

    def results(self):
        """Process results, handle failures, and set warnings"""
        self.warnings = []
        if hasattr(self, 'ur') and self.ur > float(self.design_pref_dictionary.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0")):
            self.design_status = False
            self.failed_design_dict = {
                'UR': self.ur,
                'fcd': self.fcd,
                'design_strength': getattr(self, 'design_compressive_strength', 0),
                'reason': 'Utilization Ratio exceeds allowable limit.'
            }
            self.warnings.append('Design failed: UR exceeds allowable limit.')
        elif hasattr(self, 'fcd') and self.fcd <= 0:
            self.design_status = False
            self.failed_design_dict = {
                'fcd': self.fcd,
                'reason': 'fcd is non-positive.'
            }
            self.warnings.append('Design failed: fcd is non-positive.')
        else:
            self.design_status = True
        # If failed, show best failed section data if available
        if not self.design_status and self.failed_design_dict:
            self.warnings.append(f"Best failed section data: {self.failed_design_dict}")

    ###############################################
    # Design Preference Functions Start
    ###############################################
    def tab_list(self):
        """Returns list of tabs for design preferences"""
        tabs = []
        
        # Column Section tab
        t1 = (KEY_DISP_COLSEC, TYPE_TAB_1, self.tab_section)
        tabs.append(t1)
        
        # Weld Preferences tab
        t2 = ("Weld Preferences", TYPE_TAB_4, self.all_weld_design_values)
        tabs.append(t2)
        
        return tabs

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
        """
        Returns list of tuples for tab value changes.
        Format: (tab name, [input keys], [output keys], type, function)
        """
        change_tab = []

        # Section material changes
        # Material properties update
        t1 = (KEY_DISP_COLSEC, [KEY_SEC_MATERIAL], [KEY_SEC_FU, KEY_SEC_FY], TYPE_TEXTBOX, self.get_fu_fy_I_section)
        change_tab.append(t1)

        # Section properties update
        t2 = (KEY_DISP_COLSEC, ['Label_1', 'Label_2', 'Label_3', 'Label_4', 'Label_5'],
              ['Label_11', 'Label_12', 'Label_13', 'Label_14', 'Label_15', 'Label_16', 'Label_17', 'Label_18',
               'Label_19', 'Label_20', 'Label_21', 'Label_22', KEY_IMAGE], TYPE_TEXTBOX, self.get_I_sec_properties)
        change_tab.append(t2)

        # Source update
        t3 = (KEY_DISP_COLSEC, [KEY_SECSIZE], [KEY_SOURCE], TYPE_TEXTBOX, self.change_source)
        change_tab.append(t3)

        return change_tab

    def edit_tabs(self):
        return []

    def input_dictionary_design_pref(self):
        """
        Returns list of tuples for design preferences.
        Format: (tab name, input widget type, [list of keys])
        """
        design_input = []

        # Section profile and material
        t1 = (KEY_DISP_COLSEC, TYPE_COMBOBOX, [KEY_SEC_MATERIAL])
        design_input.append(t1)

        # Section properties
        t2 = (KEY_DISP_COLSEC, TYPE_TEXTBOX, [KEY_SEC_FU, KEY_SEC_FY])
        design_input.append(t2)

        # Laced column specific
        t3 = (KEY_DISP_LACEDCOL, TYPE_COMBOBOX, [KEY_LACEDCOL_MATERIAL])
        design_input.append(t3)

        return design_input

    def input_dictionary_without_design_pref(self):
        """
        Returns list of tuples for input dictionary without design preferences.
        Format: [(key, [list of keys], source)]
        """
        design_input = []
        
        # Material input with safe defaults
        t1 = (KEY_MATERIAL, [KEY_SEC_MATERIAL], 'Input Dock')
        design_input.append(t1)

        # Weld preferences with safe defaults
        t2 = (None, [
                KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE,
                KEY_DISP_LACEDCOL_LACING_PROFILE,
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA,
                KEY_DISP_LACEDCOL_ALLOWABLE_UR,
                KEY_DISP_LACEDCOL_BOLT_DIAMETER,
                KEY_DISP_LACEDCOL_WELD_SIZE
            ], '')
        design_input.append(t2)
        t2 = (KEY_SECSIZE, [KEY_SECSIZE], 'Input Dock')
        design_input.append(t2)

        # Column section preferences with safe defaults
        t3 = (KEY_DISP_COLSEC, [
            KEY_DISP_LACEDCOL_MATERIAL,
            KEY_SEC_FU, 
            KEY_SEC_FY
        ], 'Input Dock')
        design_input.append(t3)

        return design_input

    def get_values_for_design_pref(self, key, design_dictionary):
        """
        Returns default values for design preferences when not opened by user.
        """
        if not design_dictionary or design_dictionary.get(KEY_SECSIZE, 'Select Section') == 'Select Section' or \
                design_dictionary.get(KEY_MATERIAL, 'Select Material') == 'Select Material':
            fu = ''
            fy = ''
        else:
            material = Material(design_dictionary[KEY_MATERIAL], 41)
            fu = material.fu
            fy = material.fy

        val = {
            KEY_SECSIZE: 'Select Section',  # Main section size key
            KEY_DISP_LACEDCOL_SEC_SIZE: 'Select Section',  # Keep this for backward compatibility
            KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE: "Angle",
            KEY_DISP_LACEDCOL_LACING_PROFILE: "ISA 40x40x5",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
            KEY_SEC_FU: fu,
            KEY_SEC_FY: fy,
            KEY_SEC_MATERIAL: design_dictionary.get(KEY_MATERIAL, 'Select Material'),
            # Add defaults for any label keys that might be undefined
            'Label_1': '',
            'Label_2': '',
            'Label_3': '',
            'Label_4': '',
            'Label_5': '',
            'Label_11': '',
            'Label_12': '',
            'Label_13': '',
            'Label_14': '',
            'Label_15': '',
            'Label_16': '',
            'Label_17': '',
            'Label_18': '',
            'Label_19': '',
            'Label_20': '',
            'Label_21': '',
            'Label_22': '',
            'Label_HS_1': '',
            'Label_HS_2': '',
            'Label_HS_3': '',
            'Label_HS_11': '',
            'Label_HS_12': '',
            'Label_HS_13': '',
            'Label_HS_14': '',
            'Label_HS_15': '',
            'Label_HS_16': '',
            'Label_HS_17': '',
            'Label_HS_18': '',
            'Label_HS_19': '',
            'Label_HS_20': '',
            'Label_HS_21': '',
            'Label_HS_22': '',
            'Label_CHS_1': '',
            'Label_CHS_2': '',
            'Label_CHS_3': '',
            'Label_CHS_11': '',
            'Label_CHS_12': '',
            'Label_CHS_13': ''
        }[key]

        return val

    def get_lacing_profiles(self, *args):
        """
        Returns lacing profile options based on selected lacing pattern.
        """
        if not args or not args[0]:
            return connectdb('Angles', call_type="popup")

        pattern = args[0]
        if pattern == "Single Lacing":
            return connectdb('Angles', call_type="popup")
        elif pattern == "Double Lacing":
            return connectdb('Angles', call_type="popup")
        elif pattern == "Flat Bar":
            return connectdb('Channels', call_type="popup")
        else:
            return []

    ####################################
    # Design Preference Functions End
    ####################################

    # Setting up logger and Input and Output Docks
    ####################################
    def module_name(self):
        return KEY_DISP_LACEDCOL

    @staticmethod
    def set_osdaglogger(text_edit):
        """Set up the logger for the application"""
        logger = logging.getLogger('osdag')
        logger.setLevel(logging.INFO)
        
        # Create a handler that writes to the text edit widget
        handler = QTextEditLogger(text_edit)
        handler.setLevel(logging.INFO)
        
        # Create a formatter
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        
        # Add the handler to the logger
        logger.addHandler(handler)
        
        return logger

    def customized_input(self):

        c_lst = []

        t1 = (KEY_SECSIZE, self.fn_profile_section)
        c_lst.append(t1)

        return c_lst

    def input_values(self, ui_self=None):
        """
        Returns list of tuples for input values.
        Format: (key, display key, type, values, required, validator)
        """
        options_list = []
        
        # Module title and name
        options_list.append((KEY_DISP_LACEDCOL, "Laced Column", TYPE_MODULE, [], True, 'No Validator'))

        # Section
        options_list.append(("title_Section ", "Section Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_SEC_PROFILE, KEY_DISP_LACEDCOL_SEC_PROFILE, TYPE_COMBOBOX, KEY_LACEDCOL_SEC_PROFILE_OPTIONS, True, 'No Validator'))
        options_list.append((KEY_SECSIZE, KEY_DISP_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, KEY_LACEDCOL_SEC_SIZE_OPTIONS, True, 'No Validator'))

        # Material
        options_list.append(("title_Material", "Material Properties", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_MATERIAL, KEY_DISP_MATERIAL, TYPE_COMBOBOX, VALUES_MATERIAL, True, 'No Validator'))

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



    def fn_profile_section(self, *args):
        """
        Returns available sections based on selected profile type, fetched from the database.
        """
        try:
            if not args:
                return ['All', 'Customized']
            value = args[0]
            if value == "Customized":
                # self.show_custom_section_dialog()  # Commented out: method does not exist
                return [self.section_designation] if self.section_designation else ['Customized']
            if value == 'Angle':
                return connectdb('Angles', call_type="popup")
            elif value == 'Channel':
                return connectdb('Channels', call_type="popup")
            elif value in ['Customized', '2-channels Back-to-Back', '2-channels Toe-to-Toe', '2-Girders']:
                # self.show_custom_section_dialog()  # Commented out: method does not exist
                return [self.section_designation] if self.section_designation else ['Customized']
            return ['All', 'Customized']
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in fn_profile_section: {str(e)}")
            return []

    def fn_end1_end2(self, end1=None):
        """Get end2 options based on end1 condition"""
        if end1 is None:
            return []
            
        print("end1 is {}".format(end1))
        if end1 == 'Fixed':
            return VALUES_END2
        elif end1 == 'Free':
            return ['Fixed']
        elif end1 == 'Hinged':
            return ['Fixed', 'Hinged', 'Roller']
        elif end1 == 'Roller':
            return ['Fixed', 'Hinged']
        return []

    def fn_end1_image(self, end1=None):
        """Get image path for end1 condition"""
        if end1 is None:
            return ""
            
        if end1 == 'Fixed':
            return str(files("osdag.data.ResourceFiles.images").joinpath("6.RRRR.PNG"))
        elif end1 == 'Free':
            return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF.PNG"))
        elif end1 == 'Hinged':
            return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF.PNG"))
        elif end1 == 'Roller':
            return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR.PNG"))
        return ""

    def fn_end2_image(self, end1=None, end2=None):
        """Get image path for end1 and end2 conditions"""
        if end1 is None or end2 is None:
            return ""
            
        print("end 1 and end 2 are {}".format(end1, end2))

        if end1 == 'Fixed':
            if end2 == 'Fixed':
                return str(files("osdag.data.ResourceFiles.images").joinpath("6.RRRR.PNG"))
            elif end2 == 'Free':
                return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF_rotated.PNG"))
            elif end2 == 'Hinged':
                return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF_rotated.PNG"))
            elif end2 == 'Roller':
                return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR_rotated.PNG"))
        elif end1 == 'Free':
            return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF.PNG"))
        elif end1 == 'Hinged':
            if end2 == 'Fixed':
                return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF.PNG"))
            elif end2 == 'Hinged':
                return str(files("osdag.data.ResourceFiles.images").joinpath("3.RFRF.PNG"))
            elif end2 == 'Roller':
                return str(files("osdag.data.ResourceFiles.images").joinpath("2.FRFR_rotated.PNG"))
        elif end1 == 'Roller':
            if end2 == 'Fixed':
                return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR.PNG"))
            elif end2 == 'Hinged':
                return str(files("osdag.data.ResourceFiles.images").joinpath("2.FRFR.PNG"))
        return ""

    def input_value_changed(self):
        """
        Returns list of tuples for input value changes.
        Format: ([input keys], output key, type, function)
        """
        lst = []
        # Section profile changes - This triggers the popup when "Customized" is selected
        t1 = ([KEY_SEC_PROFILE], KEY_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, self.fn_profile_section)
        lst.append(t1)
        # Material changes
        t2 = ([KEY_MATERIAL], KEY_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t2)
        # Length changes
        t3 = ([KEY_LYY], KEY_END_COND_YY, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t3)
        t4 = ([KEY_LZZ], KEY_END_COND_ZZ, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t4)
        return lst

    def output_values(self, flag):
        """
        Returns list of tuples to be displayed in the UI (Output Dock)
        Format: (key, display_key, type, value, required)
        """
        from ...Common import (
            KEY_SECSIZE, KEY_MATERIAL,
            KEY_EFF_LEN_YY, KEY_EFF_LEN_ZZ,
            KEY_END_COND_YY_1, KEY_END_COND_YY_2, KEY_END_COND_ZZ_1, KEY_END_COND_ZZ_2,
            KEY_SLENDER_YY, KEY_SLENDER_ZZ,
            KEY_FCD, KEY_DESIGN_COMPRESSIVE,
            KEY_CHANNEL_SPACING,
            KEY_TIE_PLATE_D, KEY_TIE_PLATE_T, KEY_TIE_PLATE_L,
            KEY_LACING_SPACING, KEY_LACING_ANGLE, KEY_LACING_FORCE,
            KEY_WELD_LENGTH, KEY_BOLT_COUNT, TYPE_TITLE, TYPE_TEXTBOX
        )
        out_list = []

        # Print the result dict
        print("[DEBUG] Output values (self.result):", self.result)

        def safe_display(val):
            if val is None or (isinstance(val, (int, float)) and abs(val) < 1e-6):
                return "N/A"
            return round(val, 2) if isinstance(val, float) else val

        # Section and Material Details
        out_list.append((None, "Section and Material Details", TYPE_TITLE, None, True))
        out_list.append((KEY_SECSIZE, "Section Size", TYPE_TEXTBOX, getattr(self, 'section_designation', '') if flag else '', True))
        out_list.append((KEY_MATERIAL, "Material Grade", TYPE_TEXTBOX, self.material.get('grade', '') if getattr(self, 'material', None) else '', True))

        # Effective Lengths
        out_list.append((None, "Effective Lengths", TYPE_TITLE, None, True))
        out_list.append((KEY_EFF_LEN_YY, "Effective Length (YY)", TYPE_TEXTBOX, safe_display(self.result.get('effective_length_yy')) if flag else '', True))
        out_list.append((KEY_EFF_LEN_ZZ, "Effective Length (ZZ)", TYPE_TEXTBOX, safe_display(self.result.get('effective_length_zz')) if flag else '', True))

        # End Conditions
        out_list.append((None, "End Conditions", TYPE_TITLE, None, True))
        out_list.append((KEY_END_COND_YY_1, "End Condition YY-1", TYPE_TEXTBOX, self.result.get('end_condition_yy_1', '') if flag else '', True))
        out_list.append((KEY_END_COND_YY_2, "End Condition YY-2", TYPE_TEXTBOX, self.result.get('end_condition_yy_2', '') if flag else '', True))
        out_list.append((KEY_END_COND_ZZ_1, "End Condition ZZ-1", TYPE_TEXTBOX, self.result.get('end_condition_zz_1', '') if flag else '', True))
        out_list.append((KEY_END_COND_ZZ_2, "End Condition ZZ-2", TYPE_TEXTBOX, self.result.get('end_condition_zz_2', '') if flag else '', True))

        # Slenderness Ratios
        out_list.append((None, "Slenderness Ratios", TYPE_TITLE, None, True))
        out_list.append((KEY_SLENDER_YY, "Slenderness Ratio (YY)", TYPE_TEXTBOX, safe_display(self.result.get('slenderness_yy')) if flag else '', True))
        out_list.append((KEY_SLENDER_ZZ, "Slenderness Ratio (ZZ)", TYPE_TEXTBOX, safe_display(self.result.get('slenderness_zz')) if flag else '', True))

        # Design Values
        out_list.append((None, "Design Values", TYPE_TITLE, None, True))
        out_list.append((KEY_FCD, "Design Compressive Stress (fcd)", TYPE_TEXTBOX, safe_display(self.result.get('fcd')) if flag else '', True))
        out_list.append((KEY_DESIGN_COMPRESSIVE, "Design Compressive Strength", TYPE_TEXTBOX, safe_display(self.result.get('design_compressive_strength')) if flag else '', True))

        # Channel Spacing
        out_list.append((None, "Channel Spacing", TYPE_TITLE, None, True))
        out_list.append((KEY_CHANNEL_SPACING, "Spacing Between Channels", TYPE_TEXTBOX, safe_display(self.result.get('channel_spacing')) if flag else '', True))

        # Tie Plate Details
        out_list.append((None, "Tie Plate Details", TYPE_TITLE, None, True))
        out_list.append((KEY_TIE_PLATE_D, "Overall Depth (D)", TYPE_TEXTBOX, safe_display(self.result.get('tie_plate_depth')) if flag else '', True))
        out_list.append((KEY_TIE_PLATE_T, "Thickness (t)", TYPE_TEXTBOX, safe_display(self.result.get('tie_plate_thickness')) if flag else '', True))
        out_list.append((KEY_TIE_PLATE_L, "Length (L)", TYPE_TEXTBOX, safe_display(self.result.get('tie_plate_length')) if flag else '', True))

        # Lacing Details
        out_list.append((None, "Lacing Details", TYPE_TITLE, None, True))
        out_list.append((KEY_LACING_SPACING, "Lacing Spacing", TYPE_TEXTBOX, safe_display(self.result.get('lacing_spacing')) if flag else '', True))
        out_list.append((KEY_LACING_ANGLE, "Lacing Angle", TYPE_TEXTBOX, safe_display(self.result.get('lacing_angle')) if flag else '', True))
        out_list.append((KEY_LACING_FORCE, "Force on Lacing", TYPE_TEXTBOX, safe_display(self.result.get('lacing_force')) if flag else '', True))
        out_list.append((KEY_LACING_SECTION_DIM, "Lacing Section Dimensions", TYPE_TEXTBOX, self.result.get('lacing_section_dim', '') if flag else '', True))

        # Connection Details
        out_list.append((None, "Connection Details", TYPE_TITLE, None, True))
        if getattr(self, 'weld_type', '') == 'Welded':
            out_list.append((KEY_WELD_LENGTH, "Required Weld Length", TYPE_TEXTBOX, safe_display(self.result.get('weld_length')) if flag else '', True))
        else:
            out_list.append((KEY_BOLT_COUNT, "Number of Bolts Required", TYPE_TEXTBOX, self.result.get('bolt_count', 0) if flag else '', True))

        return out_list

    def func_for_validation(self, design_dictionary):
        print(f"func_for_validation here")
        all_errors = []
        self.design_status = False
        flag = False
        option_list = self.input_values(self)
        missing_fields_list = []
        # Only check TYPE_TEXTBOX (QLineEdit) fields for required input
        for option in option_list:
            if option[2] == TYPE_TEXTBOX:
                if design_dictionary[option[0]] == '':
                    missing_fields_list.append(option[1])
                    print(option[1], option[2], option[0], design_dictionary[option[0]])
        # Do NOT check TYPE_COMBOBOX fields for required input!
        # (Removed ComboBox required check to prevent pop-up for Material, Lacing Pattern, Type of Connection)

        if len(missing_fields_list) > 0:
            print(design_dictionary)
            error = self.generate_missing_fields_error_string(missing_fields_list)
            all_errors.append(error)
            # flag = False
        else:
            flag = True

        if flag:
            print(f"\n design_dictionary{design_dictionary}")
            self.set_input_values(design_dictionary)
            if self.design_status ==False and len(self.failed_design_dict)>0:
                logger.error(
                    "Design Failed, Check Design Report"
                )
                return # ['Design Failed, Check Design Report'] @TODO
            elif self.design_status:
                pass
            else:
                logger.error(
                    "Design Failed. Slender Sections Selected"
                )
                return # ['Design Failed. Slender Sections Selected']
        else:
            return all_errors

    def get_3d_components(self):

        components = []

        t1 = ('Model', self.call_3DModel)
        components.append(t1)

        # t3 = ('Column', self.call_3DColumn)
        # components.append(t3)

        return components

    # warn if a beam of older version of IS 808 is selected
    def warn_text(self):
        """ give logger warning when a beam from the older version of IS 808 is selected """
        global logger
        red_list = red_list_function()

        if (self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[0]):  # Beams and Columns
            for section in self.sec_list:
                if section in red_list:
                    logger.warning(" : You are using a section ({}) (in red color) that is not available in latest version of IS 808".format(section))

    # Setting inputs from the input dock GUI
    def set_input_values(self, design_dictionary):
        # section properties
        self.module = design_dictionary[KEY_DISP_LACEDCOL]
        self.mainmodule = 'Columns with known support conditions'
        self.sec_profile = design_dictionary.get(KEY_LACEDCOL_SEC_PROFILE, "")
        self.sec_list = design_dictionary.get(KEY_LACEDCOL_SEC_SIZE, [])
        self.material = design_dictionary.get(KEY_LACEDCOL_MATERIAL, "")
        self.length_zz = float(design_dictionary.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, 0))
        self.length_yy = float(design_dictionary.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0))
        self.end_1_z = design_dictionary.get(KEY_END_COND_ZZ_1, "")
        self.end_2_z = design_dictionary.get(KEY_END_COND_ZZ_2, "")
        self.end_1_y = design_dictionary.get(KEY_END_COND_YY_1, "")
        self.end_2_y = design_dictionary.get(KEY_END_COND_YY_2, "")
        self.load = Load(
            axial_force=design_dictionary.get(KEY_AXIAL_LOAD, 0),
            shear_force=0.0, moment=0.0, moment_minor=0.0, unit_kNm=True
        )
        self.allowable_utilization_ratio = float(design_dictionary.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, 1.0))
        self.effective_area_factor = float(design_dictionary.get(KEY_LACEDCOL_EFFECTIVE_AREA, 1.0))
        #TODO: @danish this should be handeled dynamically at run-time
        try:
            self.optimization_parameter = design_dictionary[KEY_OPTIMIZATION_PARA]
        except:
            self.optimization_parameter = 'Utilization Ratio'
        try:
            self.steel_cost_per_kg = float(design_dictionary[KEY_STEEL_COST])
        except:
            self.steel_cost_per_kg = 50

        self.allowed_sections = ['Plastic', 'Compact', 'Semi-Compact', 'Slender']

        print(self.allowed_sections)
        print("==================")
        print(self.module)
        print(self.sec_list)
        print(self.sec_profile)
        print(self.material)
        print(self.length_yy)
        print(self.length_zz)
        print(self.load)
        print(self.end_1_z, self.end_2_z)
        print(self.end_1_y, self.end_2_y)
        print("==================")

        # safety factors
        self.gamma_m0 = IS800_2007.cl_5_4_1_Table_5["gamma_m0"]["yielding"]
        self.material_property = Material(material_grade=self.material, thickness=0)

        # initialize the design status
        self.design_status_list = []
        self.design_status = False
        self.failed_design_dict = {}
        flag = self.section_classification()
        print(flag)
        if flag:
            self.design_column()
            self.results()
        print(f"Here[Column/set_input_values]")

    # Simulation starts here
    def section_classification(self):
        """ Classify the sections based on Table 2 of IS 800:2007 """
        local_flag = True
        self.input_section_list = []
        self.input_section_classification = {} 

        for section in self.sec_list:
            trial_section = section.strip("'")

            # fetching the section properties
            if self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[0]:  # 2- CHANNELS- BACK-TO-BACK
                try:
                    result = BackToBackChannelLaced(designation=trial_section, material_grade=self.material)
                except:
                    result = BackToBackChannelLaced(designation=trial_section, material_grade=self.material)
                self.section_property = result
            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[1]:  # 2- CHANNELS-TOE-TO-TOE
                try:
                    result = ToeToToeLaced(designation=trial_section, material_grade=self.material)
                except:
                    result = ToeToToeLaced(designation=trial_section, material_grade=self.material)
                self.section_property = result
            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[2]:  # 2-GRIDERS
                self.section_property = DoubleGirderLaced(designation=trial_section, material_grade=self.material)
            else:
                self.section_property = DoubleGirderLaced(designation=trial_section, material_grade=self.material)

            # updating the material property based on thickness of the thickest element
            self.material_property.connect_to_database_to_get_fy_fu(self.material,
                                                                    max(self.section_property.flange_thickness, self.section_property.web_thickness))

            # section classification
            if (self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[0]):  # 2-Channels-Back-to-Back

                if self.section_property.type == 'Rolled':
                    self.flange_class = IS800_2007.Table2_i((self.section_property.flange_width / 2), self.section_property.flange_thickness,
                                                            self.material_property.fy, self.section_property.type)[0]
                else:
                    self.flange_class = IS800_2007.Table2_i(((self.section_property.flange_width / 2) - (self.section_property.web_thickness / 2)),
                                                            self.section_property.flange_thickness, self.material_property.fy,
                                                            self.section_property.type)[0]

                self.web_class = IS800_2007.Table2_iii((self.section_property.depth - (2 * self.section_property.flange_thickness)),
                                                       self.section_property.web_thickness, self.material_property.fy,
                                                       classification_type='Axial compression')
                web_ratio = (self.section_property.depth - 2 * (
                            self.section_property.flange_thickness + self.section_property.root_radius)) / self.section_property.web_thickness
                flange_ratio = self.section_property.flange_width / 2 / self.section_property.flange_thickness

            elif (self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[1]):  # 2- Channels Toe-to-Toe
                self.flange_class = IS800_2007.Table2_iii((self.section_property.depth - (2 * self.section_property.flange_thickness)),
                                                          self.section_property.flange_thickness, self.material_property.fy,
                                                          classification_type='Axial compression')
                self.web_class = self.flange_class
                web_ratio = (self.section_property.depth - 2 * (
                            self.section_property.flange_thickness + self.section_property.root_radius)) / self.section_property.web_thickness
                flange_ratio = self.section_property.flange_width / 2 / self.section_property.flange_thickness

            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[2]:  # 2-Girders
                self.flange_class = IS800_2007.Table2_x(self.section_property.out_diameter, self.section_property.flange_thickness,
                                                        self.material_property.fy, load_type='axial compression')
                self.web_class = self.flange_class  #Why?
                web_ratio = (self.section_property.depth - 2 * (
                            self.section_property.flange_thickness + self.section_property.root_radius)) / self.section_property.web_thickness
                flange_ratio = self.section_property.flange_width / 2 / self.section_property.flange_thickness
                # print(f"self.web_class{self.web_class}")
            
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

            # 2.2 - Effective length
            self.effective_length_zz = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_zz,
                end_1=self.end_1_z,
                end_2=self.end_2_z)

            # self.effective_length_yy = temp_yy * IS800_2007.cl_7_2_4_effective_length_of_truss_compression_members(
            #     self.length_yy,
            #     self.sec_profile) / self.length_yy  # mm
            # print(f"self.effective_length {self.effective_length_yy} ")

            self.effective_length_yy = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_yy,
                end_1=self.end_1_y,
                end_2=self.end_2_y)

            # self.effective_length_zz = temp_yy * IS800_2007.cl_7_2_4_effective_length_of_truss_compression_members(
            #     self.length_yy,
            #     self.sec_profile) / self.length_yy  # mm
            # print(f"self.effective_length {self.effective_length_zz} ")

            # print("+++++++++++++++++++++++++++++++++++++++++++++++")
            # print(self.end_1_z)
            # print(self.end_2_z)
            # print(self.end_1_y)
            # print(self.end_2_y)
            #
            # print(f"factor y-y {self.effective_length_yy/self.length_yy}")
            # print(f"factor z-z {self.effective_length_yy / self.length_yy}")
            # print("+++++++++++++++++++++++++++++++++++++++++++++++")

            # 2.3 - Effective slenderness ratio
            self.effective_sr_zz = self.effective_length_zz / self.section_property.rad_of_gy_z
            self.effective_sr_yy = self.effective_length_yy / self.section_property.rad_of_gy_y

            limit = IS800_2007.cl_3_8_max_slenderness_ratio(1)
            if self.effective_sr_zz > limit and self.effective_sr_yy > limit:
                logger.warning("Length provided is beyond the limit allowed. [Reference: Cl 3.8, IS 800:2007]")
                logger.error("Cannot compute. Given Length does not pass.")
                local_flag = False
            #else:
            #    logger.info("Length provided is within the limit allowed. [Reference: Cl 3.8, IS 800:2007]")
                

            # if len(self.allowed_sections) == 0:
            #     logger.warning("Select at-least one type of section in the design preferences tab.")
            #     logger.error("Cannot compute. Selected section classification type is Null.")
            #     self.design_status = False
            #     self.design_status_list.append(self.design_status)

            #TODO: @danish check this part
            if self.section_class in self.allowed_sections:
                self.input_section_list.append(trial_section)
                self.input_section_classification.update({trial_section: [self.section_class, self.flange_class, self.web_class, flange_ratio, web_ratio]})
            # print(f"self.section_class{self.section_class}")


        return local_flag

    def design(self):
        """
        Perform the laced column design calculations.
        Returns True if design is successful, False otherwise.
        """
        try:
            # Create design dictionary from preferences
            design_dict = {
                KEY_SEC_MATERIAL: self.design_pref.get(KEY_SEC_MATERIAL, "E 250 (Fe 410 W)C"),
                KEY_CONN_TYPE: self.design_pref.get(KEY_CONN_TYPE, "Welded"),
                KEY_LACING_PATTERN: self.design_pref.get(KEY_LACING_PATTERN, "Single"),
                KEY_SEC_PROFILE: self.design_pref.get(KEY_SEC_PROFILE, "Angle"),
                KEY_SECSIZE: self.design_pref.get(KEY_SECSIZE, ""),
                KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY: self.design_pref.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0),
                KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ: self.design_pref.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, 0),
                KEY_AXIAL_LOAD: self.design_pref.get(KEY_AXIAL_LOAD, 0)
            }

            # Create LacedColumnDesign instance
            self.designer = LacedColumnDesign(design_dict)
            
            # Perform design calculations
            self.design_status = self.designer.design()
            
            if self.design_status:
                # Store results
                self.result = self.designer.result
                return True
            else:
                return False

        except Exception as e:
            print(f"Error in design: {str(e)}")
            return False

    def get_design_pref_dictionary(self):
        """
        Returns the design preferences dictionary.
        """
        return self.design_pref_dictionary

    def set_design_pref_dictionary(self, pref_dict):
        """
        Updates the design preferences dictionary.
        Args:
            pref_dict: Dictionary containing new design preferences
        """
        if isinstance(pref_dict, dict):
            self.design_pref_dictionary.update(pref_dict)

    def show_design_preferences(self):
        try:
            # If dialog already exists, just return
            if self.design_pref_dialog is not None:
                self.design_pref_dialog.show()
                return True
                
            # Create new dialog
            from ...gui.UI_DESIGN_PREFERENCE import DesignPreferences
            from PyQt5.QtWidgets import QDialog
            from PyQt5.QtCore import Qt
            
            class DesignPreferencesDialog(DesignPreferences, QDialog):
                def __init__(self, parent, *args, **kwargs):
                    QDialog.__init__(self, parent)
                    DesignPreferences.__init__(self, parent, *args, **kwargs)
            
            self.design_pref_dialog = DesignPreferencesDialog(self, None, {})
            self.design_pref_dialog.setWindowFlags(self.design_pref_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            
            # Set validators for numeric fields
            for key in [KEY_CONNECTOR_FU, KEY_CONNECTOR_FY_20, KEY_CONNECTOR_FY_20_40, KEY_CONNECTOR_FY_40]:
                if hasattr(self.design_pref_dialog, key):
                    field = getattr(self.design_pref_dialog, key)
                    if isinstance(field, QLineEdit):
                        field.setValidator(self.double_validator)
            
            # Connect dialog signals
            self.design_pref_dialog.accepted.connect(self.cleanup_design_pref_dialog)
            self.design_pref_dialog.rejected.connect(self.cleanup_design_pref_dialog)
            
            self.design_pref_dialog.show()
            return True
            
        except Exception as e:
            logger = self.set_osdaglogger(None)
            logger.error(f"Error showing design preferences: {str(e)}")
            return False

    def cleanup_design_pref_dialog(self):
        """Clean up the design preferences dialog when it's closed"""
        if self.design_pref_dialog is not None:
            self.design_pref_dialog.close()
            self.design_pref_dialog = None
            self.design_pref_dictionary = {
                KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
                KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
                KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
            }

    def get_end_conditions(self, *args):
        """
        Returns available end conditions for the laced column.
        """
        return ['Fixed', 'Hinged', 'Free']

    def tab_elements(self, input_dictionary=None):
        """Returns list of elements for the weld preferences tab"""
        # Defensive: ensure input_dictionary is a dict or None
        if input_dictionary is not None and not isinstance(input_dictionary, dict):
            raise ValueError("input_dictionary must be a dict or None")
        elements = []
        # Lacing profile type
        elements.append((KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE, "Lacing Profile Type", TYPE_COMBOBOX, 
                        ["Single Lacing", "Double Lacing"], "Single Lacing"))
        # Lacing profile
        elements.append((KEY_DISP_LACEDCOL_LACING_PROFILE, "Lacing Profile", TYPE_COMBOBOX,
                        ["Angle", "Channel"], "Angle"))
        # Effective area factor
        elements.append((KEY_DISP_LACEDCOL_EFFECTIVE_AREA, "Effective Area Factor", TYPE_TEXTBOX,
                        [], "0.75"))
        # Allowable UR
        elements.append((KEY_DISP_LACEDCOL_ALLOWABLE_UR, "Allowable UR", TYPE_TEXTBOX,
                        [], "0.8"))
        # Bolt diameter
        elements.append((KEY_DISP_LACEDCOL_BOLT_DIAMETER, "Bolt Diameter (mm)", TYPE_TEXTBOX,
                        [], "16"))
        # Weld size
        elements.append((KEY_DISP_LACEDCOL_WELD_SIZE, "Weld Size (mm)", TYPE_TEXTBOX,
                        [], "6"))
        return elements

    @staticmethod
    def cl_7_1_2_1_phi_value(alpha, lambda_nondim):
        """IS 800:2007 cl. 7.1.2.1: phi value for buckling curve"""
        return 0.5 * (1 + alpha * (lambda_nondim - 0.2) + lambda_nondim ** 2)

    @staticmethod
    def cl_7_1_2_1_chi(phi, lambda_nondim):
        """IS 800:2007 cl. 7.1.2.1: stress reduction factor chi"""
        return 1.0 / (phi + (phi ** 2 - lambda_nondim ** 2) ** 0.5)

    @staticmethod
    def cl_7_1_2_1_fcd(chi, fy, gamma_m0):
        """IS 800:2007 cl. 7.1.2.1: design compressive stress fcd"""
        return chi * fy / gamma_m0

    @staticmethod
    def cl_7_6_2_1_transverse_shear(axial_load, lacing_angle_deg):
        """IS 800:2007 cl. 7.6.2.1: transverse shear in lacing system"""
        # 2.5% of axial load, resolved along lacing
        return 0.025 * axial_load / math.sin(math.radians(lacing_angle_deg))

    @staticmethod
    def cl_7_6_3_axial_force_on_lacing(transverse_shear, lacing_angle_deg):
        """IS 800:2007 cl. 7.6.3: axial force in lacing bar"""
        return transverse_shear / math.cos(math.radians(lacing_angle_deg))

    @staticmethod
    def cl_7_6_5_effective_length_of_lacing(lacing_spacing, lacing_angle_deg):
        """IS 800:2007 cl. 7.6.5: effective length of lacing bar"""
        return lacing_spacing / math.sin(math.radians(lacing_angle_deg))

    @staticmethod
    def cl_7_6_5_check_slenderness_lacing(effective_length, rmin):
        """IS 800:2007 cl. 7.6.5: slenderness of lacing bar (should be <= 145)"""
        return effective_length / rmin

    def perform_laced_column_design(self):
        self.design_log = []
        self.output_values_dict = {}
        self.failed_design_dict = {}
        self.design_status = True
        try:
            # 1. Collect all input values
            material_grade = self.material_combo.currentText() if self.material_combo else "E 250 (Fe 410 W)C"
            lacing_pattern = self.lacing_pattern_combo.currentText() if self.lacing_pattern_combo else "Single"
            section_profile = self.section_profile_combo.currentText() if self.section_profile_combo else "Angle"
            section_designation = self.section_designation_combo.currentText() if self.section_designation_combo else ""
            unsupported_length_yy = float(self.unsupported_length_yy_lineedit.text()) if self.unsupported_length_yy_lineedit else 0
            unsupported_length_zz = float(self.unsupported_length_zz_lineedit.text()) if self.unsupported_length_zz_lineedit else 0
            axial_load = float(self.axial_load_lineedit.text()) if self.axial_load_lineedit else 0
            weld_size = self.safe_float(str(self.design_pref_dictionary.get(KEY_DISP_LACEDCOL_WELD_SIZE, "5")).replace("mm", ""))
            allowable_ur = self.safe_float(self.design_pref_dictionary.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0"))
            # Section and material objects
            if section_profile == "BackToBackChannelLaced":
                section_obj = BackToBackChannelLaced(section_designation, material_grade)
            elif section_profile == "FrontToFrontChannelLaced":
                section_obj = ToeToToeLaced(section_designation, material_grade)
            elif section_profile == "DoubleGirderLaced":
                section_obj = DoubleGirderLaced(section_designation, material_grade)
            else:
                section_obj = BackToBackChannelLaced(section_designation, material_grade)
            material_obj = Material(material_grade, section_obj.web_thickness)
            self.design_log.append(f"Section: {section_designation}, Material: {material_grade}")
            # 2. Effective lengths (IS800 cl. 7.2.2)
            self.length_yy = unsupported_length_yy
            self.length_zz = unsupported_length_zz
            self.design_log.append(f"Effective Length yy: {self.length_yy} mm, zz: {self.length_zz} mm")
            # 3. Slenderness ratios
            self.slenderness_yy = self.length_yy / section_obj.rmin if section_obj.rmin else 0
            self.slenderness_zz = self.length_zz / section_obj.rmin if section_obj.rmin else 0
            self.design_log.append(f"Slenderness Ratio yy: {self.slenderness_yy:.2f}, zz: {self.slenderness_zz:.2f}")
            # 4. Buckling curve and imperfection factor (IS800 cl. 7.1.2.2)
            alpha = 0.49  # Example for curve b, update as needed
            lambda_yy = self.slenderness_yy / (math.pi * math.sqrt(material_obj.E / material_obj.fy)) if material_obj.fy else 0
            lambda_zz = self.slenderness_zz / (math.pi * math.sqrt(material_obj.E / material_obj.fy)) if material_obj.fy else 0
            phi_yy = self.cl_7_1_2_1_phi_value(alpha, lambda_yy)
            phi_zz = self.cl_7_1_2_1_phi_value(alpha, lambda_zz)
            chi_yy = self.cl_7_1_2_1_chi(phi_yy, lambda_yy)
            chi_zz = self.cl_7_1_2_1_chi(phi_zz, lambda_zz)
            self.fcd_yy = self.cl_7_1_2_1_fcd(chi_yy, material_obj.fy, 1.1)
            self.fcd_zz = self.cl_7_1_2_1_fcd(chi_zz, material_obj.fy, 1.1)
            self.fcd = min(self.fcd_yy, self.fcd_zz)
            self.design_log.append(f"fcd_yy: {self.fcd_yy:.2f} MPa, fcd_zz: {self.fcd_zz:.2f} MPa, fcd: {self.fcd:.2f} MPa")
            # 5. Design compressive strength
            self.design_compressive_strength = self.fcd * section_obj.area / 1000  # kN
            self.design_log.append(f"Design compressive strength: {self.design_compressive_strength:.2f} kN")
            # 6. Utilization ratio
            self.ur = axial_load / self.design_compressive_strength if self.design_compressive_strength else 0
            self.design_log.append(f"Utilization Ratio (UR): {self.ur:.3f}")
            if self.ur > allowable_ur:
                self.design_status = False
                self.failed_design_dict = {
                    'UR': self.ur,
                    'fcd': self.fcd,
                    'design_compressive_strength': self.design_compressive_strength,
                    'reason': 'Utilization Ratio exceeds allowable limit.'
                }
                self.design_log.append("Design failed: UR exceeds allowable limit.")
                return
            # 7. Lacing calculations (IS800 cl. 7.6)
            lacing_angle = 45  # Example, should be user input or calculated
            lacing_spacing = 300  # Example, should be user input or calculated
            self.lacing_angle = lacing_angle
            self.lacing_spacing = lacing_spacing
            transverse_shear = self.cl_7_6_2_1_transverse_shear(axial_load, lacing_angle)
            self.lacing_force = self.cl_7_6_3_axial_force_on_lacing(transverse_shear, lacing_angle)
            self.lacing_length = self.cl_7_6_5_effective_length_of_lacing(lacing_spacing, lacing_angle)
            self.lacing_slenderness = self.cl_7_6_5_check_slenderness_lacing(self.lacing_length, section_obj.rmin)
            self.design_log.append(f"Lacing force: {self.lacing_force:.2f} kN, Lacing length: {self.lacing_length:.2f} mm, Lacing slenderness: {self.lacing_slenderness:.2f}")
            # 8. Weld size and length (simplified, update as per IS800 weld design)
            self.weld_length = 2 * self.lacing_length  # Example
            self.weld_size = weld_size
            self.design_log.append(f"Weld length: {self.weld_length:.2f} mm, Weld size: {self.weld_size}")
            # 9. Store all outputs in output_values_dict
            self.output_values_dict = {
                'EFFECTIVE_LENGTH_YY': self.length_yy,
                'EFFECTIVE_LENGTH_ZZ': self.length_zz,
                'SLENDERNESS_YY': self.slenderness_yy,
                'SLENDERNESS_ZZ': self.slenderness_zz,
                'FCD': self.fcd,
                'DESIGN_COMPRESSIVE_STRENGTH': self.design_compressive_strength,
                'UR': self.ur,
                'LACING_FORCE': self.lacing_force,
                'LACING_LENGTH': self.lacing_length,
                'LACING_SLENDERNESS': self.lacing_slenderness,
                'WELD_LENGTH': self.weld_length,
                'WELD_SIZE': self.weld_size,
                'LACING_ANGLE': self.lacing_angle,
                'LACING_SPACING': self.lacing_spacing
            }
        except Exception as e:
            self.design_status = False
            self.failed_design_dict = {'error': str(e)}
            self.design_log.append(f"Design failed: {e}")
