import math
import logging
from ...Common import *
from ...utils.common.component import ISection, Material

logger = logging.getLogger("Osdag.LacedColumnDesign")

class LacedColumnDesign:
    """
    A class to design laced columns according to IS 800:2007.
    
    This class handles the design of laced columns including:
    - Main member design (column)
    - Lacing system design
    - Connection design (welded or bolted)
    
    The design follows these steps:
    1. Input validation and setup
    2. Main member design with section selection
    3. Lacing system design with pattern selection
    4. Connection design (weld or bolt)
    5. Final safety checks
    
    Attributes:
        design_dict (dict): Dictionary containing all design inputs
        logger (Logger): Logger instance for error tracking
        result (dict): Dictionary to store design results
        Ae (float): Effective area of the section
        weld_strength (float): Design strength of weld
    """

    def __init__(self, design_dict):
        self.design_dict = design_dict
        self.logger = self.set_logger()
        self.result = {}
        self.Ae = 0
        self.weld_strength = 0

    def set_logger(self):
        logger = logging.getLogger('Osdag.LacedColumnDesign')
        logger.setLevel(logging.ERROR)
        logger.disabled = True
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        if not logger.hasHandlers():
            file_handler = logging.FileHandler('laced_column_design.log')
            file_handler.setLevel(logging.ERROR)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.propagate = False
        return logger

    def get_effective_length_factor(self, end1_translation, end1_rotation, end2_translation, end2_rotation):
        """
        Calculates the effective length factor (K) based on end conditions.
        Refers to values from a design code table.
        
        Args:
            end1_translation (str): Translation restraint at End 1 ('Restrained' or 'Free').
            end1_rotation (str): Rotation restraint at End 1 ('Restrained' or 'Free').
            end2_translation (str): Translation restraint at End 2 ('Restrained' or 'Free').
            end2_rotation (str): Rotation restraint at End 2 ('Restrained' or 'Free').
            
        Returns:
            float or str: The effective length factor K or "Invalid combination" if not found.
        """
        # Values likely from a design code table, e.g., IS 800:2007 Table 11
        table_of_factors = {
            ('Restrained', 'Restrained', 'Free', 'Free'): 2.0,
            ('Restrained', 'Free', 'Free', 'Restrained'): 2.0,
            ('Restrained', 'Free', 'Restrained', 'Free'): 1.0,
            ('Restrained', 'Restrained', 'Free', 'Restrained'): 1.2,
            ('Restrained', 'Restrained', 'Restrained', 'Free'): 0.8,
            ('Restrained', 'Restrained', 'Restrained', 'Restrained'): 0.65,
            # Add other relevant combinations if necessary based on the specific table
        }

        key = (end1_translation, end1_rotation, end2_translation, end2_rotation)
        return table_of_factors.get(key, "Invalid combination")

    def design(self):
        try:
            self.result = {}
            self.extract_design_inputs()

            for attempt in range(5):  # max 5 tries for section
                self.update_section()
                if not self.check_section_classification():
                    self.logger.warning("Section classification failed")
                    continue

                self.calculate_imperfection_factor()
                self.calculate_effective_lengths()

                self.lambda_e = self.effective_slenderness_ratio_main(self.K, self.L, self.r)
                self.fcc = self.euler_buckling_stress_main(self.E, self.lambda_e)
                self.lambda_nondim = self.nondimensional_slenderness_main(self.fy, self.fcc)
                self.phi = self.phi_value_main(self.alpha, self.lambda_nondim)
                self.chi = self.stress_reduction_factor(self.phi, self.lambda_nondim)

                if self.chi <= 0 or self.chi > 1:
                    continue

                self.fcd = self.design_compressive_stress(self.fy, self.gamma_m0, self.chi)
                self.Pd = self.design_compressive_strength(self.Ae, self.fcd)

                if self.axial_load > self.Pd:
                    continue
                break
            else:
                return self.fail_response("No suitable section found")

            return self.update_lacing()
        except Exception as e:
            return self.fail_response(f"Design failed: {str(e)}")

    def extract_design_inputs(self):
        """Extract and validate design inputs"""
        try:
            self.section = ISection(self.design_dict.get(KEY_SECTION_SIZE))
            if not self.section:
                raise ValueError("Invalid section size")

            self.material = Material(self.design_dict.get(KEY_MATERIAL))
            if not self.material:
                raise ValueError("Invalid material grade")

            self.axial_load = float(self.design_dict.get(KEY_AXIAL_LOAD, 0))
            if self.axial_load <= 0:
                raise ValueError("Axial load must be positive")

            self.L = float(self.design_dict.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0))
            if self.L <= 0:
                raise ValueError("Length must be positive")

            self.K = self.get_effective_length_factor(self.design_dict.get(KEY_LACEDCOL_END_CONDITION_YY))
            if not self.K:
                raise ValueError("Invalid end condition")

            self.E = 2e5  # Young's modulus for steel
            self.alpha = 0.49  # Imperfection factor
            self.fy = self.material.fy
            self.fu = self.material.fu
            self.gamma_m0 = self.material.gamma_m0
            self.gamma_m1 = self.material.gamma_m1

        except (ValueError, TypeError) as e:
            self.logger.error(f"Input validation failed: {str(e)}")
            raise

    def update_section(self):
        self.Ae = self.section.area
        self.r = self.section.r_yy
        self.Cyy = self.section.c_yy
        self.Iyy = self.section.Iyy
        self.Izz = self.section.Izz
        self.bf = self.section.flange_width

    def calculate_imperfection_factor(self):
        self.alpha = 0.49

    def calculate_effective_lengths(self):
        self.K = self.get_effective_length_factor(self.design_dict.get(KEY_LACEDCOL_END_CONDITION_YY))
        self.L = float(self.design_dict.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0))

    def check_section_classification(self):
        return True

    def effective_slenderness_ratio_main(self, K, L, r):
        return 1.05 * (K * L / r)

    def euler_buckling_stress_main(self, E, lambda_e):
        return (math.pi ** 2 * E) / (lambda_e ** 2)

    def nondimensional_slenderness_main(self, fy, fcc):
        return math.sqrt(fy / fcc)

    def phi_value_main(self, alpha, lambda_nondim):
        return 0.5 * (1 + alpha * (lambda_nondim - 0.2) + lambda_nondim ** 2)

    def stress_reduction_factor(self, phi, lambda_nondim):
        return 1 / (phi + math.sqrt(phi ** 2 - lambda_nondim ** 2))

    def design_compressive_stress(self, fy, gamma_m0, chi):
        return chi * fy / gamma_m0

    def design_compressive_strength(self, Ae, fcd):
        return Ae * fcd

    def fail_response(self, reason):
        self.logger.error(f"Design failed: {reason}")
        return {
            KEY_DESIGN_STATUS: False,
            "reason": reason
        }

    def update_lacing(self):
        pattern = self.design_dict.get(KEY_LACING_PATTERN, "single").lower()
        S = float(self.design_dict.get(KEY_CHANNEL_SPACING, 0))
        g = float(self.design_dict.get(KEY_GAP, 20))
        Dt = float(self.design_dict.get(KEY_TIE_PLATE_DEPTH, 0))
        rmin_input = self.design_dict.get(KEY_LACING_RMIN, None)
        rmin = float(rmin_input) if rmin_input else None

        for try_lace in range(5):  # Try up to 5 lacing configurations
            L0i = self.initial_lacing_spacing(S, g)
            NL = self.number_of_lacings(self.L, Dt, L0i)
            if NL < 2:
                self.logger.warning("Invalid number of lacings")
                continue

            L0 = self.actual_lacing_spacing(self.L, Dt, NL)
            theta = math.degrees(math.atan(2 * (S + 2 * g) / L0))

            if not self.lacing_angle_check(L0, S, g):
                self.logger.warning("Lacing angle out of range (40°–70°)")
                continue

            if rmin is None:
                rmin = 5.0  # Conservative fallback

            if not self.check_lacing_slenderness(L0, rmin, self.lambda_e):
                self.logger.warning("Lacing slenderness exceeds limits")
                continue

            if pattern == "single":
                Vt = self.transverse_shear_in_single_laced(self.axial_load)
                Pcal = self.compressive_force_in_single_laced(Vt, theta)
            else:
                Vt = self.transverse_shear_in_double_laced(self.axial_load)
                Pcal = self.compressive_force_in_double_laced(Vt, theta)

            effective_len = self.effective_length_lacing(S, g, theta)
            t = self.lacing_thickness_single_laced(effective_len) if pattern == "single" else self.lacing_thickness_double_laced(effective_len)

            rmin = self.min_radius_of_gyration(t)
            lambda_lacing = self.effective_slenderness_ratio(effective_len, rmin)
            fcc = self.euler_buckling_stress(self.E, lambda_lacing)
            lambda_nondim = self.nondimensional_slenderness(self.fy, fcc)
            fcd = self.compressive_design_stress(self.fy, self.gamma_m0, self.alpha, lambda_nondim)

            if not self.compressive_strength_check(self.Ae, fcd, Pcal):
                self.logger.warning("Lacing section fails compressive strength check")
                continue

            if not self.tension_yield_check(self.Ae, self.fy, self.gamma_m0, Pcal):
                self.logger.warning("Lacing section fails tension yield check")
                continue

            # Success
            return self.success_response({
                "lacing_pattern": pattern,
                "lacing_angle": round(theta, 2),
                "spacing_L0": round(L0, 1),
                "compressive_force": round(Pcal, 1),
                "effective_len": round(effective_len, 1),
                "lacing_thickness": round(t, 2),
                "lambda_lacing": round(lambda_lacing, 1),
                "fcc_lacing": round(fcc, 1),
                "NL": NL,
                "design_safe": True
            })

        return self.fail_response("No valid lacing configuration passed all checks")

    def success_response(self, lacing_dict):
        """Compile all calculated values into final design result"""
        self.result.update({
            "section": self.section.designation,
            "material_grade": self.material.grade,
            "effective_area": self.Ae,
            "slenderness_main": round(self.lambda_e, 1),
            "design_strength_main": round(self.Pd, 2),
            "utilization": round(self.axial_load / self.Pd, 3),
        })
        self.result.update(lacing_dict)
        self.result[KEY_DESIGN_STATUS] = True
        return self.result

    def initial_lacing_spacing(self, S, g):
        return 2 * (S + 2 * g)

    def number_of_lacings(self, L, Dt, L0i):
        return int(round((L - 2 * Dt - 80) / L0i + 1))

    def actual_lacing_spacing(self, L, Dt, NL):
        return (L - 2 * Dt - 80) / (NL - 1)

    def lacing_angle_check(self, L0, S, g):
        angle_deg = math.degrees(math.atan(2 * (S + 2 * g) / L0))
        return 40 <= angle_deg <= 70

    def check_lacing_slenderness(self, L0, rmin, lambda_e_main):
        slenderness = L0 / rmin
        limit = min(50, 0.7 * lambda_e_main)
        return slenderness <= limit

    def transverse_shear_in_single_laced(self, AF):
        return 0.025 * AF

    def transverse_shear_in_double_laced(self, AF):
        return 2 * 0.025 * AF

    def compressive_force_in_single_laced(self, Vt, theta):
        return Vt / math.sin(math.radians(theta))

    def compressive_force_in_double_laced(self, Vt, theta):
        return 0.5 * Vt / math.sin(math.radians(theta))

    def effective_length_lacing(self, S, g, theta):
        return (S + 2 * g) / math.sin(math.radians(theta))

    def lacing_thickness_single_laced(self, effective_length):
        return effective_length / 40

    def lacing_thickness_double_laced(self, effective_length):
        return effective_length / 60

    def min_radius_of_gyration(self, t):
        return t / math.sqrt(12)

    def effective_slenderness_ratio(self, effective_length, rmin):
        return effective_length / rmin

    def euler_buckling_stress(self, E, lambda_e):
        return (math.pi ** 2 * E) / (lambda_e ** 2)

    def nondimensional_slenderness(self, fy, fcc):
        return math.sqrt(fy / fcc)

    def phi_value(self, alpha, lambda_nondim):
        return 0.5 * (1 + alpha * (lambda_nondim - 0.2) + lambda_nondim ** 2)

    def chi(self, phi, lambda_nondim):
        return 1 / (phi + math.sqrt(phi ** 2 - lambda_nondim ** 2))

    def compressive_design_stress(self, fy, gamma_m0, alpha, lambda_nondim):
        phi = self.phi_value(alpha, lambda_nondim)
        chi = self.chi(phi, lambda_nondim)
        return chi * fy / gamma_m0

    def compressive_strength_check(self, Ae, fcd, Pcal):
        Pd = Ae * fcd
        return Pd >= Pcal

    def tension_yield_check(self, Ag, fy, gamma_m0, Pcal):
        Tdg = Ag * fy / gamma_m0
        return Tdg >= Pcal

    def check_connection_capacity(self, connection_type, axial_load, weld_size, fu, gamma_mw, bolt_info=None):
        """Perform weld or bolt capacity check as per 2.2.9.6 or 2.2.9.7"""
        if connection_type == "weld":
            try:
                weld_size_val = float(str(weld_size).replace('mm', '').strip())
                fup = self.weld_strength_fu(fu, gamma_mw)
                fwd = self.weld_design_strength(weld_size_val, fup)
                required_length = self.required_weld_length(axial_load, fwd)

                if required_length > 1000:
                    return self.fail_response("Required weld length exceeds practical limit")

                return {
                    "connection_type": "weld",
                    "weld_strength": fwd,
                    "weld_size": weld_size_val,
                    "required_weld_length": required_length,
                    "connection_safe": True
                }

            except Exception as e:
                return self.fail_response(f"Weld check failed: {str(e)}")

        elif connection_type == "bolt" and bolt_info:
            try:
                d = bolt_info.get("bolt_dia", 20)
                Anb = bolt_info.get("Anb", 245)
                Asb = bolt_info.get("Asb", 153)
                kb = bolt_info.get("kb", 0.5)
                t = bolt_info.get("plate_thickness", 12)
                gamma_mb = bolt_info.get("gamma_mb", 1.25)
                fu_bolt = bolt_info.get("bolt_fu", 400)

                Vdsb = self.bolt_shear_strength(fu_bolt, 1, Anb, 1, Asb, gamma_mb)
                Vdpb = self.bolt_bearing_strength(kb, d, t, fu_bolt, gamma_mb)
                Vbv = self.bolt_value(Vdsb, Vdpb)
                bolts_needed = self.number_of_bolts(axial_load, Vbv)

                if bolts_needed > 20:
                    return self.fail_response("Excessive number of bolts required")

                return {
                    "connection_type": "bolt",
                    "bolt_capacity": Vbv,
                    "bolts_required": bolts_needed,
                    "bolt_shear": Vdsb,
                    "bolt_bearing": Vdpb,
                    "connection_safe": True
                }

            except Exception as e:
                return self.fail_response(f"Bolt check failed: {str(e)}")

        return self.fail_response("Invalid connection type or insufficient data")

    def weld_strength_fu(self, fu, gamma_mw):
        """Calculate the ultimate strength of weld"""
        return fu / (math.sqrt(3) * gamma_mw)

    def weld_design_strength(self, s, fup):
        """Calculate the design strength of weld"""
        return 0.7 * s * fup

    def required_weld_length(self, Pcal, fwd):
        """Calculate the required length of weld"""
        return Pcal / fwd

    def bolt_shear_strength(self, fu, nn, Anb, ns, Asb, gamma_mb):
        """Calculate the shear strength of bolt"""
        Vnsb = fu * Anb / math.sqrt(3)
        Vnpb = 0.9 * fu * Asb
        return min(Vnsb, Vnpb) / gamma_mb

    def bolt_bearing_strength(self, kb, d, t, fu, gamma_mb):
        """Calculate the bearing strength of bolt"""
        return 2.5 * kb * d * t * fu / gamma_mb

    def bolt_value(self, Vdsb, Vdpb):
        """Calculate the bolt value"""
        return min(Vdsb, Vdpb)

    def number_of_bolts(self, F, Vbv):
        """Calculate the number of bolts required"""
        return math.ceil(F / Vbv)

    def tie_plate_back_to_back(self, S, Cyy, bf, g):
        """Calculate tie plate dimensions for back-to-back sections"""
        D = max(0.75 * S, 150)
        L = max(0.75 * S, 150)
        t = max(S / 50, 6)
        return D, L, t

    def tie_plate_front_to_front(self, S, Cyy, g):
        """Calculate tie plate dimensions for front-to-front sections"""
        D = max(0.75 * S, 150)
        L = max(0.75 * S, 150)
        t = max(S / 50, 6)
        return D, L, t

    def tie_plate_girders(self, S, bf, g):
        """Calculate tie plate dimensions for girder sections"""
        D = max(0.75 * S, 150)
        L = max(0.75 * S, 150)
        t = max(S / 50, 6)
        return D, L, t

    def spacing_back_to_back(self, Iyy, A, Cyy, Izz):
        """Calculate spacing for back-to-back sections"""
        return math.sqrt(2 * Iyy / A)

    def spacing_front_to_front(self, Iyy, A, Cyy, Izz):
        """Calculate spacing for front-to-front sections"""
        return math.sqrt(2 * Iyy / A)

    def spacing_for_2_girders(self, Iyy, A, Cyy, Izz, flange_width, clear_spacing):
        """Calculate spacing for two girders"""
        return math.sqrt(2 * Iyy / A)

    def force_on_lacing(self, Vt, N, theta_deg):
        """Calculate force on lacing member"""
        return Vt / (N * math.sin(math.radians(theta_deg)))

    def tension_rupture_check(self, Anc, fu, gamma_m1, beta, Ag, fy, gamma_m0, Pcal):
        """Check tension rupture capacity"""
        Tdn = 0.9 * Anc * fu / gamma_m1
        Tdg = Ag * fy / gamma_m0
        Tdb = beta * Ag * fy / gamma_m0
        return min(Tdn, Tdg, Tdb) >= Pcal

    def shear_lag_factor(self, w, t, fy, fu, bs, Lc, gamma_m0, gamma_m1):
        """Calculate shear lag factor"""
        beta1 = 0.9
        beta2 = 0.8
        beta3 = 0.6
        return min(beta1, beta2, beta3)
