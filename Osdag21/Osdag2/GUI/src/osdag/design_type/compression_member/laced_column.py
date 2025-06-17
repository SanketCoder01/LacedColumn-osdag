from typing import Dict, Any, Optional, List, Tuple, Callable
from ..member import Member
from ...Common import *
from ...utils.common.component import ISection, Material
from ...utils.common.common_calculation import *
from ...utils.common.load import Load
from ..tension_member import *
import math
from ...utils.common.component import *
import logging
from ...utils.common.material import *
from ...Report_functions import *
from ...design_report.reportGenerator_latex import CreateLatex
from PyQt5.QtWidgets import QLineEdit, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QTableWidget, QTableWidgetItem, QListWidget, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtGui import QDoubleValidator
import sqlite3
from osdag.design_type.compression_member.LacedColumnDesign import LacedColumnDesign
from osdag.utils.common.component import Bolt

PATH_TO_DATABASE = r"C:\Users\SANKET\Downloads\LacedColumn-osdag-main\LacedColumn-osdag-main\Osdag21\Osdag2\GUI\src\osdag\data\ResourceFiles\Database\Intg_osdag.sqlite"

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
        super().__init__()
        self.design_status = False
        self.design_pref_dialog = None
        self.logger = logging.getLogger('Osdag')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        handler = logging.FileHandler('logging_text.log')
        self.logger.addHandler(handler)
        
        # Initialize design preferences with default values
        self.design_pref_dictionary = {
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
        }

        # Initialize database connection
        self.conn = None
        self.material_data = {}
        self.section_data = {}
        self.section_designation = None
        self.initialize_db_connection()

        # Initialize result dictionary and other attributes
        self.result = {}
        self.material = None
        self.section_size_1 = None
        self.weld_type = None
        self.unsupported_length_yy = 0.0
        self.unsupported_length_zz = 0.0
        self.end_condition_yy = ""
        self.end_condition_zz = ""
        self.lacing_pattern = ""
        self.axial_load = 0.0
        self.utilization_ratio = 0
        self.area = 0
        self.epsilon = 1.0
        self.fy = 0
        self.section = None
        self.weld_size = ''
        self.weld_strength = 0
        self.lacing_incl_angle = 0.0
        self.lacing_section = ''
        self.lacing_type = ''
        self.allowed_utilization = ''
        self.module = KEY_DISP_COMPRESSION_LacedColumn
        self.mainmodule = 'Member'
        
        # Initialize output_title_fields
        self.output_title_fields = {}
        
        # Initialize validators
        self.double_validator = QDoubleValidator()
        self.double_validator.setNotation(QDoubleValidator.StandardNotation)
        self.double_validator.setDecimals(2)
        
        # Initialize result dictionary
        self.initialize_result_dict()

        self.lace_pitch = 0.0  # Initialize lace_pitch attribute
        self.result_tc = 0.0
        self.result_wc = 0.0
        self.result_IF_lt = 0.0
        self.result_srf_lt = 0.0
        self.result_nd_esr_lt = 0.0
        self.result_fcd__lt = 0.0
        self.result_mcr = 0.0

        self.bolt = Bolt(grade=None, diameter=None, bolt_type="Bearing Bolt")

        self.lacing_angle = 0.0  # Initialize lacing_angle attribute
        self.effective_area_param = 0.0  # Initialize effective_area_param attribute

        self.failed_design_dict = {}  # Initialize failed_design_dict attribute

        # Connect the material combo box to the on_material_grade_selected method
        self.material_combo.currentTextChanged.connect(self.on_material_grade_selected)

    def initialize_result_dict(self):
        """
        Initialize the result dictionary with default values.
        """
        self.result = {
            "design_safe": False,
            "message": "",
            "utilization": 0.0,
            "effective_length_yy": 0.0,
            "effective_length_zz": 0.0,
            "end_condition_yy_1": "",
            "end_condition_yy_2": "",
            "end_condition_zz_1": "",
            "end_condition_zz_2": "",
            "slenderness_yy": 0.0,
            "slenderness_zz": 0.0,
            "fcd": 0.0,
            "design_compressive_strength": 0.0,
            "channel_spacing": 0.0,
            "tie_plate_depth": 0.0,
            "tie_plate_thickness": 0.0,
            "tie_plate_length": 0.0,
            "lacing_spacing": 0.0,
            "lacing_angle": 0.0,
            "lacing_force": 0.0,
            "lacing_section_dim": "",
            "weld_length": 0.0,
            "bolt_count": 0
        }

    def customized_input(self, ui_self=None):
        """
        Returns list of tuples for customized input values.
        Format: (key, function)
        """
        return [(KEY_SECSIZE, self.fn_profile_section)]

    def get_section_designation(self):
        """
        Returns the current section designation.
        """
        return self.section_designation

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

    def get_design_status(self):
        """
        Returns the current design status.
        """
        return self.design_status

    def set_design_status(self, status):
        """
        Updates the design status.
        Args:
            status: Boolean indicating design status
        """
        self.design_status = status

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

    def fn_torsion_warping(self):
        print( 'Inside fn_torsion_warping', self)
        if self[0] == Torsion_Restraint1:
            return Warping_Restraint_list
        elif self[0] == Torsion_Restraint2:
            return [Warping_Restraint5]
        else:
            return [Warping_Restraint5]


    def fn_supp_image(self):
        print( 'Inside fn_supp_image', self)
        if self[0] == KEY_DISP_SUPPORT1:
            return Simply_Supported_img
        else:
            return Cantilever_img

    def axis_bending_change(self):
        design = self[0]
        print( 'Inside fn_supp_image', self)
        if self[0] == KEY_DISP_DESIGN_TYPE_FLEXURE:
            return ['NA']
        else:
            return VALUES_BENDING_TYPE

    def process_design(self, design_dict):
        """Main processing method to invoke laced column calculations."""
        try:
            # Validate input dictionary first
            is_valid, message = self.validate_design_dict(design_dict)
            if not is_valid:
                self.design_status = False
                self.result = {"design_safe": False, "message": message}
                return False

            # Create a copy to avoid modifying the original
            design_dict = design_dict.copy()
            
            # Ensure numeric values are properly converted
            design_dict[KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY] = float(design_dict.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0))
            design_dict[KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ] = float(design_dict.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, 0))
            design_dict[KEY_AXIAL_LOAD] = float(design_dict.get(KEY_AXIAL_LOAD, 0))

            # Call the computational model
            design_obj = LacedColumnDesign(design_dict)
            result = design_obj.design()

            # Extract results into current instance
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

            return self.design_status

        except Exception as e:
            self.design_status = False
            self.result = {
                "design_safe": False,
                "message": f"Design failed: {str(e)}",
                "error": str(e)
            }
            self.utilization_ratio = 0
            return False

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

        # Create report summary
        report_summary = {
            "ProfileSummary": {
                "CompanyName": "Osdag",
                "CompanyLogo": "",
                "Group/TeamName": "Osdag Team",
                "Designer": "Osdag Designer"
            },
            "ProjectTitle": "Laced Column Design",
            "Subtitle": "Design Report",
            "JobNumber": "",
            "Client": "",
            "does_design_exist": True
        }

        # Create UI object with results
        ui_obj = {
            "Section and Material Details": {
                "Section Size": self.section_size_1.designation if self.section_size_1 else "",
                "Material Grade": self.material.get('grade', '') if self.material else ""
            },
            "Design Results": {
                "Utilization Ratio": f"{self.utilization_ratio:.2f}",
                "Design Status": "Safe" if self.design_status else "Unsafe",
                "Lacing Angle": f"{self.lacing_incl_angle}°",
                "Required Weld Length": f"{self.result.get('weld_length_required', 'N/A')} mm"
            }
        }

        # Generate report
        report = CreateLatex()
        report.save_latex(ui_obj, self.design_status, report_summary, "laced_column_report", "", "", "", "LacedColumn")

        return "Report generation completed."

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

    def fn_profile_section(self, *args):
        """
        Handle section profile selection for laced column.
        Returns available sections based on selected profile type.
        """
        try:
            if not args:
                return ['All', 'Customized']

            value = args[0]
            print(f"[DEBUG] fn_profile_section called with: {args}")

            # Called from design preference - customized size trigger
            if value == "Customized":
                print("[DEBUG] Showing sections from database")
                self.show_custom_section_dialog()
                return [self.section_designation] if self.section_designation else ['Customized']

            # Called from profile dropdown - fetch sections from DB
            if value == 'Angle':
                sections = connectdb('Angles', call_type="popup")
                return sections if sections else []
            elif value == 'Channel':
                sections = connectdb('Channels', call_type="popup")
                return sections if sections else []
            elif value in ['Customized', '2-channels Back-to-Back', '2-channels Toe-to-Toe', '2-Girders']:
                print("[DEBUG] Showing sections from database")
                self.show_custom_section_dialog()
                return [self.section_designation] if self.section_designation else ['Customized']

            return ['All', 'Customized']

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in fn_profile_section: {str(e)}")
            return []

    def show_custom_section_dialog(self):
        """
        Shows a dialog with available sections from the database.
        Avoids pop-up if ISection table is missing.
        """
        try:
            print("[DEBUG] Showing sections from database")
            dialog = QDialog()
            dialog.setWindowTitle("Available Sections")
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout()
            table = QTableWidget()
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels([
                "Designation", "Depth", "Flange Width", "Flange Thickness",
                "Web Thickness", "Root Radius", "Toe Radius", "Flange Slope"
            ])
            # Get sections using connectdb
            sections = connectdb('Columns', call_type="popup")
            if not sections:
                # Instead of pop-up, just return gracefully
                print("[WARNING] No sections found in database or table missing.")
                return None
            # Check if ISection table exists
            conn = sqlite3.connect(PATH_TO_DATABASE)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ISection';")
            if not c.fetchone():
                print("[WARNING] ISection table does not exist in the database.")
                conn.close()
                return None
            # Populate table
            table.setRowCount(len(sections))
            for i, section in enumerate(sections):
                c.execute('''SELECT Designation, Depth, FlangeWidth, FlangeThickness,
                            WebThickness, RootRadius, ToeRadius, FlangeSlope 
                            FROM ISection WHERE Designation = ?''', (section,))
                details = c.fetchone()
                if details:
                    for j, value in enumerate(details):
                        item = QTableWidgetItem(str(value))
                        table.setItem(i, j, item)
            conn.close()
            layout.addWidget(table)
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            dialog.setLayout(layout)
            if dialog.exec_() == QDialog.Accepted:
                selected_items = table.selectedItems()
                if selected_items:
                    row = selected_items[0].row()
                    self.section_designation = table.item(row, 0).text()
                    return self.section_designation
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in show_custom_section_dialog: {str(e)}")
            # Do not show a pop-up, just log and return
            print(f"[ERROR] Failed to show sections dialog: {str(e)}")
            return None

    def get_section_sizes(self, *args):
        """
        Returns available section sizes based on the selected profile.
        Fetches sections directly from the database tables.
        """
        if not args or not args[0]:
            return connectdb('Columns', call_type="popup")
        profile = args[0]
        if profile in ["I-section", "Columns"]:
            # Get sections from Columns table
            sections = connectdb('Columns', call_type="popup")
            print(f"DEBUG: Available I-sections: {sections}")
            return sections
        elif profile == "Channels":
            return connectdb('Channels', call_type="popup")
        elif profile == "Angles":
            return connectdb('Angles', call_type="popup")
        elif profile == "RHS":
            return connectdb('RHS', call_type="popup")
        elif profile == "SHS":
            return connectdb('SHS', call_type="popup")
        elif profile == "CHS":
            return connectdb('CHS', call_type="popup")
        elif profile == "Custom":
            return ["Custom"]
        else:
            return ["Custom"]

    def get_I_section_sizes(self):
        """
        Returns available I-section sizes from the database.
        """
        return connectdb('Columns', call_type="popup")

    def get_RHS_section_sizes(self):
        """
        Returns available RHS section sizes from the database.
        """
        return connectdb('RHS', call_type="popup")

    def get_SHS_section_sizes(self):
        """
        Returns available SHS section sizes from the database.
        """
        return connectdb('SHS', call_type="popup")

    def get_CHS_section_sizes(self):
        """
        Returns available CHS section sizes from the database.
        """
        return connectdb('CHS', call_type="popup")

    def get_end_conditions(self, *args):
        """
        Returns available end conditions for the laced column.
        """
        return ["Fixed-Fixed", "Fixed-Pinned", "Fixed-Free", "Pinned-Pinned"]

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
                        # Validate all fields are filled
                        if not all([material_data.get('grade'), material_data.get('fy_20'), 
                                  material_data.get('fy_20_40'), material_data.get('fy_40'), 
                                  material_data.get('fu')]):
                            QMessageBox.warning(dialog, "Error", "Please fill all fields")
                            return None
                        
                        try:
                            # Convert values to integers
                            fy_20 = int(material_data.get('fy_20', 0))
                            fy_20_40 = int(material_data.get('fy_20_40', 0))
                            fy_40 = int(material_data.get('fy_40', 0))
                            fu = int(material_data.get('fu', 0))
                            
                            # Calculate elongation based on fy_20
                            elongation = 20 if fy_20 > 350 else (22 if 250 < fy_20 <= 350 else 23)
                            
                            # Add to database
                            conn = sqlite3.connect("Intg_osdag.sqlite")
                            c = conn.cursor()
                            c.execute('''INSERT INTO Material (Grade,[Yield Stress (< 20)],
                            [Yield Stress (20 -40)],[Yield Stress (> 40)],
                            [Ultimate Tensile Stress],[Elongation ]) 
                            VALUES (?,?,?,?,?,?)''',
                            (material_data.get('grade'), fy_20, fy_20_40, fy_40, fu, elongation))
                            conn.commit()
                            conn.close()
                            
                            # Update material properties
                            self.material = material_data.get('grade')
                            return self.material
                            
                        except ValueError:
                            QMessageBox.warning(dialog, "Error", "Please enter valid numeric values")
                        except sqlite3.Error as e:
                            QMessageBox.critical(dialog, "Database Error", f"Failed to add material: {str(e)}")
                            
            return None
        except Exception as e:
            logger = self.set_osdaglogger(None)
            logger.error(f"Error in new_material: {str(e)}")
            return None

    def warning_majorbending(self):
        print(self)
        if self[0] == VALUES_SUPP_TYPE_temp[2]:
            return True
        # elif self[0] == VALUES_SUPP_TYPE_temp[0] or self[0] == VALUES_SUPP_TYPE_temp[1] :
        #     return True
        else:
            return False

    def output_modifier(self):
        print(self)
        if self[0] == VALUES_SUPP_TYPE_temp[2]:
            return False
        # elif self[0] == VALUES_SUPP_TYPE_temp[0] or self[0] == VALUES_SUPP_TYPE_temp[1] :
        #     return True
        else:
            return True

    def Design_pref_modifier(self):
        print("Design_pref_modifier", self)

    def input_values(self, ui_self):
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

        # LTB Parameters
        spacing.append((
            KEY_T_constatnt,
            KEY_DISP_T_constatnt,
            TYPE_TEXTBOX,
            self.result_tc if status else '',
            False
        ))
        spacing.append((
            KEY_W_constatnt,
            KEY_DISP_W_constatnt,
            TYPE_TEXTBOX,
            self.result_wc if status else '',
            False
        ))
        spacing.append((
            KEY_IMPERFECTION_FACTOR_LTB,
            KEY_DISP_IMPERFECTION_FACTOR,
            TYPE_TEXTBOX,
            self.result_IF_lt if status else '',
            False
        ))
        spacing.append((
            KEY_SR_FACTOR_LTB,
            KEY_DISP_SR_FACTOR,
            TYPE_TEXTBOX,
            self.result_srf_lt if status else '',
            False
        ))
        spacing.append((
            KEY_NON_DIM_ESR_LTB,
            KEY_DISP_NON_DIM_ESR,
            TYPE_TEXTBOX,
            self.result_nd_esr_lt if status else '',
            False
        ))
        spacing.append((
            KEY_DESIGN_STRENGTH_COMPRESSION,
            KEY_DISP_COMP_STRESS,
            TYPE_TEXTBOX,
            self.result_fcd__lt if status else '',
            False
        ))
        spacing.append((
            KEY_Elastic_CM,
            KEY_DISP_Elastic_CM,
            TYPE_TEXTBOX,
            self.result_mcr if status else '',
            False
        ))

        return spacing

    def output_values(self, flag):
        """
        Returns list of tuples to be displayed in the UI (Output Dock)
        Format: (key, display_key, type, value, required)
        """
        out_list = []

        # Section and Material Details
        out_list.append((None, "Section and Material Details", TYPE_TITLE, None, True))
        out_list.append((KEY_SECSIZE, "Section Size", TYPE_TEXTBOX, self.section_size_1.designation if (flag and self.section_size_1 is not None) else '', True))
        out_list.append((KEY_MATERIAL, "Material Grade", TYPE_TEXTBOX, self.material.get('grade', '') if self.material else '', True))

        # Effective Lengths
        out_list.append((None, "Effective Lengths", TYPE_TITLE, None, True))
        out_list.append((KEY_EFF_LEN_YY, "Effective Length (YY)", TYPE_TEXTBOX, 
                        round(self.result.get('effective_length_yy', 0), 2) if flag else '', True))
        out_list.append((KEY_EFF_LEN_ZZ, "Effective Length (ZZ)", TYPE_TEXTBOX, 
                        round(self.result.get('effective_length_zz', 0), 2) if flag else '', True))

        # End Conditions
        out_list.append((None, "End Conditions", TYPE_TITLE, None, True))
        out_list.append((KEY_END_COND_YY_1, "End Condition YY-1", TYPE_TEXTBOX, 
                        self.result.get('end_condition_yy_1', '') if flag else '', True))
        out_list.append((KEY_END_COND_YY_2, "End Condition YY-2", TYPE_TEXTBOX, 
                        self.result.get('end_condition_yy_2', '') if flag else '', True))
        out_list.append((KEY_END_COND_ZZ_1, "End Condition ZZ-1", TYPE_TEXTBOX, 
                        self.result.get('end_condition_zz_1', '') if flag else '', True))
        out_list.append((KEY_END_COND_ZZ_2, "End Condition ZZ-2", TYPE_TEXTBOX, 
                        self.result.get('end_condition_zz_2', '') if flag else '', True))

        # Slenderness Ratios
        out_list.append((None, "Slenderness Ratios", TYPE_TITLE, None, True))
        out_list.append((KEY_SLENDER_YY, "Slenderness Ratio (YY)", TYPE_TEXTBOX, 
                        round(self.result.get('slenderness_yy', 0), 2) if flag else '', True))
        out_list.append((KEY_SLENDER_ZZ, "Slenderness Ratio (ZZ)", TYPE_TEXTBOX, 
                        round(self.result.get('slenderness_zz', 0), 2) if flag else '', True))

        # Design Values
        out_list.append((None, "Design Values", TYPE_TITLE, None, True))
        out_list.append((KEY_FCD, "Design Compressive Stress (fcd)", TYPE_TEXTBOX, 
                        round(self.result.get('fcd', 0), 2) if flag else '', True))
        out_list.append((KEY_DESIGN_COMPRESSIVE, "Design Compressive Strength", TYPE_TEXTBOX, 
                        round(self.result.get('design_compressive_strength', 0), 2) if flag else '', True))

        # Channel Spacing
        out_list.append((None, "Channel Spacing", TYPE_TITLE, None, True))
        out_list.append((KEY_CHANNEL_SPACING, "Spacing Between Channels", TYPE_TEXTBOX, 
                        round(self.result.get('channel_spacing', 0), 2) if flag else '', True))

        # Tie Plate Details
        out_list.append((None, "Tie Plate Details", TYPE_TITLE, None, True))
        out_list.append((KEY_TIE_PLATE_D, "Overall Depth (D)", TYPE_TEXTBOX, 
                        round(self.result.get('tie_plate_depth', 0), 2) if flag else '', True))
        out_list.append((KEY_TIE_PLATE_T, "Thickness (t)", TYPE_TEXTBOX, 
                        round(self.result.get('tie_plate_thickness', 0), 2) if flag else '', True))
        out_list.append((KEY_TIE_PLATE_L, "Length (L)", TYPE_TEXTBOX, 
                        round(self.result.get('tie_plate_length', 0), 2) if flag else '', True))

        # Lacing Details
        out_list.append((None, "Lacing Details", TYPE_TITLE, None, True))
        out_list.append((KEY_LACING_SPACING, "Lacing Spacing", TYPE_TEXTBOX, 
                        round(self.result.get('lacing_spacing', 0), 2) if flag else '', True))
        out_list.append((KEY_LACING_ANGLE, "Lacing Angle", TYPE_TEXTBOX, 
                        round(self.result.get('lacing_angle', 0), 2) if flag else '', True))
        out_list.append((KEY_LACING_FORCE, "Force on Lacing", TYPE_TEXTBOX, 
                        round(self.result.get('lacing_force', 0), 2) if flag else '', True))
        out_list.append((KEY_LACING_SECTION_DIM, "Lacing Section Dimensions", TYPE_TEXTBOX, 
                        self.result.get('lacing_section_dim', '') if flag else '', True))

        # Connection Details
        out_list.append((None, "Connection Details", TYPE_TITLE, None, True))
        if self.weld_type == 'Welded':
            out_list.append((KEY_WELD_LENGTH, "Required Weld Length", TYPE_TEXTBOX, 
                           round(self.result.get('weld_length', 0), 2) if flag else '', True))
        else:
            out_list.append((KEY_BOLT_COUNT, "Number of Bolts Required", TYPE_TEXTBOX, 
                           self.result.get('bolt_count', 0) if flag else '', True))

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
        print(f"func_for_validation here")
        all_errors = []
        self.design_status = False
        flag = False
        self.output_values(flag)  # Removed extra self parameter
        flag1 = False
        flag2 = False
        flag3 = False
        option_list = self.input_values(self)  # Removed extra self parameter
        missing_fields_list = []
        print(f'func_for_validation option_list {option_list}'
            f"\n  design_dictionary {design_dictionary}")
        
        for option in option_list:
            if option[2] == TYPE_TEXTBOX or option[0] == KEY_LENGTH or option[0] == KEY_SHEAR or option[0] == KEY_MOMENT:
                try:
                    if design_dictionary[option[0]] == '':
                        missing_fields_list.append(option[1])
                        continue
                    if option[0] == KEY_LENGTH:
                        if float(design_dictionary[option[0]]) <= 0.0:
                            print("Input value(s) cannot be equal or less than zero.")
                            error = "Input value(s) cannot be equal or less than zero."
                            all_errors.append(error)
                        else:
                            flag1 = True
                    elif option[0] == KEY_SHEAR:
                        if float(design_dictionary[option[0]]) <= 0.0:
                            print("Input value(s) cannot be equal or less than zero.")
                            error = "Input value(s) cannot be equal or less than zero."
                            all_errors.append(error)
                        else:
                            flag2 = True
                    elif option[0] == KEY_MOMENT:
                        if float(design_dictionary[option[0]]) <= 0.0:
                            print("Input value(s) cannot be equal or less than zero.")
                            error = "Input value(s) cannot be equal or less than zero."
                            all_errors.append(error)
                        else:
                            flag3 = True
                except Exception as e:
                    error = "Input value(s) are not valid"
                    all_errors.append(error)

        if len(missing_fields_list) > 0:
            error = self.generate_missing_fields_error_string(missing_fields_list)
            all_errors.append(error)
        else:
            flag = True

        if flag and flag1 and flag2 and flag3:
            print(f"\n design_dictionary{design_dictionary}")
            self.set_input_values(design_dictionary)  # Removed extra self parameter
            if self.design_status == False and len(self.failed_design_dict) > 0:
                logger.error("Design Failed, Check Design Report")
                return  # ['Design Failed, Check Design Report'] @TODO
            elif self.design_status:
                pass
            else:
                logger.error("Design Failed. Slender Sections Selected")
                return  # ['Design Failed. Slender Sections Selected']
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
        t = (1 / 50) * (S + 2 * g)
        return De, D, t

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
            if self.design_pref_dialog is not None and self.design_pref_dialog.dialog.isVisible():
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
        """Clear all input values and reset UI state when window is closed"""
        try:
            # Clear all input fields
            if hasattr(self, 'design_inputs'):
                self.design_inputs.clear()
            
            # Clear design preferences
            if hasattr(self, 'design_pref'):
                self.design_pref.clear()
            
            # Reset design preference dictionary to defaults
            self.design_pref_dictionary = {
                KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
                KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
                KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
            }
            
            # Clear output values
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
            self.lacing_incl_angle = 0.0
            self.lacing_section = ''
            self.lacing_type = ''
            self.allowed_utilization = ''
            
            # Reset design status
            self.design_status = False
            
            # Clear output title fields
            if hasattr(self, 'output_title_fields'):
                self.output_title_fields.clear()
            
            # Clean up design preference dialog if it exists
            if self.design_pref_dialog is not None:
                self.design_pref_dialog.close()
                self.design_pref_dialog = None
            
            # Reset logger
            if self.logger:
                self.logger = None
            
            # Accept the close event
            event.accept()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in closeEvent: {str(e)}")
            event.accept()

    def set_input_values(self, design_dictionary):
        """Sets input values with proper validation."""
        if not isinstance(design_dictionary, dict):
            raise ValueError("design_dictionary must be a dictionary")
            
        try:
            # Validate required keys before processing
            required_keys = [
                KEY_DISP_LACEDCOL,
                KEY_LACEDCOL_SEC_PROFILE,
                KEY_LACEDCOL_SEC_SIZE,
                KEY_LACEDCOL_MATERIAL,
                KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY,
                KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ,
                KEY_AXIAL_LOAD
            ]
            
            # Check for missing required keys
            missing_keys = [key for key in required_keys if key not in design_dictionary]
            if missing_keys:
                error_msg = f"Missing required keys: {', '.join(missing_keys)}"
                if self.logger:
                    self.logger.error(error_msg)
                raise ValueError(error_msg)

            # section properties with safe access
            self.module = design_dictionary.get(KEY_DISP_LACEDCOL, "Laced Column")
            self.mainmodule = 'Member'
            self.sec_profile = design_dictionary.get(KEY_LACEDCOL_SEC_PROFILE, "")
            self.sec_list = design_dictionary.get(KEY_LACEDCOL_SEC_SIZE, [])
            self.main_material = design_dictionary.get(KEY_LACEDCOL_MATERIAL, "")
            self.material = design_dictionary.get(KEY_LACEDCOL_MATERIAL, "")

            # section user data with safe conversion
            try:
                self.length_yy = float(design_dictionary.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0))
                self.length_zz = float(design_dictionary.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, 0))
            except (ValueError, TypeError) as e:
                if self.logger:
                    self.logger.error(f"Error converting length values: {str(e)}")
                raise ValueError("Invalid length values in design dictionary")

            # end conditions with safe access
            self.end_1 = design_dictionary.get(KEY_LACEDCOL_END_CONDITION_YY, "Hinged")
            self.end_2 = design_dictionary.get(KEY_LACEDCOL_END_CONDITION_ZZ, "Hinged")

            # factored loads with safe access
            try:
                axial_force = design_dictionary.get(KEY_AXIAL_LOAD, "0")
                self.load = Load(
                    shear_force="",
                    axial_force=axial_force,
                    moment="",
                    unit_kNm=True
                )
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error creating Load object: {str(e)}")
                raise ValueError("Invalid load values in design dictionary")

            # design preferences with safe access and defaults
            try:
                self.effective_area_factor = float(design_dictionary.get(KEY_LACEDCOL_EFFECTIVE_AREA, "1.0"))
                self.allowable_utilization_ratio = float(design_dictionary.get(KEY_DISP_LACEDCOL_ALLOWABLE_UR, "1.0"))
            except (ValueError, TypeError) as e:
                if self.logger:
                    self.logger.error(f"Error converting design preference values: {str(e)}")
                raise ValueError("Invalid design preference values in design dictionary")

            self.optimization_parameter = "Utilization Ratio"
            self.allow_class = design_dictionary.get(KEY_ALLOW_CLASS, "No")
            self.steel_cost_per_kg = 50

            # section classification with safe access
            self.allowed_sections = []
            if self.allow_class == "Yes":
                self.allowed_sections = KEY_SemiCompact

            # safety factors with safe access
            try:
                self.gamma_m0 = IS800_2007.cl_5_4_1_Table_5["gamma_m0"]["yielding"]
                self.gamma_m1 = IS800_2007.cl_5_4_1_Table_5["gamma_m1"]["ultimate_stress"]
            except KeyError as e:
                if self.logger:
                    self.logger.error(f"Error accessing safety factors: {str(e)}")
                raise ValueError("Invalid safety factor configuration")

            # material properties with safe access
            try:
                self.material_property = Material(material_grade=self.material, thickness=0)
                self.fyf = self.material_property.fy
                self.fyw = self.material_property.fy
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error accessing material properties: {str(e)}")
                raise ValueError("Invalid material properties")

            # initialize design status
            self.design_status_list = []
            self.design_status = False

            # process design with safe dictionary
            return self.process_design(design_dictionary)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in set_input_values: {str(e)}")
            raise  # Re-raise the exception for caller to handle

    def input_modifier(self):
        """Classify the sections based on Table 2 of IS 800:2007"""
        print(f"Inside input_modifier")
        local_flag = True
        self.input_modified = []
        self.input_section_list = []
        # self.input_section_classification = {}

        for section in self.sec_list:
            section = section.strip("'")
            self.section_property = self.section_connect_database(self, section)

            self.Zp_req = self.load.moment * self.gamma_m0 / self.material_property.fy
            print('Inside input_modifier not allow_class',self.allow_class,self.load.moment, self.gamma_m0, self.material_property.fy)
            if self.section_property.plast_sec_mod_z >= self.Zp_req:
                self.input_modified.append(section)
                # logger.info(
                #     f"Required self.Zp_req = {round(self.Zp_req * 10**-3,2)} x 10^3 mm^3 and Zp of section {self.section_property.designation} = {round(self.section_property.plast_sec_mod_z* 10**-3,2)} x 10^3 mm^3.Section satisfy Min self.Zp_req value")
            # else:
                # local_flag = False
                # logger.warning(
                #     f"Required self.Zp_req = {round(self.Zp_req* 10**-3,2)} x 10^3 mm^3 and Zp of section {self.section_property.designation} = {round(self.section_property.plast_sec_mod_z* 10**-3,2)} x 10^3 mm^3.Section dosen't satisfy Min self.Zp_req value")
        # logger.info("")
        print("self.input_modified", self.input_modified)
    def section_connect_database(self, section, material_grade):
        """Connect to database and get section properties"""
        try:
            if not section:
                if self.logger:
                    self.logger.error("No section provided")
                return None
                
            if self.logger:
                self.logger.info(f"Connecting to database for section: {section}")
                
            # Create ISection object with material grade
            self.section_property = ISection(designation=section, material_grade=material_grade)
            
            if not self.section_property:
                               if self.logger:
                                   self.logger.error("Failed to create ISection object")
                                   return None
                
            if self.logger:
                self.logger.info("ISection object created successfully")
                
            # Initialize material property if not exists
            if not hasattr(self, 'material_property'):
                self.material_property = Material(material_grade, 41)
                
            if self.logger:
                self.logger.info("Connecting to database for material properties")
                
            # Connect to database to get material properties
            conn = sqlite3.connect("Intg_osdag.sqlite")
            cursor = conn.cursor()
            
            # Get material properties
            cursor.execute("SELECT * FROM Material WHERE Grade = ?", (material_grade,))
            material_data = cursor.fetchone()
            
            if material_data:
                if self.logger:
                    self.logger.info("Material properties found in database")
                    
                self.material_property.fy = material_data[1]  # Yield strength
                self.material_property.fu = material_data[2]  # Ultimate strength
                self.material_property.E = material_data[3]   # Young's modulus
                self.material_property.G = material_data[4]   # Shear modulus
                self.material_property.nu = material_data[5]  # Poisson's ratio
               
                self.material_property.rho = material_data[6]  # Density
                
                # Calculate epsilon
                self.epsilon = math.sqrt(250 / self.material_property.fy)
                
               
                
                if self.logger:
                    self.logger.info(f"Material properties set: fy={self.material_property.fy}, fu={self.material_property.fu}")
            else:
                if self.logger:
                    self.logger.error(f"No material properties found for grade: {material_grade}")
                
            conn.close()
            
            return self.section_property
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in section_connect_database: {str(e)}")
            return None

    def on_material_grade_selected(self, grade):
        """Handle material grade selection."""
        material = self.fetch_material_properties(grade)
        if material:
            self.fy = material.get('Yield Stress (< 20)', '')
            self.fu = material.get('Ultimate Tensile Stress', '')
            # Example: update UI fields
            self.fy_lineedit.setText(str(self.fy))
            self.fu_lineedit.setText(str(self.fu))

    def on_section_profile_selected(self, section_type):
        """Handle section profile selection."""
        designations = self.fetch_section_designations(section_type)
        # Update the section designation dropdown in the UI with these values
        return designations

    def on_section_designation_selected(self, section_type, designation):
        """Handle section designation selection."""
        section = self.fetch_section_properties(section_type, designation)
        if section:
            self.depth = section.get('Depth', '')
            self.flange_width = section.get('FlangeWidth', '')
            # Update other fields as needed
            return section
        return {}

    def initialize_db_connection(self):
        """Initialize database connection if not already connected."""
        if not self.conn:
            self.conn = sqlite3.connect("")
            self.conn.row_factory = sqlite3.Row

    def fetch_material_properties(self, grade):
        """Fetch material properties from database."""
        self.initialize_db_connection()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Material WHERE Grade = ?", (grade,))
        row = cursor.fetchone()
        if row:
            self.material_data = dict(row)
            return self.material_data
        return {}

    def fetch_section_designations(self, section_type):
        """Fetch available section designations for a given section type."""
        self.initialize_db_connection()
        table_map = {
            "I-section": "ISection",
            "Channel": "Channels",
            "Angle": "Angles"
        }
        table = table_map.get(section_type)
        if not table:
            return []
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT Designation FROM {table}")
        return [r[0] for r in cursor.fetchall()]

    def fetch_section_properties(self, section_type, designation):
        """Fetch section properties for a given section type and designation."""
        self.initialize_db_connection()
        table_map = {
            "I-section": "ISection",
            "Channel": "Channels",
            "Angle": "Angles"
        }
        table = table_map.get(section_type)
        if not table:
            return {}
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table} WHERE Designation = ?", (designation,))
        row = cursor.fetchone()
        if row:
            self.section_data = dict(row)
            self.section_designation = designation
            return self.section_data
        return {}

    def on_user_input(self, design_dict):
        # Fetch material and section properties from DB
        material = self.fetch_material_properties(design_dict.get("material"))
        section = self.fetch_section_properties(design_dict.get("sec_profile"), design_dict.get("sec_size"))
        # Merge DB values into design_dict for calculation
        if material:
            design_dict["fy"] = material.get("Yield Stress (< 20)", 0)
            design_dict["fu"] = material.get("Ultimate Tensile Stress", 0)
        if section:
            design_dict["area"] = section.get("Area", 0)
            design_dict["depth"] = section.get("Depth", 0)
            # ...add other needed section properties...
        # Calculate results using lacedcolumndesign formulas
        result = LacedColumnDesign.calculate_all(design_dict)
        self.result = result
        return result

    def input_dictionary_without_design_pref(self):
        """
        Returns list of tuples for default design preference values if the design preference dialog is never opened.
        Format: (Key of input dock, [List of Design Preference Keys], 'Input Dock')
        """
        design_input = []
        # Adjust these keys as per your actual laced column design preferences
        t1 = (KEY_MATERIAL, [KEY_MATERIAL], 'Input Dock')
        t2 = (None, [KEY_DISP_LACEDCOL_ALLOWABLE_UR, KEY_DISP_LACEDCOL_EFFECTIVE_AREA], '')
        design_input.append(t1)
        design_input.append(t2)
        return design_input

    def tab_list(self):
        """
        Returns a list of tuples for the design preferences tabs.
        Each tuple: (Tab Title, Tab Type, function for tab content)
        """
        tabs = [
            ("Section", "TYPE_TAB_1", self.get_section_tab_elements),
            ("Material", "TYPE_TAB_2", self.get_material_tab_elements),
            ("Connection", "TYPE_TAB_3", self.get_connection_tab_elements),
        ]
        return tabs

    def get_section_tab_elements(self, *args):
        # Return a list of tuples for section tab content
        return []

    def get_material_tab_elements(self, *args):
        # Return a list of tuples for material tab content
        return []

    def get_connection_tab_elements(self, *args):
        # Return a list of tuples for connection tab content
        return []

    def tab_value_changed(self):
        change_tab = []
        # Example: Add a tuple for section material changes
        t1 = (KEY_DISP_COLSEC, [KEY_SEC_MATERIAL], [KEY_SEC_FU, KEY_SEC_FY], TYPE_TEXTBOX, self.get_fu_fy_I_section)
        change_tab.append(t1)
        return change_tab
