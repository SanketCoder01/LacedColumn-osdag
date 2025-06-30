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


class BattenedColumn(Member):
    def __init__(self):
        super(BattenedColumn, self).__init__()
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
        self.module = KEY_DISP_COMPRESSION_BattenedColumn
        self.mainmodule = 'Member'
        
        # Initialize output_title_fields
        self.output_title_fields = {}
        
        # Initialize design preferences with default values
        self.design_pref_dictionary = {
            KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA: "1.0",                 
            KEY_DISP_BATTENEDCOL_ALLOWABLE_UR: "1.0",                    
            KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE: "Angle",           
            KEY_DISP_BATTENEDCOL_LACING_PROFILE: "ISA 40x40x5",        
            KEY_DISP_BATTENEDCOL_BOLT_DIAMETER: "16mm",                  
            KEY_DISP_BATTENEDCOL_WELD_SIZE: "5mm"                        
            }

        
        # Initialize validators
        self.double_validator = QDoubleValidator()
        self.double_validator.setNotation(QDoubleValidator.StandardNotation)
        self.double_validator.setDecimals(2)


    def tab_list(self):
        return [
                ("Weld Preferences", TYPE_TAB_4, self.all_weld_design_values),  # Existing
                ("Bolt Preferences", TYPE_TAB_5, self.all_bolt_design_values),  # New Tab
                ("General Design Parameters", "TYPE_TAB_6", self.all_general_design_values)  # Custom new tab type
                ]
        
    def all_weld_design_values(self, *args):
        return [
                (KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE, "Lacing Profile Type", TYPE_COMBOBOX,["Angle", "Channel", "Flat"], True, 'No Validator'),
                (KEY_DISP_BATTENEDCOL_LACING_PROFILE, "Lacing Profile Section", TYPE_COMBOBOX_CUSTOMIZED,self.get_lacing_profiles, True, 'No Validator'),
                (KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA, "Effective Area Parameter", TYPE_COMBOBOX,["1.0", "0.9", "0.8", "0.7", "0.6", "0.5", "0.4", "0.3", "0.2", "0.1"], True, 'No Validator'),
                (KEY_DISP_BATTENEDCOL_ALLOWABLE_UR, "Allowable Utilization Ratio", TYPE_COMBOBOX,["1.0", "0.95", "0.9", "0.85"], True, 'No Validator'),
                (KEY_DISP_BATTENEDCOL_BOLT_DIAMETER, "Bolt Diameter", TYPE_COMBOBOX,["16mm", "20mm", "24mm", "27mm"], True, 'No Validator'),
                (KEY_DISP_BATTENEDCOL_WELD_SIZE, "Weld Size", TYPE_COMBOBOX,["4mm", "5mm", "6mm", "8mm"], True, 'No Validator')
                ]
        
    def tab_value_changed(self):
        return [
                ("Weld Preferences", [KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE], [KEY_DISP_BATTENEDCOL_LACING_PROFILE], TYPE_COMBOBOX_CUSTOMIZED,self.get_lacing_profiles)
                ]
        
    def edit_tabs(self):
        return []

    def input_dictionary_design_pref(self):
        return [
        # Tab: Weld Preferences
        ("Weld Preferences", TYPE_COMBOBOX, [
            KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE,
            KEY_DISP_BATTENEDCOL_LACING_PROFILE,
            KEY_DISP_BATTENEDCOL_WELD_SIZE
        ]),

        # Tab: Bolt Preferences
        ("Bolt Preferences", TYPE_COMBOBOX, [
            KEY_DISP_BATTENEDCOL_BOLT_DIAMETER
        ]),

        # Tab: General Design Parameters
        ("General Design Parameters", TYPE_COMBOBOX, [
            KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA,
            KEY_DISP_BATTENEDCOL_ALLOWABLE_UR
        ])
    ]

    def input_dictionary_without_design_pref(self):
        return [
        # Weld Preferences (without tab grouping)
        (None, [
            KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE,
            KEY_DISP_BATTENEDCOL_LACING_PROFILE,
            KEY_DISP_BATTENEDCOL_WELD_SIZE
        ], ''),

        # Bolt Preferences
        (None, [
            KEY_DISP_BATTENEDCOL_BOLT_DIAMETER
        ], ''),

        # General Design Parameters
        (None, [
            KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA,
            KEY_DISP_BATTENEDCOL_ALLOWABLE_UR
        ], '')
    ]
    def get_values_for_design_pref(self, key, design_dictionary):
        """
         Retrieves the user-specified or default design preference value for the given key.
         Parameters:- key: The preference key to retrieve.
         - design_dictionary: Dictionary containing user-specified design preferences.
         Returns:
         - A string value corresponding to the key, either from user input or default.
         """
    # Default values for all FEED-based design preferences
        defaults = {
            KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE: "Angle",         # Default lacing profile type
            KEY_DISP_BATTENEDCOL_LACING_PROFILE: "ISA 40x40x5",        # Default angle section
            KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA: "1.0",                # Default full effective area
            KEY_DISP_BATTENEDCOL_ALLOWABLE_UR: "1.0",                  # Default allowable utilization ratio
            KEY_DISP_BATTENEDCOL_BOLT_DIAMETER: "16mm",                # Default bolt diameter
            KEY_DISP_BATTENEDCOL_WELD_SIZE: "5mm"                      # Default weld size
            }
        # Priority 1: Return user-defined preference if it exists
        if key in design_dictionary:
            return design_dictionary[key]
        # Priority 2: If no user-defined value, return hardcoded default
        if key in defaults:
            return defaults[key]
        # Priority 3: If key is completely unknown, return empty string
        return ""
    
    def get_lacing_profiles(self, *args):
        """
    Returns the default and selectable battening/lacing profile sections
    based on the user's selection of profile type (Angle, Channel, Flat).

    This function supports the FEED task: "Battening Profile Section"
    as defined in the OSDAG Design & Detailing Checklist.

    Parameters:
    - args[0]: Profile type string ("Angle", "Channel", or "Flat")

    Returns:
    - List of profile section strings appropriate for the selected type
    """

        # If no profile type provided, fallback to default for Angle
        if not args or not args[0]:
            return ["ISA 40x40x5"]

        profile_type = args[0]

        # FEED-default profiles as per DDCL:
        if profile_type == "Angle":
            return ["ISA 40x40x5", "ISA 50x50x5", "ISA 60x60x5"]  # Expandable set
        elif profile_type == "Channel":
            return ["ISMC 75", "ISMC 100", "ISMC 125"]
        elif profile_type == "Flat":
            return ["ISF 100x8", "ISF 120x10"]
        # If unknown profile type selected
        return [""]
    
    def set_osdaglogger(self, widget_or_key=None):
        pass
    

    def input_value_changed(self, ui_self=None):
        lst = []
        t8 = ([KEY_BATTENEDCOL_MATERIAL], KEY_BATTENEDCOL_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t8)
        t9 = ([KEY_BATTENEDCOL_SEC_PROFILE], KEY_BATTENEDCOL_SEC_SIZE, TYPE_COMBOBOX_CUSTOMIZED, self.get_section_sizes)
        lst.append(t9)
        t10 = ([KEY_BATT_LYY], KEY_BATTENEDCOL_END_COND_YY, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t10)
        t11 = ([KEY_BATT_LZZ], KEY_BATTENEDCOL_END_COND_ZZ, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t11)
        t12 = ([KEY_BATTENEDCOL_MATERIAL], KEY_BATTENEDCOL_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t12)
        return lst
    
    def generate_latex_report(self):
        if not self.design_status:
            return "Design not safe. No report generated."
        report = CreateLatex()
        report.add_title("Battened Column Design Report")
        report.add_section("Summary", [
            f"Utilization Ratio: {self.utilization_ratio:.2f}",
            f"Design Status: {'Safe' if self.design_status else 'Unsafe'}",
            f"Lacing Angle: {self.lacing_incl_angle}°",
            f"Required Weld Length: {self.result.get('weld_length_required', 'N/A')} mm"
        ])
        report.compile()
        return "Report generation completed."
    

    def input_values(self, ui_self=None):
        self.module = KEY_DISP_BATTENEDCOL
        options_list = []
        options_list.append((KEY_DISP_BATTENEDCOL, "Battened Column", TYPE_MODULE, [], True, 'No Validator'))
        options_list.append(("title_Section", "Section Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_SEC_PROFILE, "Section Profile", TYPE_COMBOBOX, KEY_BATTENEDCOL_SEC_PROFILE_OPTIONS_UI, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_SEC_SIZE, "Section Size", TYPE_COMBOBOX, KEY_BATTENEDCOL_SEC_SIZE_OPTIONS_UI, True, 'No Validator'))
        if ui_self and isinstance(ui_self, dict) and ui_self.get(KEY_BATTENEDCOL_SEC_SIZE) == "User-defined":
            options_list.append((KEY_BATTENEDCOL_CUSTOM_SEC_SIZE, KEY_DISP_BATTENEDCOL_CUSTOM_SEC_SIZE, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_BATTENEDCOL_SPACING, KEY_DISP_BATTENEDCOL_SPACING, TYPE_TEXTBOX, None, False, 'Float Validator'))
        options_list.append(("title_Material", "Material Properties", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_MATERIAL, KEY_DISP_BATTENEDCOL_MATERIAL, TYPE_COMBOBOX, KEY_BATTENEDCOL_MATERIAL_OPTIONS, True, 'No Validator'))
        options_list.append(("title_Geometry", "Geometry", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_UNSUPPORTED_LENGTH_YY, KEY_DISP_BATTENEDCOL_UNSUPPORTED_LENGTH_YY, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_BATTENEDCOL_UNSUPPORTED_LENGTH_ZZ, KEY_DISP_BATTENEDCOL_UNSUPPORTED_LENGTH_ZZ, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_BATTENEDCOL_END_CONDITION_YY_1, KEY_DISP_BATTENEDCOL_END_CONDITION_YY_1, TYPE_COMBOBOX, KEY_BATTENEDCOL_END_CONDITION_OPTIONS, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_END_CONDITION_YY_2, KEY_DISP_BATTENEDCOL_END_CONDITION_YY_2, TYPE_COMBOBOX, KEY_BATTENEDCOL_END_CONDITION_OPTIONS, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_END_CONDITION_ZZ_1, KEY_DISP_BATTENEDCOL_END_CONDITION_ZZ_1, TYPE_COMBOBOX, KEY_BATTENEDCOL_END_CONDITION_OPTIONS, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_END_CONDITION_ZZ_2, KEY_DISP_BATTENEDCOL_END_CONDITION_ZZ_2, TYPE_COMBOBOX, KEY_BATTENEDCOL_END_CONDITION_OPTIONS, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_LACING_PROFILE, KEY_DISP_BATTENEDCOL_LACING_PROFILE, TYPE_COMBOBOX, KEY_BATTENEDCOL_LACING_PROFILE_OPTIONS, True, 'No Validator'))
        options_list.append(("title_Load", "Load Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_BATTENEDCOL_AXIAL_LOAD, KEY_DISP_BATTENEDCOL_AXIAL_LOAD, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_BATTENEDCOL_CONN_TYPE, KEY_DISP_BATTENEDCOL_CONN_TYPE, TYPE_COMBOBOX, KEY_BATTENEDCOL_CONN_TYPE_OPTIONS, True, 'No Validator'))
        return options_list
    
    def module_name(self):
        return KEY_DISP_BATTENEDCOL
    
    def customized_input(self, ui_self=None):
        customized_list = []
        customized_list.append((
        KEY_BATTENEDCOL_SEC_SIZE,
        self.get_section_sizes,
        [],
        "Select the section size based on the chosen profile"
    ))
        customized_list.append((
        KEY_BATTENEDCOL_END_COND_YY,
        self.get_end_conditions,
        [],
        "Select the end condition for y-y axis"
    ))
        customized_list.append((
        KEY_BATTENEDCOL_END_COND_ZZ,
        self.get_end_conditions,
        [],
        "Select the end condition for z-z axis"
    ))
        customized_list.append((
        KEY_BATTENEDCOL_MATERIAL,
        self.new_material,
        [],
        "Material Custom popup"
    ))
        return customized_list

    
    def get_section_sizes(self, *args):
        """
    Returns a list of section sizes based on the selected profile type for Battened Columns.
    If no profile type is provided, defaults to a standard set.
        """
        if not args or not args[0]:
            return ["User-defined", "Optimized"]
        profile_type = args[0]
        if profile_type == "2-channels back-to-back":
            return ["ISMC 100", "ISMC 125", "ISMC 150"]
        elif profile_type == "2-channels front-front":
            return ["ISMC 100", "ISMC 125", "ISMC 200"]
        elif profile_type == "2 Girders":
            return ["ISMB 200", "ISMB 300", "ISMB 400"]
        return ["User-defined"]
    
    def get_end_conditions(self, *args):
        """
    Returns the list of standard end conditions for both y-y and z-z axes.
    These values are used in dropdowns for End 1 and End 2.
        """
        return ["Fixed", "Pinned", "Free"]
    
    def get_lacing_profiles(self, *args):
        """
    Returns available lacing profile sections based on the selected lacing profile type.
    Default is ISA 40x40x5 if no input provided.
        """
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
    
    def module_name(self):
        """
        Returns the display name for the Battened Column module.
        """
        return "Battened Columns"
    
    def spacing(self):
        """
    Returns the spacing value (mm) entered for battened column configuration.
    Used for LaTeX and report generation.
    """
        return self.design_dict.get(KEY_BATTENEDCOL_SPACING, "")
    
    def all_weld_design_values(self, *args):
        return [
        (KEY_DISP_BATTENEDCOL_LACING_PROFILE_TYPE, "Lacing Profile Type", TYPE_COMBOBOX, ["Angle", "Channel", "Flat"], True, 'No Validator'),
        (KEY_DISP_BATTENEDCOL_BATTEN_PROFILE, "Batten Profile Section", TYPE_COMBOBOX_CUSTOMIZED, self.get_lacing_profiles, True, 'No Validator'),
        (KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA, "Effective Area Parameter", TYPE_COMBOBOX, KEY_BATTENEDCOL_EFFECTIVE_AREA_OPTIONS, True, 'No Validator'),
        (KEY_DISP_BATTENEDCOL_ALLOWABLE_UR, "Allowable Utilization Ratio", TYPE_COMBOBOX, KEY_BATTENEDCOL_ALLOWABLE_UR_OPTIONS, True, 'No Validator'),
        (KEY_DISP_BATTENEDCOL_BOLT_DIAMETER, "Bolt Diameter", TYPE_COMBOBOX, KEY_BATTENEDCOL_BOLT_DIAMETER_OPTIONS_UI, True, 'No Validator'),
        (KEY_DISP_BATTENEDCOL_WELD_SIZE, "Weld Size", TYPE_COMBOBOX, KEY_BATTENEDCOL_WELD_SIZE_OPTIONS_UI, True, 'No Validator')
    ]
    
    def get_input_file_name(self):
        """
    Returns the name of the input file for Battened Column module.
    Used for exporting user inputs.
        """
        return "battened_column_input.json"
    
    def get_output_file_name(self):
        """
    Returns the name of the output file for Battened Column module.
    Used for exporting result outputs.
        """
        return "battened_column_output.json"
    
    def get_result(self):
        """
    Returns the final result dictionary after design processing.
    Useful for interfacing with reporting modules or UI.
        """
        return self.result
    
    def design_safe(self):
        """
    Boolean indicator of whether the design is safe.
    Used to determine design pass/fail status in UI.
        """
        return self.design_status
    
    def design_failed_message(self):
        """
    Returns a message to be displayed if design fails.
    Extracts message from result dictionary.
        """
        return self.result.get("message", "Design failed. Please check input parameters.")
    
    def utilization(self):
        """
    Returns the utilization ratio value from result.
        """
        return self.utilization_ratio
    
    def weld_size(self):
        """
    Returns the weld size value.
        """
        return self.weld_size
    
    def output_values(self, flag):
        if not flag:
            return []
        return [
            (None, "Design Summary", TYPE_TITLE, None, True),
            ("section", "Section Profile", TYPE_TEXTBOX, self.result.get("section", ""), True),
            ("material", "Material Grade", TYPE_TEXTBOX, self.result.get("material", ""), True),
            ("load", "Axial Load (kN)", TYPE_TEXTBOX, self.result.get("load", ""), True),
            ("status", "Design Status", TYPE_TEXTBOX, "Safe" if self.result.get("design_safe", False) else "Unsafe", True)
        ]
    
    def func_for_validation(self, design_dict):
        return []
    
    def all_bolt_design_values(self, *args):
        return [
            (KEY_DISP_BATTENEDCOL_BOLT_DIAMETER, "Bolt Diameter", TYPE_COMBOBOX, KEY_BATTENEDCOL_BOLT_DIAMETER_OPTIONS_UI, True, 'No Validator'),
            (KEY_DISP_BATTENEDCOL_BOLT_TYPE, "Bolt Type", TYPE_COMBOBOX, KEY_BATTENEDCOL_BOLT_TYPE_OPTIONS, True, 'No Validator')
            ]
    
    def all_general_design_values(self, *args):
        """
    Returns tuples representing general design parameter options
    for the "General Design Parameters" tab.
    This method resolves the AttributeError by providing this required method.
    """
        return [
            (KEY_DISP_BATTENEDCOL_EFFECTIVE_AREA, "Effective Area Parameter", TYPE_COMBOBOX, ["1.0", "0.9", "0.8", "0.7", "0.6", "0.5", "0.4", "0.3", "0.2", "0.1"], True, 'No Validator'),
            (KEY_DISP_BATTENEDCOL_ALLOWABLE_UR, "Allowable Utilization Ratio", TYPE_COMBOBOX, ["1.0", "0.95", "0.9", "0.85"], True, 'No Validator')]
