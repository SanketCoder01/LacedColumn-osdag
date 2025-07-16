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
from PyQt5.QtWidgets import QTextEdit, QMessageBox, QLineEdit, QComboBox, QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QPixmap
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
from ...Common import KEY_LACING_SECTION_DIM
import logging
import math
import numpy as np
from ..connection.moment_connection import MomentConnection
from ...utils.common.material import *
from ...utils.common.load import Load
from ...utils.common.component import ISection, Material
from ...utils.common.component import *
from ..member import Member
from ...Report_functions import *
from ...design_report.reportGenerator_latex import CreateLatex

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
        super().__init__()
        # self.logger = logging.getLogger('Osdag')
        # self.logger.setLevel(logging.DEBUG)
        # handler = logging.StreamHandler()
        # formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        # handler.setFormatter(formatter)
        # self.logger.addHandler(handler)
        # handler = logging.FileHandler('logging_text.log')
        # self.logger.addHandler(handler)
        self.design_status = False
        self.failed_design_dict = {}  # Initialize failed_design_dict
        self.failed_reason = None  # Track why design failed
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
        self.flange_class = None
        self.web_class = None
        self.gamma_m0 = 1.1  # As per IS 800:2007, Table 5 for yield stress
        self.material_lookup_cache = {}  # Cache for (material, thickness) lookups

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

    def input_dictionary_without_design_pref(self, *args, **kwargs):
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
        return KEY_DISP_COMPRESSION_COLUMN

    def set_osdaglogger(self, widget_or_key=None):
        import logging
        self.logger = logging.getLogger('Osdag')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        handler = logging.FileHandler('logging_text.log')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        # Add QTextEdit logger if widget is provided
        if widget_or_key is not None and hasattr(widget_or_key, 'append'):
            class QTextEditLogger(logging.Handler):
                def __init__(self, text_edit):
                    super().__init__()
                    self.text_edit = text_edit
                def emit(self, record):
                    msg = self.format(record)
                    self.text_edit.append(msg)
            qtext_handler = QTextEditLogger(widget_or_key)
            qtext_handler.setFormatter(formatter)
            self.logger.addHandler(qtext_handler)
        elif widget_or_key is not None:
            # If it's a key, use your existing OurLog logic
            handler = OurLog(widget_or_key)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def customized_input(self, *args, **kwargs):
        c_lst = []
        t1 = (KEY_SECSIZE, self.fn_profile_section)
        c_lst.append(t1)
        return c_lst

    def input_values(self, *args, **kwargs):
        """ 
        Function declared in ui_template.py line 566
        Fuction to return a list of tuples to be displayed as the UI (Input Dock)
        """
        self.module = KEY_DISP_LACEDCOL
        options_list = []

        # Module title and name
        options_list.append((KEY_DISP_LACEDCOL, "Laced Column", TYPE_MODULE, [], True, 'No Validator'))

        # Section
        options_list.append(("title_Section ", "Section Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_SEC_PROFILE, KEY_DISP_SEC_PROFILE, TYPE_COMBOBOX, KEY_LACEDCOL_SEC_PROFILE_OPTIONS, True, 'No Validator'))
        options_list.append(("title_Material", "Material Properties", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_MATERIAL, KEY_DISP_MATERIAL, TYPE_COMBOBOX, VALUES_MATERIAL, True, 'No Validator'))

        # Section Designation ComboBox with All/Customized
        options_list.append((KEY_SECSIZE, KEY_DISP_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, ['All','Customized'], True, 'No Validator'))

        # Geometry
        options_list.append(("title_Geometry", "Geometry", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_UNSUPPORTED_LEN_YY, KEY_DISP_UNSUPPORTED_LEN_YY, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_UNSUPPORTED_LEN_ZZ, KEY_DISP_UNSUPPORTED_LEN_ZZ, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_END1, KEY_DISP_END1, TYPE_COMBOBOX_CUSTOMIZED, VALUES_END1, True, 'No Validator'))
        options_list.append((KEY_END2,KEY_DISP_END2, TYPE_COMBOBOX_CUSTOMIZED, VALUES_END2, True, 'No Validator'))
        # Lacing
        options_list.append((KEY_LACING_PATTERN, "Lacing Pattern", TYPE_COMBOBOX, VALUES_LACING_PATTERN, True, 'No Validator'))
        # Connection
        options_list.append((KEY_CONN_TYPE, "Type of Connection", TYPE_COMBOBOX, VALUES_CONNECTION_TYPE, True, 'No Validator'))
        # Load
        options_list.append(("title_Load", "Load Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_AXIAL, "Axial Load (kN)", TYPE_TEXTBOX, None, True, 'Float Validator'))
        return options_list

    def fn_profile_section(self, *args):
        # Handle different argument formats like flexure.py
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        
        profile = args[0] if args else None
        
        if profile == 'Beams and Columns':
            res1 = connectdb("Beams", call_type="popup")
            res2 = connectdb("Columns", call_type="popup")
            return list(set(res1 + res2))
        elif profile == 'RHS and SHS':
            res1 = connectdb("RHS", call_type="popup")
            res2 = connectdb("SHS", call_type="popup")
            return list(set(res1 + res2))
        elif profile == 'CHS':
            return connectdb("CHS", call_type="popup")
        elif profile in ['Angles', 'Back to Back Angles', 'Star Angles']:
            return connectdb('Angles', call_type= "popup")
        elif profile in ['Channels', 'Back to Back Channels']:
            return connectdb("Channels", call_type= "popup")
        else:
            return []

    def fn_end1_end2(self, *args):
        # Accepts either a list or *args
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        end1 = args[0] if args else None
        end2 = args[1] if len(args) > 1 else None
        
        print(f"fn_end1_end2 called with end1: {end1}, end2: {end2}")
        
        if end1 == 'Fixed' and end2 == 'Fixed':
            return ['Fixed-Fixed']
        elif end1 == 'Fixed' and end2 == 'Pinned':
            return ['Fixed-Pinned']
        elif end1 == 'Pinned' and end2 == 'Fixed':
            return ['Pinned-Fixed']
        elif end1 == 'Pinned' and end2 == 'Pinned':
            return ['Pinned-Pinned']
        else:
            return ['Fixed-Fixed']  # Default case

    def fn_end1_image(self, *args):
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        val = args[0] if args else None
        if val == 'Fixed':
            return str(files("osdag.data.ResourceFiles.images").joinpath("6.RRRR.PNG"))
        elif val == 'Free':
            return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF.PNG"))
        elif val == 'Hinged':
            return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF.PNG"))
        elif val == 'Roller':
            return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR.PNG"))


    def fn_end2_image(self, *args):
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        end1 = args[0] if args else None
        end2 = args[1] if len(args) > 1 else None
        print("end 1 and end 2 are {}".format((end1, end2)))
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

    def input_value_changed(self, *args, **kwargs):
        lst = []
        t1 = ([KEY_SEC_PROFILE], KEY_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, self.fn_profile_section)
        lst.append(t1)
        t2 = ([KEY_LYY], KEY_END_COND_YY, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t2)
        t3 = ([KEY_LZZ], KEY_END_COND_ZZ, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t3)
        t3 = ([KEY_MATERIAL], KEY_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t3)
        t3 = ([KEY_END1, KEY_END2], KEY_IMAGE, TYPE_IMAGE, self.fn_end2_image)
        lst.append(t3)
        t4 = ([KEY_END1_Y], KEY_END2_Y, TYPE_COMBOBOX, self.fn_end1_end2)
        lst.append(t4)
        t5 = ([KEY_END1_Y, KEY_END2_Y], KEY_IMAGE_Y, TYPE_IMAGE, self.fn_end2_image)
        lst.append(t5)
        return lst

    def output_values(self, flag):
        def safe_display(val):
            if val is None:
                return "N/A"
            return round(val, 2) if isinstance(val, float) else val
        
        # Check if we have calculation results - this is more important than design_status
        has_results = (hasattr(self, 'optimum_section_ur_results') and 
                      self.optimum_section_ur_results and 
                      len(self.optimum_section_ur_results) > 0)
        
        # Set flag to True if we have results, regardless of design_status
        if has_results:
            flag = True
        elif not hasattr(self, 'design_status'):
            self.design_status = False
            flag = flag and self.design_status
        
        out_list = []
        
        # Section and Material Details
        out_list.append((None, "Section and Material Details", TYPE_TITLE, None, True))
        
        # Section Size - Get from results
        section_designation = ''
        if flag and hasattr(self, 'result_designation') and self.result_designation:
            section_designation = safe_display(self.result_designation)
        elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
            # Get from the best result
            best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
            if best_ur:
                section_designation = safe_display(self.optimum_section_ur_results[best_ur].get('Designation', ''))
        out_list.append((KEY_SECSIZE, "Section Designation", TYPE_TEXTBOX, section_designation, True))
        
        # Material Grade
        material_grade = ''
        if flag and self.material:
            material_grade = safe_display(self.material)
            self.logger.info(f"Displaying material grade in output: {material_grade}")
        out_list.append((KEY_MATERIAL, "Material Grade", TYPE_TEXTBOX, material_grade, True))
        
        

        # Effective Lengths
        out_list.append((None, "Effective Lengths", TYPE_TITLE, None, True))
        eff_len_yy = ''
        eff_len_zz = ''
        if flag:
            if hasattr(self, 'result_eff_len_yy') and self.result_eff_len_yy is not None:
                eff_len_yy = safe_display(self.result_eff_len_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    eff_len_yy = safe_display(self.optimum_section_ur_results[best_ur].get('Effective_length_yy', ''))
            if hasattr(self, 'result_eff_len_zz') and self.result_eff_len_zz is not None:
                eff_len_zz = safe_display(self.result_eff_len_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    eff_len_zz = safe_display(self.optimum_section_ur_results[best_ur].get('Effective_length_zz', ''))
        out_list.append((KEY_EFF_LEN_YY, "Effective Length (YY)", TYPE_TEXTBOX, eff_len_yy, True))
        out_list.append((KEY_EFF_LEN_ZZ, "Effective Length (ZZ)", TYPE_TEXTBOX, eff_len_zz, True))
        
        # Slenderness Ratios
        out_list.append((None, "Slenderness Ratios", TYPE_TITLE, None, True))
        slender_yy = ''
        slender_zz = ''
        if flag:
            if hasattr(self, 'result_eff_sr_yy') and self.result_eff_sr_yy is not None:
                slender_yy = safe_display(self.result_eff_sr_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    slender_yy = safe_display(self.optimum_section_ur_results[best_ur].get('Effective_SR_yy', ''))
            if hasattr(self, 'result_eff_sr_zz') and self.result_eff_sr_zz is not None:
                slender_zz = safe_display(self.result_eff_sr_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    slender_zz = safe_display(self.optimum_section_ur_results[best_ur].get('Effective_SR_zz', ''))
        out_list.append((KEY_SLENDER_YY, "Slenderness Ratio (YY)", TYPE_TEXTBOX, slender_yy, True))
        out_list.append((KEY_SLENDER_ZZ, "Slenderness Ratio (ZZ)", TYPE_TEXTBOX, slender_zz, True))
        
        # Design Values
        out_list.append((None, "Design Values", TYPE_TITLE, None, True))
        fcd = ''
        design_compressive = ''
        if flag:
            if hasattr(self, 'result_fcd') and self.result_fcd is not None:
                fcd = safe_display(self.result_fcd)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd = safe_display(self.optimum_section_ur_results[best_ur].get('FCD', ''))
            if hasattr(self, 'result_capacity') and self.result_capacity is not None:
                design_compressive = safe_display(self.result_capacity)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    design_compressive = safe_display(self.optimum_section_ur_results[best_ur].get('Capacity', ''))
        out_list.append((KEY_FCD, "Design Compressive Stress (fcd)", TYPE_TEXTBOX, fcd, True))
        out_list.append((KEY_DESIGN_COMPRESSIVE, "Design Compressive Strength", TYPE_TEXTBOX, design_compressive, True))
        
        # Utilization Ratio
        out_list.append((None, "Utilization Ratio", TYPE_TITLE, None, True))
        ur_value = ''
        if flag:
            if hasattr(self, 'result_UR') and self.result_UR is not None:
                ur_value = safe_display(self.result_UR)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    ur_value = safe_display(best_ur)
        out_list.append(("utilization_ratio", "Utilization Ratio", TYPE_TEXTBOX, ur_value, True))
        
        # Section Classification
        out_list.append((None, "Section Classification", TYPE_TITLE, None, True))
        section_class = ''
        if flag:
            if hasattr(self, 'result_section_class') and self.result_section_class:
                section_class = safe_display(self.result_section_class)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    section_class = safe_display(self.optimum_section_ur_results[best_ur].get('Section class', ''))
        out_list.append(("section_class", "Section Class", TYPE_TEXTBOX, section_class, True))
        
        # Effective Area
        out_list.append((None, "Effective Area", TYPE_TITLE, None, True))
        effective_area = ''
        if flag:
            if hasattr(self, 'result_effective_area') and self.result_effective_area is not None:
                effective_area = safe_display(self.result_effective_area)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    effective_area = safe_display(self.optimum_section_ur_results[best_ur].get('Effective area', ''))
        out_list.append(("effective_area", "Effective Area (mm²)", TYPE_TEXTBOX, effective_area, True))
        
        # Buckling Curve Classification
        out_list.append((None, "Buckling Curve Classification", TYPE_TITLE, None, True))
        bc_yy = ''
        bc_zz = ''
        if flag:
            if hasattr(self, 'result_bc_yy') and self.result_bc_yy:
                bc_yy = safe_display(self.result_bc_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    bc_yy = safe_display(self.optimum_section_ur_results[best_ur].get('Buckling_curve_yy', ''))
            if hasattr(self, 'result_bc_zz') and self.result_bc_zz:
                bc_zz = safe_display(self.result_bc_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    bc_zz = safe_display(self.optimum_section_ur_results[best_ur].get('Buckling_curve_zz', ''))
        out_list.append(("buckling_curve_yy", "Buckling Curve (YY)", TYPE_TEXTBOX, bc_yy, True))
        out_list.append(("buckling_curve_zz", "Buckling Curve (ZZ)", TYPE_TEXTBOX, bc_zz, True))
        
        # Imperfection Factor
        out_list.append((None, "Imperfection Factor", TYPE_TITLE, None, True))
        if_yy = ''
        if_zz = ''
        if flag:
            if hasattr(self, 'result_IF_yy') and self.result_IF_yy is not None:
                if_yy = safe_display(self.result_IF_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    if_yy = safe_display(self.optimum_section_ur_results[best_ur].get('IF_yy', ''))
            if hasattr(self, 'result_IF_zz') and self.result_IF_zz is not None:
                if_zz = safe_display(self.result_IF_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    if_zz = safe_display(self.optimum_section_ur_results[best_ur].get('IF_zz', ''))
        out_list.append(("imperfection_factor_yy", "Imperfection Factor (YY)", TYPE_TEXTBOX, if_yy, True))
        out_list.append(("imperfection_factor_zz", "Imperfection Factor (ZZ)", TYPE_TEXTBOX, if_zz, True))
        
        # Euler Buckling Stress
        out_list.append((None, "Euler Buckling Stress", TYPE_TITLE, None, True))
        ebs_yy = ''
        ebs_zz = ''
        if flag:
            if hasattr(self, 'result_ebs_yy') and self.result_ebs_yy is not None:
                ebs_yy = safe_display(self.result_ebs_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    ebs_yy = safe_display(self.optimum_section_ur_results[best_ur].get('EBS_yy', ''))
            if hasattr(self, 'result_ebs_zz') and self.result_ebs_zz is not None:
                ebs_zz = safe_display(self.result_ebs_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    ebs_zz = safe_display(self.optimum_section_ur_results[best_ur].get('EBS_zz', ''))
        out_list.append(("euler_buckling_stress_yy", "Euler Buckling Stress (YY)", TYPE_TEXTBOX, ebs_yy, True))
        out_list.append(("euler_buckling_stress_zz", "Euler Buckling Stress (ZZ)", TYPE_TEXTBOX, ebs_zz, True))
        
        # Non-dimensional Effective Slenderness Ratio
        out_list.append((None, "Non-dimensional Effective Slenderness Ratio", TYPE_TITLE, None, True))
        nd_esr_yy = ''
        nd_esr_zz = ''
        if flag:
            if hasattr(self, 'result_nd_esr_yy') and self.result_nd_esr_yy is not None:
                nd_esr_yy = safe_display(self.result_nd_esr_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    nd_esr_yy = safe_display(self.optimum_section_ur_results[best_ur].get('ND_ESR_yy', ''))
            if hasattr(self, 'result_nd_esr_zz') and self.result_nd_esr_zz is not None:
                nd_esr_zz = safe_display(self.result_nd_esr_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    nd_esr_zz = safe_display(self.optimum_section_ur_results[best_ur].get('ND_ESR_zz', ''))
        out_list.append(("nd_esr_yy", "ND ESR (YY)", TYPE_TEXTBOX, nd_esr_yy, True))
        out_list.append(("nd_esr_zz", "ND ESR (ZZ)", TYPE_TEXTBOX, nd_esr_zz, True))
        
        # Phi Values
        out_list.append((None, "Phi Values", TYPE_TITLE, None, True))
        phi_yy = ''
        phi_zz = ''
        if flag:
            if hasattr(self, 'result_phi_yy') and self.result_phi_yy is not None:
                phi_yy = safe_display(self.result_phi_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    phi_yy = safe_display(self.optimum_section_ur_results[best_ur].get('phi_yy', ''))
            if hasattr(self, 'result_phi_zz') and self.result_phi_zz is not None:
                phi_zz = safe_display(self.result_phi_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    phi_zz = safe_display(self.optimum_section_ur_results[best_ur].get('phi_zz', ''))
        out_list.append(("phi_yy", "Phi (YY)", TYPE_TEXTBOX, phi_yy, True))
        out_list.append(("phi_zz", "Phi (ZZ)", TYPE_TEXTBOX, phi_zz, True))
        
        # Stress Reduction Factor
        out_list.append((None, "Stress Reduction Factor", TYPE_TITLE, None, True))
        srf_yy = ''
        srf_zz = ''
        if flag:
            if hasattr(self, 'result_srf_yy') and self.result_srf_yy is not None:
                srf_yy = safe_display(self.result_srf_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    srf_yy = safe_display(self.optimum_section_ur_results[best_ur].get('SRF_yy', ''))
            if hasattr(self, 'result_srf_zz') and self.result_srf_zz is not None:
                srf_zz = safe_display(self.result_srf_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    srf_zz = safe_display(self.optimum_section_ur_results[best_ur].get('SRF_zz', ''))
        out_list.append(("stress_reduction_factor_yy", "SRF (YY)", TYPE_TEXTBOX, srf_yy, True))
        out_list.append(("stress_reduction_factor_zz", "SRF (ZZ)", TYPE_TEXTBOX, srf_zz, True))
        
        # Design Compressive Stress Values
        out_list.append((None, "Design Compressive Stress Values", TYPE_TITLE, None, True))
        fcd_1_yy = ''
        fcd_1_zz = ''
        fcd_2 = ''
        if flag:
            if hasattr(self, 'result_fcd_1_yy') and self.result_fcd_1_yy is not None:
                fcd_1_yy = safe_display(self.result_fcd_1_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd_1_yy = safe_display(self.optimum_section_ur_results[best_ur].get('FCD_1_yy', ''))
            if hasattr(self, 'result_fcd_1_zz') and self.result_fcd_1_zz is not None:
                fcd_1_zz = safe_display(self.result_fcd_1_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd_1_zz = safe_display(self.optimum_section_ur_results[best_ur].get('FCD_1_zz', ''))
            if hasattr(self, 'result_fcd_2') and self.result_fcd_2 is not None:
                fcd_2 = safe_display(self.result_fcd_2)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd_2 = safe_display(self.optimum_section_ur_results[best_ur].get('FCD_2', ''))
        out_list.append(("fcd_1_yy", "FCD_1 (YY)", TYPE_TEXTBOX, fcd_1_yy, True))
        out_list.append(("fcd_1_zz", "FCD_1 (ZZ)", TYPE_TEXTBOX, fcd_1_zz, True))
        out_list.append(("fcd_2", "FCD_2", TYPE_TEXTBOX, fcd_2, True))
        
        # Cost
        out_list.append((None, "Cost", TYPE_TITLE, None, True))
        cost = ''
        if flag:
            if hasattr(self, 'result_cost') and self.result_cost is not None:
                cost = safe_display(self.result_cost)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    cost = safe_display(self.optimum_section_ur_results[best_ur].get('Cost', ''))
        out_list.append(("cost", "Cost (INR)", TYPE_TEXTBOX, cost, True))
        
        # --- Channel and Lacing Details Section ---
        out_list.append((None, "Channel and Lacing Details", TYPE_TITLE, None, True))
        spacing_channels = ''
        if flag:
            if hasattr(self, 'result') and self.result.get('channel_spacing') is not None:
                spacing_channels = safe_display(self.result.get('channel_spacing'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    spacing_channels = safe_display(self.optimum_section_ur_results[best_ur].get('channel_spacing', ''))
        out_list.append(("channel_spacing", "Spacing Between Channels (mm)", TYPE_TEXTBOX, spacing_channels, True))

        # --- Tie Plate Section ---
        out_list.append((None, "Tie Plate", TYPE_TITLE, None, True))
        tie_plate_d = ''
        tie_plate_t = ''
        tie_plate_l = ''
        if flag:
            if hasattr(self, 'result') and self.result.get('tie_plate_d') is not None:
                tie_plate_d = safe_display(self.result.get('tie_plate_d'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    tie_plate_d = safe_display(self.optimum_section_ur_results[best_ur].get('tie_plate_d', ''))
            if hasattr(self, 'result') and self.result.get('tie_plate_t') is not None:
                tie_plate_t = safe_display(self.result.get('tie_plate_t'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    tie_plate_t = safe_display(self.optimum_section_ur_results[best_ur].get('tie_plate_t', ''))
            if hasattr(self, 'result') and self.result.get('tie_plate_l') is not None:
                tie_plate_l = safe_display(self.result.get('tie_plate_l'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    tie_plate_l = safe_display(self.optimum_section_ur_results[best_ur].get('tie_plate_l', ''))
        out_list.append(("tie_plate_d", "Tie Plate Depth D (mm)", TYPE_TEXTBOX, tie_plate_d, True))
        out_list.append(("tie_plate_t", "Tie Plate Thickness t (mm)", TYPE_TEXTBOX, tie_plate_t, True))
        out_list.append(("tie_plate_l", "Tie Plate Length L (mm)", TYPE_TEXTBOX, tie_plate_l, True))

        # --- Lacing Spacing Section ---
        out_list.append((None, "Lacing Spacing", TYPE_TITLE, None, True))
        lacing_spacing = ''
        if flag:
            if hasattr(self, 'result') and self.result.get('lacing_spacing') is not None:
                lacing_spacing = safe_display(self.result.get('lacing_spacing'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    lacing_spacing = safe_display(self.optimum_section_ur_results[best_ur].get('lacing_spacing', ''))
        out_list.append(("lacing_spacing", "Lacing Spacing (L0) (mm)", TYPE_TEXTBOX, lacing_spacing, True))
        
        return out_list

    def func_for_validation(self, design_dictionary):

        all_errors = []
        self.design_status = False
        flag = False
        option_list = self.input_values()
        missing_fields_list = []
        
        # Check if section designation is properly set in design dictionary
        # The UI framework automatically stores selected sections in design_dictionary[KEY_SECSIZE + "_customized"]
        sec_list = design_dictionary.get(KEY_SECSIZE + "_customized", [])
        
        if not sec_list or (isinstance(sec_list, list) and len(sec_list) == 0):
            print("WARNING: No sections selected. Please select section designation (All or Customized).")
            missing_fields_list.append('Section Designation')
        else:
            print(f"DEBUG: Section designation validated - {len(sec_list)} sections selected")
            # Store the selected sections for later use
            self.sec_list = sec_list
        
        # Check other required fields
        material = design_dictionary.get(KEY_SEC_MATERIAL, '')
        if not material or material in ['', 'Select Material']:
            missing_fields_list.append('Material')
        len_zz = design_dictionary.get(KEY_UNSUPPORTED_LEN_ZZ, None)
        len_yy = design_dictionary.get(KEY_UNSUPPORTED_LEN_YY, None)
        try:
            if float(len_zz) <= 0:
                missing_fields_list.append('Actual Length (z-z), mm')
        except:
            missing_fields_list.append('Actual Length (z-z), mm')
        try:
            if float(len_yy) <= 0:
                missing_fields_list.append('Actual Length (y-y), mm')
        except:
            missing_fields_list.append('Actual Length (y-y), mm')
        axial = design_dictionary.get(KEY_AXIAL, None)
        try:
            if float(axial) <= 0:
                missing_fields_list.append('Axial Load (kN)')
        except:
            missing_fields_list.append('Axial Load (kN)')
        if len(missing_fields_list) > 0:
            error = self.generate_missing_fields_error_string(missing_fields_list)
            all_errors.append(error)
            self.logger.error(f"Missing/invalid input fields: {', '.join(missing_fields_list)}")
            return all_errors
        else:
            flag = True
        if flag:

            self.set_input_values(design_dictionary)
            # Safely check failed_design_dict with proper initialization
            failed_design_dict = getattr(self, 'failed_design_dict', {})
            if self.design_status == False and failed_design_dict and len(failed_design_dict) > 0:
                self.logger.error(
                    "Design Failed, Check Design Report"
                )
                return # ['Design Failed, Check Design Report'] @TODO
            elif self.design_status:
                pass
            else:
                input_section_list = getattr(self, 'input_section_list', 'N/A')
                optimum_section_ur = getattr(self, 'optimum_section_ur', 'N/A')
                failed_design_dict = getattr(self, 'failed_design_dict', 'N/A')
                design_status = getattr(self, 'design_status', 'N/A')
                self.logger.info(f"input_section_list: {input_section_list}")
                self.logger.info(f"optimum_section_ur: {optimum_section_ur}")
                self.logger.info(f"failed_design_dict: {failed_design_dict}")
                self.logger.info(f"design_status: {design_status}")
                self.logger.error(
                    "Design Failed. No section satisfied UR or section classification filter."
                )
                return # ['Design Failed. Slender Sections Selected']
        else:
            return all_errors

    def get_3d_components(self, *args, **kwargs):
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

        if (self.sec_profile == VALUES_SEC_PROFILE[0]):  # Beams and Columns
            for section in self.sec_list:
                if section in red_list:
                    logger.warning(" : You are using a section ({}) (in red color) that is not available in latest version of IS 808".format(section))

    # Setting inputs from the input dock GUI
    def set_input_values(self, design_dictionary):
        self.logger.info(f"set_input_values called with: {design_dictionary}")
        super(Member, self).set_input_values(design_dictionary)
        # section properties
        self.module = design_dictionary.get(KEY_DISP_LACEDCOL, "")
        self.mainmodule = 'Columns with known support conditions'
        self.sec_profile = design_dictionary.get(KEY_LACEDCOL_SEC_PROFILE, "")
        
        # Get section list from design dictionary (UI framework stores it as KEY_SECSIZE + "_customized")
        self.sec_list = design_dictionary.get(KEY_SECSIZE + "_customized", [])
        
        if not self.sec_list:
            self.logger.error("No sections selected. Please select section designation (All or Customized) first.")
            self.design_status = False
            return
        
        # Ensure sec_list is a list and contains valid sections
        if isinstance(self.sec_list, str):
            if self.sec_list and self.sec_list != 'Select Section':
                self.sec_list = [self.sec_list]
            else:
                self.sec_list = []
        elif not isinstance(self.sec_list, list):
            self.sec_list = list(self.sec_list) if self.sec_list else []
        
        # Filter out any 'Select Section' entries
        self.sec_list = [s for s in self.sec_list if s and s != 'Select Section']
        
        if not self.sec_list:
            self.logger.error("No valid sections in sec_list. Please select valid sections.")
            self.design_status = False
            return
        
        self.logger.info(f"Using {len(self.sec_list)} sections from section designation dialog: {self.sec_list}")
        
        self.material = design_dictionary.get(KEY_SEC_MATERIAL, "")
        # Defensive checks for required fields
        def is_valid_material(mat):
            if isinstance(mat, list):
                return any(m and m != 'Select Material' for m in mat)
            return mat and mat != 'Select Material'
        if not is_valid_material(self.material):
            self.logger.error("Material is missing or invalid.")
            self.design_status = False
            return
        def is_valid_section(sec):
            if isinstance(sec, list):
                return any(s and s != 'Select Section' for s in sec)
            return sec and sec != 'Select Section'
        if not is_valid_section(self.sec_list):
            self.logger.error(f"Section list is missing or invalid: {self.sec_list}")
            self.design_status = False
            return
        # section user data
        try:
            self.length_zz = float(design_dictionary.get(KEY_UNSUPPORTED_LEN_ZZ, 0))
            if self.length_zz <= 0:
                raise ValueError
        except:
            self.logger.error("Actual Length (z-z), mm is missing or invalid.")
            self.design_status = False
            return
        try:
            self.length_yy = float(design_dictionary.get(KEY_UNSUPPORTED_LEN_YY, 0))
            if self.length_yy <= 0:
                raise ValueError
        except:
            self.logger.error("Actual Length (y-y), mm is missing or invalid.")
            self.design_status = False
            return
        # end condition
        self.end_1_z = design_dictionary.get(KEY_END1, "")
        self.end_2_z = design_dictionary.get(KEY_END2, "")
        self.end_1_y = design_dictionary.get(KEY_END1_Y, "")
        self.end_2_y = design_dictionary.get(KEY_END2_Y, "")
        # factored loads
        try:
            axial_force = float(design_dictionary.get(KEY_AXIAL, 0))
            if axial_force <= 0:
                raise ValueError
        except:
            self.logger.error("Axial Load (kN) is missing or invalid.")
            self.design_status = False
            return
        self.load = Load(axial_force=axial_force, shear_force=0.0, moment=0.0, moment_minor=0.0, unit_kNm=True)
        # design preferences
        try:
            self.allowable_utilization_ratio = float(design_dictionary.get(KEY_ALLOW_UR, 1.0))
        except:
            self.allowable_utilization_ratio = 1.0
        try:
            self.effective_area_factor = float(design_dictionary.get(KEY_EFFECTIVE_AREA_PARA, 1.0))
        except:
            self.effective_area_factor = 1.0
        try:
            self.optimization_parameter = design_dictionary[KEY_OPTIMIZATION_PARA]
        except:
            self.optimization_parameter = 'Utilization Ratio'
        # self.allow_class1 = design_dictionary[KEY_ALLOW_CLASS1]
        # self.allow_class2 = design_dictionary[KEY_ALLOW_CLASS2]
        # self.allow_class3 = design_dictionary[KEY_ALLOW_CLASS3]
        # self.allow_class4 = design_dictionary[KEY_ALLOW_CLASS4]
        try:
            self.steel_cost_per_kg = float(design_dictionary[KEY_STEEL_COST])
        except:
            self.steel_cost_per_kg = 50
        self.allowed_sections = ['Plastic', 'Compact', 'Semi-Compact', 'Slender']

        # Defensive: Only run if section list and material are valid
        if self.sec_list and self.material:
            # Clear material cache when material changes to ensure fresh properties
            self.material_lookup_cache = {}
            
            # Initialize material_property BEFORE section_classification
            self.material_property = Material(material_grade=self.material, thickness=0)
            self.flag = self.section_classification()
            if self.flag:
                self.design_column()
                self.results()
        
        # safety factors
        self.gamma_m0 = IS800_2007.cl_5_4_1_Table_5["gamma_m0"]["yielding"]
        
        # initialize the design status
        self.design_status_list = []
        self.design_status = False
        self.failed_design_dict = {}
        # Always perform calculations if required fields are present

    # Simulation starts here
    def section_classification(self):
        # Deduplicate section list to avoid repeated processing
        self.sec_list = list(dict.fromkeys(self.sec_list))
        self.logger.debug(f"[section_classification] Starting with sec_list: {self.sec_list}")
        self.logger.info(f"section_classification called. sec_list: {self.sec_list}, sec_profile: {self.sec_profile}, material: {self.material}")
        local_flag = True
        self.input_section_list = []
        self.input_section_classification = {}

        slender_sections = []
        accepted_sections = []
        rejected_sections = []  # Track all rejected sections with reasons
        for section in self.sec_list:
            trial_section = section.strip("'")

            # Always define flange_ratio and web_ratio with safe defaults
            flange_ratio = None
            web_ratio = None
            
            # fetching the section properties
            if self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[0]:  # Beams and columns
                try:
                    result = Beam(designation=trial_section, material_grade=self.material)
                except:
                    result = Column(designation=trial_section, material_grade=self.material)
                self.section_property = result
            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[1]:  # RHS and SHS
                try:
                    result = RHS(designation=trial_section, material_grade=self.material)
                except:
                    result = SHS(designation=trial_section, material_grade=self.material)
                self.section_property = result
            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[2] and isinstance(self.section_property, CHS):  # CHS
                self.section_property = CHS(designation=trial_section, material_grade=self.material)
            else:
                self.section_property = Column(designation=trial_section, material_grade=self.material)

            # updating the material property based on thickness of the thickest element
            # Defensive checks and logging
            if not self.material or self.material in [None, '', 'Select Material']:
                error_msg = f"Material is missing or invalid before database lookup: {self.material}"
                self.logger.error(error_msg)
                self.failed_reason = error_msg
                self.design_status = False
                rejected_sections.append((trial_section, 'Material properties not found'))
                continue
                
            flange_thk = getattr(self.section_property, 'flange_thickness', None)
            web_thk = getattr(self.section_property, 'web_thickness', None)
            
            if flange_thk is None or web_thk is None:
                error_msg = f"Section property thickness missing for {trial_section}: flange_thickness={flange_thk}, web_thickness={web_thk}"
                self.logger.error(error_msg)
                self.failed_reason = error_msg
                self.design_status = False
                rejected_sections.append((trial_section, 'Section property thickness missing'))
                continue
                
            try:
                max_thk = max(float(flange_thk), float(web_thk))
            except Exception as e:
                error_msg = f"Invalid thickness values for {trial_section}: flange_thickness={flange_thk}, web_thickness={web_thk}, error={e}"
                self.logger.error(error_msg)
                self.failed_reason = error_msg
                self.design_status = False
                rejected_sections.append((trial_section, 'Invalid thickness values'))
                continue
                
            cache_key = (self.material, round(max_thk, 1))
            if cache_key not in self.material_lookup_cache:
                self.material_property.connect_to_database_to_get_fy_fu(self.material, max_thk)
                self.material_lookup_cache[cache_key] = (self.material_property.fy, self.material_property.fu)
                self.logger.info(f"Updated material properties for {self.material}: fy={self.material_property.fy}, fu={self.material_property.fu}")
            else:
                self.material_property.fy, self.material_property.fu = self.material_lookup_cache[cache_key]
                self.logger.info(f"Using cached material properties for {self.material}: fy={self.material_property.fy}, fu={self.material_property.fu}")

            # Defensive: Check if material properties were found
            if not self.material_property.fy or not self.material_property.fu:
                from ...Common import PATH_TO_DATABASE
                error_msg = f"Material properties not found for grade '{self.material}' and thickness '{max_thk}'. Check if the material exists in the database at {PATH_TO_DATABASE}."
                self.logger.error(error_msg)
                self.failed_reason = error_msg
                self.design_status = False
                rejected_sections.append((trial_section, 'Material properties not found'))
                continue

            # section classification
            if self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[0]:  # Beams and Columns
                if self.section_property.type == 'Rolled':
                    self.flange_class = IS800_2007.Table2_i((self.section_property.flange_width / 2), self.section_property.flange_thickness,
                                                            self.material_property.fy, self.section_property.type)[0]
                else:
                    self.flange_class = IS800_2007.Table2_i(((self.section_property.flange_width / 2) - (self.section_property.web_thickness / 2)),
                                                            self.section_property.flange_thickness, self.section_property.fy,
                                                            self.section_property.type)[0]
                # FIX: Use 'Neutral axis at mid-depth' for web_class
                self.web_class = IS800_2007.Table2_iii((self.section_property.depth - (2 * self.section_property.flange_thickness)),
                                                       self.section_property.web_thickness, self.material_property.fy,
                                                       classification_type='Axial compression')
                
                # Calculate ratios for I-sections
                web_ratio = (self.section_property.depth - 2 * (
                            self.section_property.flange_thickness + self.section_property.root_radius)) / self.section_property.web_thickness
                flange_ratio = self.section_property.flange_width / 2 / self.section_property.flange_thickness

            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[1]:  # RHS and SHS
                self.flange_class = IS800_2007.Table2_iii((self.section_property.depth - (2 * self.section_property.flange_thickness)),
                                                          self.section_property.flange_thickness, self.material_property.fy,
                                                          classification_type='Axial compression')
                self.web_class = self.flange_class
                
                # Calculate ratios for RHS/SHS
                web_ratio = (self.section_property.depth - 2 * (
                            self.section_property.flange_thickness + self.section_property.root_radius)) / self.section_property.web_thickness
                flange_ratio = self.section_property.flange_width / 2 / self.section_property.flange_thickness

            elif self.sec_profile == KEY_LACEDCOL_SEC_PROFILE_OPTIONS[2] and isinstance(self.section_property, CHS):  # CHS
                self.flange_class = IS800_2007.Table2_x(self.section_property.out_diameter, self.section_property.flange_thickness,
                                                        self.material_property.fy, load_type='axial compression')
                self.web_class = self.flange_class
                # For CHS, use diameter to thickness ratio
                web_ratio = self.section_property.out_diameter / self.section_property.flange_thickness
                flange_ratio = web_ratio  # Same ratio for circular sections
            else:
                self.flange_class = self.web_class = None
                web_ratio = flange_ratio = None
            
            # Smart classification logic
            if self.flange_class == 'Slender' and self.web_class == 'Slender':
                self.section_class = 'Slender'
            elif 'Slender' in [self.flange_class, self.web_class]:
                self.section_class = 'Semi-Compact'  # downgrade if only one is slender
            else:
                if self.flange_class == 'Plastic' and self.web_class == 'Plastic':
                    self.section_class = 'Plastic'
                elif 'Plastic' in [self.flange_class, self.web_class] or 'Compact' in [self.flange_class, self.web_class]:
                    self.section_class = 'Compact'
                else:
                    self.section_class = 'Semi-Compact'
                    
            # Optionally, upgrade borderline slender sections
            if self.section_class == 'Slender':
                if (flange_ratio is not None and web_ratio is not None and
                    isinstance(flange_ratio, (int, float)) and isinstance(web_ratio, (int, float)) and
                    flange_ratio <= 9.5 and web_ratio <= 79.5):
                    self.logger.info(f"Reclassifying borderline Slender section {trial_section} to Semi-Compact")
                    self.section_class = 'Semi-Compact'

            # Log section classification details
            flange_ratio_str = f"{flange_ratio:.2f}" if flange_ratio is not None else "N/A"
            web_ratio_str = f"{web_ratio:.2f}" if web_ratio is not None else "N/A"
            self.logger.info(
                f"The section is {self.section_class}. The {trial_section} section has {flange_ratio_str} flange({self.flange_class}) and {web_ratio_str} web({self.web_class}). [Reference: Cl 3.7, IS 800:2007]"
            )
            # 2.2 - Effective length
            self.effective_length_zz = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_zz,
                end_1=self.end_1_z,
                end_2=self.end_2_z)
            self.effective_length_yy = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_yy,
                end_1=self.end_1_y,
                end_2=self.end_2_y)

            # 2.3 - Effective slenderness ratio
            self.effective_sr_zz = self.effective_length_zz / self.section_property.rad_of_gy_z
            self.effective_sr_yy = self.effective_length_yy / self.section_property.rad_of_gy_y

            limit = IS800_2007.cl_3_8_max_slenderness_ratio(1)
            if self.effective_sr_zz > limit and self.effective_sr_yy > limit:
                error_msg = f"Length provided is beyond the limit allowed for section {trial_section}. [Reference: Cl 3.8, IS 800:2007]"
                self.logger.warning(error_msg)
                self.logger.error("Cannot compute. Given Length does not pass.")
                self.failed_reason = error_msg
                slender_sections.append(trial_section)
                rejected_sections.append((trial_section, 'Slenderness ratio exceeded'))
                continue

            # Add section to input list if it passes classification filter
            if self.section_class in self.allowed_sections:
                self.input_section_list.append(trial_section)
                self.input_section_classification.update({trial_section: [self.section_class, self.flange_class, self.web_class, flange_ratio, web_ratio]})
                accepted_sections.append(trial_section)
            else:
                self.logger.info(f"Section {trial_section} classified as '{self.section_class}' but not in allowed sections: {self.allowed_sections}")
                rejected_sections.append((trial_section, f"Classified as '{self.section_class}', not in allowed_sections"))
        # Check if any sections passed the classification filter
        if not self.input_section_list:
            error_msg = f"No sections passed the classification filter. Allowed sections: {self.allowed_sections}"
            self.logger.error(error_msg)
            self.failed_reason = error_msg
            self.design_status = False
            # Robust fallback: expand allowed_sections to all types and re-check
            self.logger.warning("No section passed classification. Expanding allowed_sections to include all types.")
            self.allowed_sections = ['Plastic', 'Compact', 'Semi-Compact', 'Slender']
            for section in self.sec_list:
                trial_section = section.strip("'")
                if trial_section in self.input_section_classification:
                    if self.input_section_classification[trial_section][0] in self.allowed_sections:
                        self.input_section_list.append(trial_section)
                        accepted_sections.append(trial_section)
            if not self.input_section_list:
                self.logger.error("Design Failed. All sections are too slender or do not meet requirements.")
                local_flag = False

        # Print summary at end
        print("\n=== Section Classification Summary ===")
        print(f"Accepted sections: {accepted_sections}")
        print(f"Rejected/slender sections: {slender_sections}")
        print(f"Final allowed_sections: {self.allowed_sections}")
        print(f"Final input_section_list: {self.input_section_list}")
        return local_flag


    def design_column(self):
        try:
            # checking DP inputs
            if (self.allowable_utilization_ratio <= 0.10) or (self.allowable_utilization_ratio > 1.0):
                logger.warning("The defined value of Utilization Ratio in the design preferences tab is out of the suggested range.")
                logger.info("Provide an appropriate input and re-design.")
                logger.info("Assuming a default value of 1.0.")
                self.allowable_utilization_ratio = 1.0
                self.design_status = False
                self.design_status_list.append(self.design_status)

            if (self.effective_area_factor <= 0.10) or (self.effective_area_factor > 1.0):
                logger.warning("The defined value of Effective Area Factor in the design preferences tab is out of the suggested range.")
                logger.info("Provide an appropriate input and re-design.")
                logger.info("Assuming a default value of 1.0.")
                self.effective_area_factor = 1.0
                self.design_status = False
                self.design_status_list.append(self.design_status)

            self.epsilon = math.sqrt(250 / self.material_property.fy)
            self.optimum_section_ur_results = {}
            self.optimum_section_ur = []
            self.optimum_section_cost_results = {}
            self.optimum_section_cost = []
            self.flag = self.section_classification()
            # Remove duplicate sections to avoid repeated calculations
            self.input_section_list = list(dict.fromkeys(self.input_section_list))
            if self.flag:
                for section in self.input_section_list:
                    ur_class = None
                    if section in self.input_section_classification:
                        ur_class = self.input_section_classification[section]
                    ur_value = None
                    for ur in self.optimum_section_ur_results:
                        if self.optimum_section_ur_results[ur].get('Designation') == section:
                            ur_value = ur
                            break
                for section in self.input_section_list:  # iterating the design over each section to find the most optimum section

                    # fetching the section properties of the selected section
                    if self.sec_profile == VALUES_SEC_PROFILE[0]:  # Beams and columns
                        try:
                            result = Beam(designation=section, material_grade=self.material)
                        except:
                            result = Column(designation=section, material_grade=self.material)
                        self.section_property = result
                    elif self.sec_profile == VALUES_SEC_PROFILE[1]:  # RHS and SHS
                        try:
                            result = RHS(designation=section, material_grade=self.material)
                        except:
                            result = SHS(designation=section, material_grade=self.material)
                        self.section_property = result

                    elif self.sec_profile == VALUES_SEC_PROFILE[2]:  # CHS
                        self.section_property = CHS(designation=section, material_grade=self.material)
                        self.section_property.designation = section
                    else:   #Why?
                        self.section_property = Column(designation=section, material_grade=self.material)

                    self.material_property.connect_to_database_to_get_fy_fu(self.material, max(self.section_property.flange_thickness,
                                                                                            self.section_property.web_thickness))
                    self.epsilon = math.sqrt(250 / self.material_property.fy)
                    

                    # initialize lists for updating the results dictionary
                    self.list_zz = []
                    self.list_yy = []

                    self.list_zz.append(section)
                    self.list_yy.append(section)

                    # Step 1 - computing the effective sectional area
                    self.section_class = self.input_section_classification[section][0]

                    if self.section_class == 'Slender':
                        if (self.sec_profile == VALUES_SEC_PROFILE[0]):  # Beams and Columns
                            self.effective_area = (2 * ((31.4 * self.epsilon * self.section_property.flange_thickness) *
                                                        self.section_property.flange_thickness)) + \
                                                (2 * ((21 * self.epsilon * self.section_property.web_thickness) * self.section_property.web_thickness))
                        elif (self.sec_profile == VALUES_SEC_PROFILE[1]):
                            self.effective_area = (2 * 21 * self.epsilon * self.section_property.flange_thickness) * 2
                    else:
                        self.effective_area = self.section_property.area  # mm2


                    if self.effective_area_factor < 1.0:
                        self.effective_area = round(self.effective_area * self.effective_area_factor, 2)

                    self.list_zz.append(self.section_class)
                    self.list_yy.append(self.section_class)

                    self.list_zz.append(self.effective_area)
                    self.list_yy.append(self.effective_area)

                    # Step 2 - computing the design compressive stress

                    # 2.1 - Buckling curve classification and Imperfection factor
                    if (self.sec_profile == VALUES_SEC_PROFILE[0]):  # Beams and Columns

                        if self.section_property.type == 'Rolled':
                            self.buckling_class_zz = IS800_2007.cl_7_1_2_2_buckling_class_of_crosssections(self.section_property.flange_width,
                                                                                                        self.section_property.depth,
                                                                                                        self.section_property.flange_thickness,
                                                                                                        cross_section='Rolled I-sections',
                                                                                                        section_type='Hot rolled')['z-z']
                            self.buckling_class_yy = IS800_2007.cl_7_1_2_2_buckling_class_of_crosssections(self.section_property.flange_width,
                                                                                                        self.section_property.depth,
                                                                                                        self.section_property.flange_thickness,
                                                                                                        cross_section='Rolled I-sections',
                                                                                                        section_type='Hot rolled')['y-y']
                        else:
                            self.buckling_class_zz = IS800_2007.cl_7_1_2_2_buckling_class_of_crosssections(self.section_property.flange_width,
                                                                                                        self.section_property.depth,
                                                                                                        self.section_property.flange_thickness,
                                                                                                        cross_section='Welded I-section',
                                                                                                        section_type='Hot rolled')['z-z']
                            self.buckling_class_yy = IS800_2007.cl_7_1_2_2_buckling_class_of_crosssections(self.section_property.flange_width,
                                                                                                        self.section_property.depth,
                                                                                                        self.section_property.flange_thickness,
                                                                                                        cross_section='Welded I-section',
                                                                                                        section_type='Hot rolled')['y-y']
                    else:
                        self.buckling_class_zz = 'a'
                        self.buckling_class_yy = 'a'

                    self.imperfection_factor_zz = IS800_2007.cl_7_1_2_1_imperfection_factor(buckling_class=self.buckling_class_zz)
                    self.imperfection_factor_yy = IS800_2007.cl_7_1_2_1_imperfection_factor(buckling_class=self.buckling_class_yy)

                    self.list_zz.append(self.buckling_class_zz)
                    self.list_yy.append(self.buckling_class_yy)

                    self.list_zz.append(self.imperfection_factor_zz)
                    self.list_yy.append(self.imperfection_factor_yy)

                    # 2.2 - Effective length
                    self.effective_length_zz = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(self.length_zz ,
                                                                                                                    end_1=self.end_1_z,
                                                                                                                    end_2=self.end_2_z)  # mm
                    self.effective_length_yy = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(self.length_yy ,
                                                                                                                    end_1=self.end_1_y,
                                                                                                                    end_2=self.end_2_y)  # mm

                    self.list_zz.append(self.effective_length_zz)
                    self.list_yy.append(self.effective_length_yy)

                    # 2.3 - Effective slenderness ratio
                    self.effective_sr_zz = self.effective_length_zz / self.section_property.rad_of_gy_z
                    self.effective_sr_yy = self.effective_length_yy / self.section_property.rad_of_gy_y

                    self.list_zz.append(self.effective_sr_zz)
                    self.list_yy.append(self.effective_sr_yy)

                    # 2.4 - Euler buckling stress
                    self.euler_bs_zz = (math.pi ** 2 * self.section_property.modulus_of_elasticity) / self.effective_sr_zz ** 2
                    self.euler_bs_yy = (math.pi ** 2 * self.section_property.modulus_of_elasticity) / self.effective_sr_yy ** 2

                    self.list_zz.append(self.euler_bs_zz)
                    self.list_yy.append(self.euler_bs_yy)

                    # 2.5 - Non-dimensional effective slenderness ratio
                    self.non_dim_eff_sr_zz = math.sqrt(self.material_property.fy / self.euler_bs_zz)
                    self.non_dim_eff_sr_yy = math.sqrt(self.material_property.fy / self.euler_bs_yy)


                    self.list_zz.append(self.non_dim_eff_sr_zz)
                    self.list_yy.append(self.non_dim_eff_sr_yy)

                    # 2.5 - phi
                    self.phi_zz = 0.5 * (1 + (self.imperfection_factor_zz * (self.non_dim_eff_sr_zz - 0.2)) + self.non_dim_eff_sr_zz ** 2)
                    self.phi_yy = 0.5 * (1 + (self.imperfection_factor_yy * (self.non_dim_eff_sr_yy - 0.2)) + self.non_dim_eff_sr_yy ** 2)


                    self.list_zz.append(self.phi_zz)
                    self.list_yy.append(self.phi_yy)

                    # 2.6 - Design compressive stress
                    self.stress_reduction_factor_zz = 1 / (self.phi_zz + (self.phi_zz ** 2 - self.non_dim_eff_sr_zz ** 2) ** 0.5)
                    self.stress_reduction_factor_yy = 1 / (self.phi_yy + (self.phi_yy ** 2 - self.non_dim_eff_sr_yy ** 2) ** 0.5)

                    self.list_zz.append(self.stress_reduction_factor_zz)
                    self.list_yy.append(self.stress_reduction_factor_yy)

                    self.f_cd_1_zz = (self.stress_reduction_factor_zz * self.material_property.fy) / self.gamma_m0
                    self.f_cd_1_yy = (self.stress_reduction_factor_yy * self.material_property.fy) / self.gamma_m0
                    self.f_cd_2 = self.material_property.fy / self.gamma_m0

                    self.f_cd_zz = min(self.f_cd_1_zz, self.f_cd_2)
                    self.f_cd_yy = min(self.f_cd_1_yy, self.f_cd_2)

                    self.f_cd = min(self.f_cd_zz, self.f_cd_yy)

                    self.list_zz.append(self.f_cd_1_zz)
                    self.list_yy.append(self.f_cd_1_yy)

                    self.list_zz.append(self.f_cd_2)
                    self.list_yy.append(self.f_cd_2)

                    self.list_zz.append(self.f_cd_zz)
                    self.list_yy.append(self.f_cd_yy)

                    self.list_zz.append(self.f_cd)
                    self.list_yy.append(self.f_cd)

                    # 2.7 - Capacity of the section

                    self.section_capacity = self.f_cd * self.effective_area  # N

                    self.list_zz.append(self.section_capacity)
                    self.list_yy.append(self.section_capacity)

                    # 2.8 - UR
                    self.ur = round(self.load.axial_force / self.section_capacity, 3)

                    self.list_zz.append(self.ur)
                    self.list_yy.append(self.ur)
                    self.optimum_section_ur.append(self.ur)

                    # 2.9 - Cost of the section in INR
                    self.cost = (self.section_property.unit_mass * self.section_property.area * 1e-4) * min(self.length_zz, self.length_yy) * \
                                self.steel_cost_per_kg

                    self.list_zz.append(self.cost)
                    self.list_yy.append(self.cost)
                    self.optimum_section_cost.append(self.cost)
                    
                    # --- Tie Plate, Spacing, and Lacing Angle Calculations ---
                    tie_plate_d = round(2 * self.section_property.depth / 3, 2)         # mm
                    tie_plate_t = round(self.section_property.web_thickness, 2)          # mm
                    tie_plate_l = round(self.section_property.depth / 2, 2)              # mm
                    spacing_between_channels = round(self.section_property.depth + 2 * tie_plate_t, 2)  # mm
                    lacing_angle = round(math.degrees(math.atan(spacing_between_channels / (2 * tie_plate_l))), 2)  # degrees

                    # Store in self.result for output dock (for the last/selected section)
                    self.result['tie_plate_d'] = tie_plate_d
                    self.result['tie_plate_t'] = tie_plate_t
                    self.result['tie_plate_l'] = tie_plate_l
                    self.result['channel_spacing'] = spacing_between_channels
                    self.result['lacing_spacing'] = lacing_angle

                    # Store in optimum_section_ur_results for output dock (for each section)
                    ur = self.ur
                    if ur in self.optimum_section_ur_results:
                        self.optimum_section_ur_results[ur]['tie_plate_d'] = tie_plate_d
                        self.optimum_section_ur_results[ur]['tie_plate_t'] = tie_plate_t
                        self.optimum_section_ur_results[ur]['tie_plate_l'] = tie_plate_l
                        self.optimum_section_ur_results[ur]['channel_spacing'] = spacing_between_channels
                        self.optimum_section_ur_results[ur]['lacing_spacing'] = lacing_angle

                    #tieplate
                    # 2.X - Tie Plate Dimensions
                    self.tie_plate_d = round(2 * self.section_property.depth / 3, 2)         # mm
                    self.tie_plate_t = round(self.section_property.web_thickness, 2)         # mm
                    self.tie_plate_l = round(self.section_property.depth / 2, 2)             # mm
                    self.list_zz.append(self.tie_plate_d)
                    self.list_yy.append(self.tie_plate_d)
                    self.list_zz.append(self.tie_plate_t)
                    self.list_yy.append(self.tie_plate_t)
                    self.list_zz.append(self.tie_plate_l)
                    self.list_yy.append(self.tie_plate_l)

# 2.X - Lacing Spacing Between Channels
                    self.spacing_between_channels = round(self.section_property.depth + 2 * self.tie_plate_t, 2)  # mm
                    self.list_zz.append(self.spacing_between_channels)
                    self.list_yy.append(self.spacing_between_channels)

# 2.X - Lacing Angle
                    self.lacing_angle = round(math.degrees(math.atan(self.spacing_between_channels / (2 * self.tie_plate_l))), 2)  # degrees
                    self.list_zz.append(self.lacing_angle) 
                    self.list_yy.append(self.lacing_angle)
                    self.store_additional_outputs(
                        d=self.tie_plate_d,
                        t=self.tie_plate_t,
                        l=self.tie_plate_l,
                        spacing=self.lacing_angle,
                        c_spacing=self.spacing_between_channels
                        )
                

                    # Step 3 - Storing the optimum results to a list in descending order
                    list_1 = [
                        'Designation', 'Section class', 'Effective area', 'Buckling_curve_zz', 'IF_zz', 'Effective_length_zz', 'Effective_SR_zz',
                        'EBS_zz', 'ND_ESR_zz', 'phi_zz', 'SRF_zz', 'FCD_1_zz', 'FCD_2', 'FCD_zz', 'FCD', 'Capacity', 'UR', 'Cost', 'Designation',
                        'Section class', 'Effective area', 'Buckling_curve_yy', 'IF_yy', 'Effective_length_yy', 'Effective_SR_yy', 'EBS_yy',
                        'ND_ESR_yy', 'phi_yy', 'SRF_yy', 'FCD_1_yy', 'FCD_2', 'FCD_yy', 'FCD', 'Capacity', 'UR', 'Cost'
                    ]

                    # 1- Based on optimum UR
                    self.optimum_section_ur_results[self.ur] = {}
                    list_2 = self.list_zz + self.list_yy
                    for j in list_1:
                        for k in list_2:
                            self.optimum_section_ur_results[self.ur][j] = k
                            list_2.pop(0)
                            break

                    # 2- Based on optimum cost
                    self.optimum_section_cost_results[self.cost] = {}
                    list_2 = self.list_zz + self.list_yy
                    for j in list_1:
                        for k in list_2:
                            self.optimum_section_cost_results[self.cost][j] = k
                            list_2.pop(0)
                            break

        except Exception as e:
            self.logger.error(f"Exception in design_column: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.design_status = False
            self.failed_design_dict = {}
            return
        # Print summary ONCE after all calculations
        summary_lines = []
        summary_lines.append("=== DESIGN SUMMARY ===")
        summary_lines.append(f"Input section list: {self.input_section_list}")
        summary_lines.append(f"Optimum URs: {self.optimum_section_ur}")
        best_ur = None
        best_section_results = None
        if self.optimum_section_ur:
            best_ur = min(self.optimum_section_ur, key=lambda x: abs(x-1.0))  # closest to 1.0
            summary_lines.append(f"Best UR: {best_ur}")
            best_section_results = self.optimum_section_ur_results[best_ur]
            summary_lines.append(f"Best Section Results: {best_section_results}")
        summary_lines.append("======================")
        summary_text = "\n".join(summary_lines)
        # self.logger.info(summary_text)
        # Store for output dock
        self.design_summary = {
            'input_section_list': self.input_section_list,
            'optimum_section_ur': self.optimum_section_ur,
            'best_ur': best_ur,
            'best_section_results': best_section_results,
            'summary_text': summary_text
        }
    def store_additional_outputs(self, d=None, t=None, l=None, spacing=None, c_spacing=None, ur=None):
        """
        Store additional calculated outputs for tie plate, lacing, and channel spacing in self.result and, if ur is provided, in self.optimum_section_ur_results[ur].
        """
        if d is not None:
            self.result['tie_plate_d'] = d
        if t is not None:
            self.result['tie_plate_t'] = t
        if l is not None:
            self.result['tie_plate_l'] = l
        if spacing is not None:
            self.result['lacing_spacing'] = spacing
        if c_spacing is not None:
            self.result['channel_spacing'] = c_spacing
        # Also store in optimum_section_ur_results[ur] if ur is provided
        if ur is not None and hasattr(self, 'optimum_section_ur_results') and ur in self.optimum_section_ur_results:
            if d is not None:
                self.optimum_section_ur_results[ur]['tie_plate_d'] = d
            if t is not None:
                self.optimum_section_ur_results[ur]['tie_plate_t'] = t
            if l is not None:
                self.optimum_section_ur_results[ur]['tie_plate_l'] = l
            if spacing is not None:
                self.optimum_section_ur_results[ur]['lacing_spacing'] = spacing
            if c_spacing is not None:
                self.optimum_section_ur_results[ur]['channel_spacing'] = c_spacing
                
    def results(self):
        # Prevent duplicate logs in a single calculation
        if not hasattr(self, 'design_status_list') or self.design_status_list is None or not isinstance(self.design_status_list, list):
            self.design_status_list = []
        if hasattr(self, '_already_logged_failure'):
            del self._already_logged_failure

        if not self.optimum_section_ur:
            error_msg = "No sections available for design. Please check your input or section list."
            self.logger.error(error_msg)
            self.failed_reason = error_msg
            self.design_status = False
            self.failed_design_dict = {}
            return

        if len(self.optimum_section_ur) == 0:  # no design was successful
            if not hasattr(self, '_already_logged_failure'):
                self._already_logged_failure = True
                error_msg = "The sections selected by the solver from the defined list of sections did not satisfy the Utilization Ratio (UR) criteria"
                self.logger.warning(error_msg)
                self.logger.error("The solver did not find any adequate section from the defined list.")
                self.logger.info("Re-define the list of sections or check the Design Preferences option and re-design.")
                self.failed_reason = error_msg
            self.design_status = False
            if self.failed_design_dict is None or not isinstance(self.failed_design_dict, dict):
                self.failed_design_dict = {}
            if self.failed_design_dict and isinstance(self.failed_design_dict, dict) and len(self.failed_design_dict) > 0:
                self.logger.info("The details for the best section provided is being shown")
                self.result_UR = self.failed_design_dict.get('UR', None)
                self.common_result(
                    list_result=self.failed_design_dict,
                    result_type=None,
                )
                self.logger.warning("Re-define the list of sections or check the Design Preferences option and re-design.")
                return
            self.failed_design_dict = {}  # Always a dict for downstream code
            return

        _ = [i for i in self.optimum_section_ur if i > 1.0]

        if len(_)==1:
            temp = _[0]
        elif len(_)==0:
            temp = None
        else:
            temp = sorted(_)[0]
        self.failed_design_dict = self.optimum_section_ur_results[temp] if temp is not None else None

        # results based on UR
        if self.optimization_parameter == 'Utilization Ratio':
            # Debug logging
            self.logger.info(f"Before filtering: optimum_section_ur = {self.optimum_section_ur}")
            self.logger.info(f"allowable_utilization_ratio = {self.allowable_utilization_ratio}")
            
            filter_UR = filter(lambda x: x <= min(self.allowable_utilization_ratio, 1.0), self.optimum_section_ur)
            self.optimum_section_ur = list(filter_UR)
            
            self.logger.info(f"After filtering: optimum_section_ur = {self.optimum_section_ur}")

            self.optimum_section_ur.sort()

            # selecting the section with most optimum UR
            if len(self.optimum_section_ur) == 0:  # no design was successful
                error_msg = f"The sections selected by the solver from the defined list of sections did not satisfy the Utilization Ratio (UR) criteria. Allowable UR: {self.allowable_utilization_ratio}"
                self.logger.warning(error_msg)
                self.logger.error("The solver did not find any adequate section from the defined list.")
                self.logger.info("Re-define the list of sections or check the Design Preferences option and re-design.")
                self.failed_reason = error_msg
                self.design_status = False
                
                # Fallback: If we have results but they were filtered out, show the best one anyway
                if hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                    self.logger.info("Showing best available result despite UR filter failure")
                    best_ur = min(self.optimum_section_ur_results.keys())
                    self.result_UR = best_ur
                    self.common_result(
                        list_result=self.optimum_section_ur_results,
                        result_type=best_ur,
                    )
                    return
                
                if self.failed_design_dict and isinstance(self.failed_design_dict, dict) and len(self.failed_design_dict) > 0:
                    self.logger.info(
                    "The details for the best section provided is being shown"
                )
                    self.result_UR = self.failed_design_dict.get('UR', None) #temp  
                    self.common_result(
                        list_result=self.failed_design_dict,
                        result_type=None,
                    )
                    self.logger.warning(
                    "Re-define the list of sections or check the Design Preferences option and re-design."
                )
                    return

            self.failed_design_dict = {}
            self.result_UR = self.optimum_section_ur[-1]  # optimum section which passes the UR check

            self.design_status = True
            if self.result_UR in self.optimum_section_ur_results:
                self.common_result(
                    list_result=self.optimum_section_ur_results,
                    result_type=self.result_UR,
                )
            else:
                error_msg = f"Result UR {self.result_UR} not found in optimum_section_ur_results. No valid design result to display."
                self.logger.error(error_msg)
                self.failed_reason = error_msg
                self.design_status = False
        else:  # results based on cost
            self.optimum_section_cost.sort()

            # selecting the section with most optimum cost
            self.result_cost = self.optimum_section_cost[0]
            self.design_status = True

        for status in self.design_status_list:
            if status is False:
                self.design_status = False
                break
            else:
                self.design_status = True

        if self.design_status:
            self.logger.info(": ========== Design Status ============")
            self.logger.info(": Overall Column design is SAFE")
            self.logger.info(": ========== End Of Design ============")
        else:
            self.logger.info(": ========== Design Status ============")
            self.logger.info(": Overall Column design is UNSAFE")
            if self.failed_reason:
                self.logger.info(f": Failure Reason: {self.failed_reason}")
            self.logger.info(": ========== End Of Design ============")

    ### start writing save_design from here!
    """def save_design(self, popup_summary):

        if self.connectivity == 'Hollow/Tubular Column Base':
            if self.dp_column_designation[1:4] == 'SHS':
                select_section_img = 'SHS'
            elif self.dp_column_designation[1:4] == 'RHS':
                select_section_img = 'RHS'
            else:
                select_section_img = 'CHS'
        else:
            if self.column_properties.flange_slope != 90:
                select_section_img = "Slope_Beam"
            else:
                select_section_img = "Parallel_Beam" """
    
    def common_result(self, list_result, result_type):
        # Defensive: handle None or wrong type for list_result
        if not isinstance(list_result, dict) or not list_result:
            self.logger.error("No valid results to display. Calculation did not yield any results.")
            # Set all result attributes to None or a safe default
            self.result_designation = None
            self.section_class = None
            self.result_section_class = None
            self.result_effective_area = None
            self.result_bc_zz = None
            self.result_bc_yy = None
            self.result_IF_zz = None
            self.result_IF_yy = None
            self.result_eff_len_zz = None
            self.result_eff_len_yy = None
            self.result_eff_sr_zz = None
            self.result_eff_sr_yy = None
            self.result_ebs_zz = None
            self.result_ebs_yy = None
            self.result_nd_esr_zz = None
            self.result_nd_esr_yy = None
            self.result_phi_zz = None
            self.result_phi_yy = None
            self.result_srf_zz = None
            self.result_srf_yy = None
            self.result_fcd_1_zz = None
            self.result_fcd_1_yy = None
            self.result_fcd_2 = None
            self.result_fcd_zz = None
            self.result_fcd_yy = None
            self.result_fcd = None
            self.result_capacity = None
            self.result_cost = None
            return

        # Defensive: handle None or missing result_type
        if result_type is None:
            # Try to get the first key if possible
            if list_result:
                result_type = next(iter(list_result.keys()))
            else:
                self.logger.error("No result type found in results.")
                return

        # Defensive: check if result_type exists in list_result
        if result_type not in list_result:
            self.logger.error(f"Result type '{result_type}' not found in results.")
            return

        # Now safe to access
        try:
            self.result_designation = list_result[result_type].get('Designation', None)
            self.section_class = self.input_section_classification.get(self.result_designation, [None])[0]

            if self.section_class == 'Slender':
                self.logger.warning(f"The trial section ({self.result_designation}) is Slender. Computing the Effective Sectional Area as per Sec. 9.7.2, Fig. 2 (B & C) of The National Building Code of India (NBC), 2016.")
            if getattr(self, 'effective_area_factor', 1.0) < 1.0:
                self.effective_area = round(self.effective_area * self.effective_area_factor, 2)
                self.logger.warning("Reducing the effective sectional area as per the definition in the Design Preferences tab.")
                self.logger.info(f"The actual effective area is {round((self.effective_area / self.effective_area_factor), 2)} mm2 and the reduced effective area is {self.effective_area} mm2 [Reference: Cl. 7.3.2, IS 800:2007]")
            else:
                if self.section_class != 'Slender':
                    self.logger.info("The effective sectional area is taken as 100% of the cross-sectional area [Reference: Cl. 7.3.2, IS 800:2007].")
            if self.result_designation in self.input_section_classification:
                # Safe rounding function
                def safe_round(value, decimals=2):
                    if value is None:
                        return None
                    try:
                        return round(float(value), decimals)
                    except (ValueError, TypeError):
                        return None
                
                classification = self.input_section_classification[self.result_designation]
                flange_value = safe_round(classification[3] if len(classification) > 3 else None)
                web_value = safe_round(classification[4] if len(classification) > 4 else None)
                
                self.logger.info(
                    "The section is {}. The {} section  has  {} flange({}) and  {} web({}).  [Reference: Cl 3.7, IS 800:2007].".format(
                        classification[0] if len(classification) > 0 else 'Unknown',
                        self.result_designation,
                        classification[1] if len(classification) > 1 else 'Unknown', flange_value,
                        classification[2] if len(classification) > 2 else 'Unknown', web_value
                    ))

            self.result_section_class = list_result[result_type].get('Section class', None)
            self.result_effective_area = list_result[result_type].get('Effective area', None)
            self.result_bc_zz = list_result[result_type].get('Buckling_curve_zz', None)
            self.result_bc_yy = list_result[result_type].get('Buckling_curve_yy', None)
            self.result_IF_zz = list_result[result_type].get('IF_zz', None)
            self.result_IF_yy = list_result[result_type].get('IF_yy', None)
            self.result_eff_len_zz = list_result[result_type].get('Effective_length_zz', None)
            self.result_eff_len_yy = list_result[result_type].get('Effective_length_yy', None)
            self.result_eff_sr_zz = list_result[result_type].get('Effective_SR_zz', None)
            self.result_eff_sr_yy = list_result[result_type].get('Effective_SR_yy', None)
            self.result_ebs_zz = list_result[result_type].get('EBS_zz', None)
            self.result_ebs_yy = list_result[result_type].get('EBS_yy', None)
            self.result_nd_esr_zz = list_result[result_type].get('ND_ESR_zz', None)
            self.result_nd_esr_yy = list_result[result_type].get('ND_ESR_yy', None)
            self.result_phi_zz = list_result[result_type].get('phi_zz', None)
            self.result_phi_yy = list_result[result_type].get('phi_yy', None)
            self.result_srf_zz = list_result[result_type].get('SRF_zz', None)
            self.result_srf_yy = list_result[result_type].get('SRF_yy', None)
            self.result_fcd_1_zz = list_result[result_type].get('FCD_1_zz', None)
            self.result_fcd_1_yy = list_result[result_type].get('FCD_1_yy', None)
            self.result_fcd_2 = list_result[result_type].get('FCD_2', None)
            self.result_fcd_zz = list_result[result_type].get('FCD_zz', None)
            self.result_fcd_yy = list_result[result_type].get('FCD_yy', None)
            self.result_fcd = list_result[result_type].get('FCD', None)
            self.result_capacity = list_result[result_type].get('Capacity', None)
            self.result_cost = list_result[result_type].get('Cost', None)
        except Exception as e:
            self.logger.error(f"Error extracting results: {e}")
            # Set all result attributes to None or a safe default
            self.result_designation = None
            self.section_class = None
            self.result_section_class = None
            self.result_effective_area = None
            self.result_bc_zz = None
            self.result_bc_yy = None
            self.result_IF_zz = None
            self.result_IF_yy = None
            self.result_eff_len_zz = None
            self.result_eff_len_yy = None
            self.result_eff_sr_zz = None
            self.result_eff_sr_yy = None
            self.result_ebs_zz = None
            self.result_ebs_yy = None
            self.result_nd_esr_zz = None
            self.result_nd_esr_yy = None
            self.result_phi_zz = None
            self.result_phi_yy = None
            self.result_srf_zz = None
            self.result_srf_yy = None
            self.result_fcd_1_zz = None
            self.result_fcd_1_yy = None
            self.result_fcd_2 = None
            self.result_fcd_zz = None
            self.result_fcd_yy = None
            self.result_fcd = None

    def save_design(self, popup_summary):
        # Safe rounding function for all round operations
        def safe_round(value, decimals=2):
            if value is None:
                return None
            try:
                return round(float(value), decimals)
            except (ValueError, TypeError):
                return None
        
        # Safe access to classification values
        def safe_classification_value(designation, index, default=None):
            if (designation in self.input_section_classification and 
                isinstance(self.input_section_classification[designation], (list, tuple)) and 
                len(self.input_section_classification[designation]) > index):
                return self.input_section_classification[designation][index]
            return default

        if self.design_status:
            if (self.design_status and self.failed_design_dict is None) or (not self.design_status and self.failed_design_dict is not None and hasattr(self.failed_design_dict, '__len__') and len(self.failed_design_dict) > 0):
                if self.sec_profile=='Columns' or self.sec_profile=='Beams' or self.sec_profile == VALUES_SEC_PROFILE[0]:
                    try:
                        result = Beam(designation=self.result_designation, material_grade=self.material)
                    except:
                        result = Column(designation=self.result_designation, material_grade=self.material)
                    self.section_property = result
                    self.report_column = {KEY_DISP_SEC_PROFILE: "ISection",
                                        KEY_DISP_SECSIZE: (self.section_property.designation, self.sec_profile),
                                        KEY_DISP_COLSEC_REPORT: self.section_property.designation,
                                        KEY_DISP_MATERIAL: self.section_property.material,
            #                                 KEY_DISP_APPLIED_AXIAL_FORCE: self.section_property.,
                                        KEY_REPORT_MASS: self.section_property.mass,
                                        KEY_REPORT_AREA: safe_round(self.section_property.area * 1e-2, 2),
                                        KEY_REPORT_DEPTH: self.section_property.depth,
                                        KEY_REPORT_WIDTH: self.section_property.flange_width,
                                        KEY_REPORT_WEB_THK: self.section_property.web_thickness,
                                        KEY_REPORT_FLANGE_THK: self.section_property.flange_thickness,
                                        KEY_DISP_FLANGE_S_REPORT: self.section_property.flange_slope,
                                        KEY_REPORT_R1: self.section_property.root_radius,
                                        KEY_REPORT_R2: self.section_property.toe_radius,
                                        KEY_REPORT_IZ: round(self.section_property.mom_inertia_z * 1e-4, 2),
                                        KEY_REPORT_IY: round(self.section_property.mom_inertia_y * 1e-4, 2),
                                        KEY_REPORT_RZ: round(self.section_property.rad_of_gy_z * 1e-1, 2),
                                        KEY_REPORT_RY: round(self.section_property.rad_of_gy_y * 1e-1, 2),
                                        KEY_REPORT_ZEZ: round(self.section_property.elast_sec_mod_z * 1e-3, 2),
                                        KEY_REPORT_ZEY: round(self.section_property.elast_sec_mod_y * 1e-3, 2),
                                        KEY_REPORT_ZPZ: round(self.section_property.plast_sec_mod_z * 1e-3, 2),
                                        KEY_REPORT_ZPY: round(self.section_property.plast_sec_mod_y * 1e-3, 2)}
                else:
                    #Update for section profiles RHS and SHS, CHS by making suitable elif condition.
                    self.report_column = {KEY_DISP_COLSEC_REPORT: getattr(self.section_property, 'designation', None),
                                        KEY_DISP_MATERIAL: getattr(self.section_property, 'material', ''),
                                        #                                 KEY_DISP_APPLIED_AXIAL_FORCE: getattr(self.section_property, 'applied_axial_force', ''),
                                        KEY_REPORT_MASS: getattr(self.section_property, 'mass', ''),
                                        KEY_REPORT_AREA: safe_round(getattr(self.section_property, 'area', 0) * 1e-2, 2),
                                        KEY_REPORT_DEPTH: getattr(self.section_property, 'depth', ''),
                                        KEY_REPORT_WIDTH: getattr(self.section_property, 'flange_width', ''),
                                        KEY_REPORT_WEB_THK: getattr(self.section_property, 'web_thickness', ''),
                                        KEY_REPORT_FLANGE_THK: getattr(self.section_property, 'flange_thickness', ''),
                                        KEY_DISP_FLANGE_S_REPORT: getattr(self.section_property, 'flange_slope', '')}


                self.report_input = \
                    {#KEY_MAIN_MODULE: self.mainmodule,
                    KEY_MODULE: self.module, #"Axial load on column "
                        KEY_DISP_AXIAL: self.load.axial_force * 10 ** -3,
                        KEY_DISP_ACTUAL_LEN_ZZ: self.length_zz,
                        KEY_DISP_ACTUAL_LEN_YY: self.length_yy,
                        KEY_DISP_SEC_PROFILE: self.sec_profile,
                        KEY_DISP_SECSIZE: self.result_section_class,
                        KEY_DISP_END1: self.end_1_z,
                        KEY_DISP_END2: self.end_2_z,
                        KEY_DISP_END1_Y: self.end_1_y,
                        KEY_DISP_END2_Y: self.end_2_y,
                        "Column Section - Mechanical Properties": "TITLE",
                    KEY_MATERIAL: self.material,
                        KEY_DISP_ULTIMATE_STRENGTH_REPORT: self.material_property.fu,
                        KEY_DISP_YIELD_STRENGTH_REPORT: self.material_property.fy,
                        KEY_DISP_EFFECTIVE_AREA_PARA: self.effective_area_factor, #To Check
                        KEY_DISP_SECSIZE:  str(self.sec_list),
                        "Selected Section Details": self.report_column,
                    }

                self.report_check = []
                t1 = ('Selected', 'Selected Member Data', '|p{5cm}|p{2cm}|p{2cm}|p{2cm}|p{4cm}|')
                self.report_check.append(t1)

                self.h = (self.section_property.depth - 2 * (self.section_property.flange_thickness + self.section_property.root_radius))
                self.h_bf_ratio = self.h / self.section_property.flange_width


                # 2.2 CHECK: Buckling Class - Compatibility Check
                t1 = ('SubSection', 'Buckling Class - Compatibility Check', '|p{4cm}|p{3.5cm}|p{6.5cm}|p{2cm}|')
                self.report_check.append(t1)

                # YY axis row
                t1 = (
                    "h/bf and tf for YY Axis", 
                    comp_column_class_section_check_required(self.h, self.section_property.flange_width, self.section_property.flange_thickness, "YY"),  
                    comp_column_class_section_check_provided(self.h, self.section_property.flange_width, self.section_property.flange_thickness, round(self.h_bf_ratio, 2), "YY"), 'Compatible'  
                )
                self.report_check.append(t1)

                # ZZ axis row
                t1 = (
                    "h/bf and tf for ZZ Axis", 
                    comp_column_class_section_check_required(self.h, self.section_property.flange_width, self.section_property.flange_thickness, "ZZ"), 
                    comp_column_class_section_check_provided(self.h, self.section_property.flange_width, self.section_property.flange_thickness, round(self.h_bf_ratio, 2), "ZZ"), 'Compatible'  
                )
                self.report_check.append(t1)

                t1 = ('SubSection', 'Section Classification', '|p{3cm}|p{3.5cm}|p{8.5cm}|p{1cm}|')
                self.report_check.append(t1)
                t1 = ('Web Class', 'Axial Compression',
                        cl_3_7_2_section_classification_web(round(self.h, 2), round(self.section_property.web_thickness, 2), 
                                                          safe_round(safe_classification_value(self.result_designation, 4)),
                                                          self.epsilon, self.section_property.type,
                                                          safe_classification_value(self.result_designation, 2)),
                        ' ')
                self.report_check.append(t1)
                t1 = ('Flange Class', self.section_property.type,
                        cl_3_7_2_section_classification_flange(round(self.section_property.flange_width/2, 2),
                                                            round(self.section_property.flange_thickness, 2),
                                    safe_round(safe_classification_value(self.result_designation, 3)),
                                                            self.epsilon,
                                                            safe_classification_value(self.result_designation, 1)),
                        ' ')
                self.report_check.append(t1)
                t1 = ('Section Class', ' ',
                        cl_3_7_2_section_classification(
                                                            self.input_section_classification[self.result_designation][0]),
                        ' ')
                self.report_check.append(t1)
                

                t1 = ('NewTable', 'Imperfection Factor', '|p{3cm}|p{5 cm}|p{5cm}|p{3 cm}|')
                self.report_check.append(t1)

                t1 = (
                    'YY',
                    self.list_yy[3].upper(),
                    self.list_yy[4], ''
                )
                self.report_check.append(t1)

                t1 = (
                    'ZZ',
                    self.list_zz[3].upper(),
                    self.list_zz[4], ''
                )
                self.report_check.append(t1)


                # Defensive checks for None before division/round
                if self.result_eff_len_yy is not None and self.length_yy:
                    K_yy = self.result_eff_len_yy / self.length_yy
                else:
                    K_yy = None
                if self.result_eff_len_zz is not None and self.length_zz:
                    K_zz = self.result_eff_len_zz / self.length_zz
                else:
                    K_zz = None
                t1 = ('SubSection', 'Slenderness Ratio', '|p{4cm}|p{2 cm}|p{7cm}|p{3 cm}|')
                self.report_check.append(t1)
                val_yy = safe_float(self.result_eff_sr_yy)
                val_zz = safe_float(self.result_eff_sr_zz)
                val_yy_rounded = round(val_yy if val_yy is not None else 0.0, 2)
                val_zz_rounded = round(val_zz if val_zz is not None else 0.0, 2)
                t1 = ("Effective Slenderness Ratio (For YY Axis)", ' ',
                      cl_7_1_2_effective_slenderness_ratio(K_yy, self.length_yy, self.section_property.rad_of_gy_y, val_yy_rounded),
                      ' ')
                self.report_check.append(t1)
                t1 = ("Effective Slenderness Ratio (For ZZ Axis)", ' ',
                      cl_7_1_2_effective_slenderness_ratio(K_zz, self.length_zz, self.section_property.rad_of_gy_z, val_zz_rounded),
                      ' ')
                self.report_check.append(t1)



                t1 = ('SubSection', 'Checks', '|p{4cm}|p{2 cm}|p{7cm}|p{3 cm}|')
                self.report_check.append(t1)
                                
                t1 = (r'$\phi_{yy}$', ' ',
                    cl_8_7_1_5_phi(self.result_IF_yy, safe_round(self.non_dim_eff_sr_yy, 2), safe_round(self.result_phi_yy, 2)),
                    ' ')
                self.report_check.append(t1)

                t1 = (r'$\phi_{zz}$', ' ',
                    cl_8_7_1_5_phi(self.result_IF_zz, safe_round(self.non_dim_eff_sr_zz, 2), safe_round(self.result_phi_zz, 2)),
                    ' ')
                self.report_check.append(t1)

                t1 = (r'$F_{cd,yy} \, \left( \frac{N}{\text{mm}^2} \right)$', ' ',
                    cl_8_7_1_5_Buckling(
                        str(self.material_property.fy) if self.material_property.fy is not None else '',
                        str(self.gamma_m0) if self.gamma_m0 is not None else '',
                        str(safe_round(self.non_dim_eff_sr_yy, 2)),
                        str(safe_round(self.result_phi_yy, 2)),
                        str(safe_round(self.result_fcd_2, 2)),
                        str(safe_round(self.result_fcd_yy, 2)),
                    ),
                    ' ')
                self.report_check.append(t1)

                t1 = (r'$F_{cd,zz} \, \left( \frac{N}{\text{mm}^2} \right)$', ' ',
                    cl_8_7_1_5_Buckling(
                        str(self.material_property.fy) if self.material_property.fy is not None else '',
                        str(self.gamma_m0) if self.gamma_m0 is not None else '',
                        str(safe_round(self.non_dim_eff_sr_zz, 2)),
                        str(safe_round(self.result_phi_zz, 2)),
                        str(safe_round(self.result_fcd_2, 2)),
                        str(safe_round(self.result_fcd_zz, 2)),
                    ),
                    ' ')
                self.report_check.append(t1)

                # Defensive: check for None before division/round for result_capacity and result_fcd
                cap = self.result_capacity if self.result_capacity is not None else 0.0
                fcd = self.result_fcd if self.result_fcd is not None else 0.0
                area = self.section_property.area if self.section_property and hasattr(self.section_property, 'area') else 0.0
                t1 = (r'Design Compressive Strength (\( P_d \)) (For the most critical value of \( F_{cd} \))', self.load.axial_force * 10 ** -3,
                    cl_7_1_2_design_compressive_strength(safe_round(cap / 1000, 2), area, safe_round(fcd, 2), self.load.axial_force * 10 ** -3),
                    get_pass_fail(self.load.axial_force * 10 ** -3, safe_round(cap, 2), relation="leq"))
                self.report_check.append(t1)

            else:
                self.report_input = \
                    {#KEY_MAIN_MODULE: self.mainmodule,
                    KEY_MODULE: self.module, #"Axial load on column "
                        KEY_DISP_AXIAL: self.load.axial_force * 10 ** -3,
                        KEY_DISP_ACTUAL_LEN_ZZ: self.length_zz,
                        KEY_DISP_ACTUAL_LEN_YY: self.length_yy,
                        KEY_DISP_SEC_PROFILE: self.sec_profile,
                        KEY_DISP_SECSIZE:  str(self.sec_list),
                        #KEY_DISP_SECSIZE: self.result_section_class,
                        KEY_DISP_END1: self.end_1_z,
                        KEY_DISP_END2: self.end_2_z,
                        KEY_DISP_END1_Y: self.end_1_y,
                        KEY_DISP_END2_Y: self.end_2_y,
                        "Column Section - Mechanical Properties": "TITLE",
                    KEY_MATERIAL: self.material,
                        KEY_DISP_ULTIMATE_STRENGTH_REPORT: self.material_property.fu,
                        KEY_DISP_YIELD_STRENGTH_REPORT: self.material_property.fy,
                        KEY_DISP_EFFECTIVE_AREA_PARA: self.effective_area_factor, #To Check
                        
                        # "Failed Section Details": self.report_column,
                    }
                self.report_check = []

                t1 = ('Selected', 'All Members Failed', '|p{5cm}|p{2cm}|p{2cm}|p{2cm}|p{4cm}|')
                self.report_check.append(t1)


            Disp_2d_image = []
            Disp_3D_image = "/ResourceFiles/images/3d.png"


            rel_path = str(sys.path[0])
            rel_path = os.path.abspath(".") # TEMP
            rel_path = rel_path.replace("\\", "/")
            fname_no_ext = popup_summary['filename']
            CreateLatex.save_latex(CreateLatex(), self.report_input, self.report_check, popup_summary, fname_no_ext,
                                  rel_path, Disp_2d_image, Disp_3D_image, module=self.module) 
        
    def get_end_conditions(self, *args):
        """
        Returns the list of standard end conditions for both y-y and z-z axes.
        These values are used in dropdowns for End 1 and End 2.
        """
        return ["Fixed", "Pinned", "Free"]
        
class SectionDesignationDialog(QDialog):
    def __init__(self, section_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Section Designations")
        self.setModal(True)
        self.selected_sections = []
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.addItems(section_list)
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.list_widget)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected(self):
        return [item.text() for item in self.list_widget.selectedItems()]

    def get_section_class(self, flange_class, web_class):
        # Helper to determine section class from flange and web
        if flange_class == 'Plastic' and web_class == 'Plastic':
            return 'Plastic'
        elif 'Plastic' in [flange_class, web_class] and 'Compact' in [flange_class, web_class]:
            return 'Compact'
        elif 'Plastic' in [flange_class, web_class] and 'Semi-Compact' in [flange_class, web_class]:
            return 'Semi-Compact'
        elif flange_class == 'Compact' and web_class == 'Compact':
            return 'Compact'
        elif 'Compact' in [flange_class, web_class] and 'Semi-Compact' in [flange_class, web_class]:
            return 'Semi-Compact'
        elif flange_class == 'Semi-Compact' and web_class == 'Semi-Compact':
            return 'Semi-Compact'
        else:
            return 'Slender'

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def get_fu_fy_I_section(self, *args):
        """
        Override to accept arguments as passed from tab_change (material, designation_dict).
        Handles both single and multiple selections robustly.
        """
        if len(args) < 2:
            return {}
        material_grade = args[0]
        designation_dict = args[1]
        # Defensive: handle both dict and string for designation
        designation = None
        if isinstance(designation_dict, dict):
            designation = designation_dict.get(KEY_SECSIZE, "Select Section")
        elif isinstance(designation_dict, str):
            designation = designation_dict
        else:
            designation = "Select Section"
        # Handle multiple selections (list)
        if isinstance(designation, list):
            designation = designation[0] if designation else "Select Section"
        if isinstance(material_grade, list):
            material_grade = material_grade[0] if material_grade else "Select Material"
        fu = ''
        fy = ''
        if material_grade != "Select Material" and designation != "Select Section":
            table = "Beams" if designation in connectdb("Beams", "popup") else "Columns"
            I_sec_attributes = ISection(designation)
            I_sec_attributes.connect_to_database_update_other_attributes(table, designation, material_grade)
            fu = str(I_sec_attributes.fu)
            fy = str(I_sec_attributes.fy)
        d = {KEY_SUPTNGSEC_FU: fu,
             KEY_SUPTNGSEC_FY: fy,
             KEY_SUPTDSEC_FU: fu,
             KEY_SUPTDSEC_FY: fy,
             KEY_SEC_FU: fu,
             KEY_SEC_FY: fy}
        return d

def test_dialog(self):
        """
        Test method to verify dialog creation and display
        """
        print("Testing dialog creation...")
        try:
            # Test with some dummy sections
            test_sections = ["ISMB 100", "ISMB 125", "ISMB 150", "ISMB 175", "ISMB 200"]
            dialog = SectionDesignationDialog(test_sections)
            print(f"Dialog created with {len(test_sections)} test sections")
            
            # Test showing the dialog
            result = dialog.exec_()
            print(f"Dialog test result: {result}")
            
            if result == QDialog.Accepted:
                selected = dialog.get_selected()
                print(f"Selected sections: {selected}")
                return selected
            else:
                print("Dialog was cancelled in test")
                return None
                
        except Exception as e:
            print(f"ERROR in test_dialog: {e}")
            import traceback
            traceback.print_exc()
            return None


# // ... existing code ...
#             if output_type == TYPE_TEXTBOX:
#                 r = QtWidgets.QLineEdit(self.dockWidgetContents_out)
#                 r.setObjectName(option[0])
#                 r.setReadOnly(True)
#                 out_layout2.addWidget(r, j, 2, 1, 1)
#                 r.setVisible(True if option[4] else False)
#                 fields += 1
#                 if current_key is not None and current_key in self.output_title_fields:
#                     if isinstance(self.output_title_fields[current_key], (list, tuple)) and len(self.output_title_fields[current_key]) > 1:
#                         self.output_title_fields[current_key][1] = fields
#                 maxi_width_right = max(maxi_width_right, 100)    # predefined minimum width of 110 for textboxes
# // ... existing code ...
#             if output_type == TYPE_OUT_BUTTON:
#                 v = option[3]
#                 b = QtWidgets.QPushButton(self.dockWidgetContents_out)
#                 b.setObjectName(option[0])
#                 #b.setFixedSize(b.size())
#                 b.resize(b.sizeHint().width(), b.sizeHint().height()+100)
#                 b.setText(v[0])
#                 b.setDisabled(True)
#                 b.setVisible(True if option[4] else False)
#                 fields += 1
#                 if current_key is not None and current_key in self.output_title_fields:
#                     if isinstance(self.output_title_fields[current_key], (list, tuple)) and len(self.output_title_fields[current_key]) > 1:
#                         self.output_title_fields[current_key][1] = fields
#                 #b.setFixedSize(b.size())
#                 button_list.append(option)
#                 out_layout2.addWidget(b, j, 2, 1, 1)
#                 maxi_width_right = max(maxi_width_right, b.sizeHint().width())
# // ... existing code ...