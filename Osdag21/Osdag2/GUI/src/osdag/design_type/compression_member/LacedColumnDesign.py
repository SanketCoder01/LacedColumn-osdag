import math
import logging
from ...Common import *
from ...utils.common.component import ISection, Material

logger = logging.getLogger("Osdag.LacedColumnDesign")

class LacedColumnDesign:
    def __init__(self, design_dict):
        self.design_dict = design_dict
        self.logger = self.set_logger()
        self.result = {}
        self.Ae = 0
        self.weld_strength = 0

    def set_logger(self):
        logger = logging.getLogger('Osdag.LacedColumnDesign')
        logger.setLevel(logging.DEBUG)
        if not logger.hasHandlers():
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
            file_handler = logging.FileHandler('laced_column_design.log')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        return logger

    def design(self):
        try:
            self.logger.info("Starting Laced Column Design Calculations")

            # Step 2.2.1: Input extraction
            section = self.design_dict.get(KEY_SECTION_SIZE)
            material_grade = self.design_dict.get(KEY_MATERIAL)
            axial_load = float(self.design_dict.get(KEY_AXIAL_LOAD, 0))
            unsupported_length_yy = float(self.design_dict.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_YY, 0))
            unsupported_length_zz = float(self.design_dict.get(KEY_LACEDCOL_UNSUPPORTED_LENGTH_ZZ, 0))
            end_condition_yy = self.design_dict.get(KEY_LACEDCOL_END_CONDITION_YY)
            end_condition_zz = self.design_dict.get(KEY_LACEDCOL_END_CONDITION_ZZ)
            lacing_pattern = self.design_dict.get(KEY_LACING_PATTERN)
            lacing_profile = self.design_dict.get(KEY_LACING_PROFILE)
            if not lacing_profile:
                return self.fail_response("Lacing profile not provided")
            self.logger.info(f"Lacing profile selected: {lacing_profile}")
            weld_size = self.design_dict.get(KEY_WELD_SIZE, "5mm")

            # Step 2.2.2: Section setup & validation
            section_obj = ISection(section)
            self.Ae = section_obj.area
            if self.Ae == 0:
                self.logger.warning("Section area is zero. Returning to section iteration.")
                return self.fail_response("Invalid Section Area")

            # Step 2.2.3: Material property setup
            material = Material(material_grade)
            fy = material.fy
            fu = material.fu
            gamma_m0 = material.gamma_m0
            gamma_m1 = material.gamma_m1

            # Step 2.2.4: Effective Length Calculations
            k_yy = self.get_effective_length_factor(end_condition_yy)
            k_zz = self.get_effective_length_factor(end_condition_zz)
            le_yy = k_yy * unsupported_length_yy
            le_zz = k_zz * unsupported_length_zz

            # Step 2.2.5: Slenderness Calculations
            r_yy = section_obj.r_yy
            r_zz = section_obj.r_zz
            lambda_yy = le_yy / r_yy if r_yy != 0 else float('inf')
            lambda_zz = le_zz / r_zz if r_zz != 0 else float('inf')
            lambda_max = max(lambda_yy, lambda_zz)

            # Step 2.2.6: Early Slenderness Failure Check
            if lambda_max > 180:
                return self.fail_response("Slenderness ratio exceeds limit")

            # Step 2.2.7: Design Compressive Strength
            epsilon = math.sqrt(250 / fy)
            lambda_e = lambda_max * epsilon
            fcd = self.calculate_fcd(lambda_e, fy, gamma_m0)
            pd = fcd * self.Ae
            if pd == 0:
                return self.fail_response("Design strength Pd is zero")

            # Step 2.2.8: Utilization Check
            utilization = axial_load / pd
            design_safe = utilization <= 1.0

            # Step 2.2.9.1 to 2.2.9.4: Lacing Details
            lacing_angle = self.calculate_lacing_angle(unsupported_length_yy, section_obj)
            if not (40 <= lacing_angle <= 70):
                return self.fail_response("Lacing angle out of permissible range")
            lacing_spacing = self.calculate_lacing_spacing(unsupported_length_yy, lacing_pattern)
            if lacing_spacing <= 0:
                return self.fail_response("Invalid lacing spacing computed")

            lacing_force = self.calculate_lacing_force(axial_load, lacing_angle)
            weld_length = self.calculate_weld_length(lacing_force, weld_size, fu, gamma_mw=1.25)
            if weld_length <= 0:
                return self.fail_response("Invalid weld length computed")

            tie_plate = self.calculate_tie_plate(section_obj, lacing_spacing)
            if not all(tie_plate.values()):
                return self.fail_response("Invalid tie plate geometry")

            # Step 2.2.9.2 to 2.40: Checks
            if weld_length > 1000:
                return self.fail_response("Weld length unreasonably high")
            if tie_plate["thickness"] > 50 or tie_plate["depth"] > 2000:
                return self.fail_response("Unrealistic tie plate dimensions")
            if lacing_force > 0.05 * axial_load:
                return self.fail_response("Lacing force exceeds 5% limit")

            self.result = {
                'section': section,
                'material_grade': material_grade,
                'effective_area': self.Ae,
                'effective_area_factor': self.Ae / section_obj.area,
                'slenderness': lambda_max,
                'design_strength': pd,
                'lacing_angle_deg': lacing_angle,
                'L0': lacing_spacing,
                'Fcl': lacing_force,
                'weld_length_required': weld_length,
                'tie_plate_D': tie_plate['depth'],
                'tie_plate_L': tie_plate['length'],
                'tie_plate_t': tie_plate['thickness'],
                'utilization': utilization,
                'design_safe': design_safe,
                'lacing_profile': lacing_profile
            }

            self.logger.info("Laced Column Design Calculations Completed Successfully")
            return self.result

        except Exception as e:
            self.logger.error(f"Error in design calculations: {str(e)}")
            return self.fail_response(f"Design calculation failed: {str(e)}")

    def get_effective_length_factor(self, end_condition):
        """Get effective length factor based on end condition (IS 800:2007 Table 11)"""
        factors = {
            "Fixed-Fixed": 0.65,
            "Fixed-Hinged": 0.80,
            "Hinged-Fixed": 0.80,
            "Fixed-Free": 2.10,
            "Hinged-Hinged": 1.00
        }
        return factors.get(end_condition, 1.00)

    def calculate_fcd(self, lambda_e, fy, gamma_m0):
        """Calculate design compressive stress using IS 800 buckling formula"""
        if lambda_e <= 0.2:
            return fy / gamma_m0
        else:
            phi = 0.5 * (1 + 0.49 * (lambda_e - 0.2) + lambda_e ** 2)
            return (fy / gamma_m0) / (phi + math.sqrt(phi ** 2 - lambda_e ** 2))

    def calculate_lacing_angle(self, length, section):
        """Calculate lacing angle in degrees and constrain it between 40° and 70°"""
        angle = math.degrees(math.atan(2 * section.depth / length))
        return max(40, min(70, angle))

    def calculate_lacing_spacing(self, length, pattern):
        """Determine lacing spacing based on pattern type"""
        if pattern.lower() == "single":
            return length / 3
        elif pattern.lower() == "double":
            return length / 4
        return 0

    def calculate_lacing_force(self, axial_load, lacing_angle):
        """Calculate force in lacing member using 2.5% rule and trigonometry"""
        return 0.025 * axial_load / math.sin(math.radians(lacing_angle))

    def calculate_weld_length(self, force, weld_size, fu, gamma_mw):
        """Compute required weld length for given force"""
        weld_size_mm = float(weld_size.replace('mm', '').strip())
        fwd = fu / (math.sqrt(3) * gamma_mw)
        return force * 1000 / (0.7 * weld_size_mm * fwd)

    def calculate_tie_plate(self, section, spacing):
        """Estimate tie plate dimensions based on spacing and flange width"""
        depth = max(2 * section.flange_width, spacing + 2 * section.flange_width)
        length = spacing + 2 * 20  # add 20 mm margin on each side
        thickness = max(5, (spacing + 40) / 50)
        return {'depth': depth, 'length': length, 'thickness': thickness}

    def fail_response(self, reason):
        """Standardize error handling with logging and response object"""
        self.logger.error(f"Design failed: {reason}")
        return {
            KEY_DESIGN_STATUS: False,
            "reason": reason
        }
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
        """Calculate non-dimensional slenderness ratio"""
        return math.sqrt(fy / fcc)

    def euler_buckling_stress_main(self, E, lambda_e):
        """Calculate Euler buckling stress"""
        return (math.pi ** 2 * E) / (lambda_e ** 2)

    def stress_reduction_factor(self, phi, lambda_nondim):
        """Calculate stress reduction factor chi"""
        return 1 / (phi + math.sqrt(phi**2 - lambda_nondim**2))

    def design_strength_check(self, P, Pd):
        """Check if design strength is adequate"""
        return P <= Pd

    def design_compressive_strength(self, Ae, fcd):
        """Calculate total design compressive strength"""
        return Ae * fcd

    def spacing_back_to_back(self, Iyy, A, Cyy, Izz):
        """Spacing for back-to-back channels"""
        S = math.sqrt(((Izz / 2) - Iyy) / A) - Cyy
        return 2 * S

    def spacing_front_to_front(self, Iyy, A, Cyy, Izz):
        """Spacing for front-to-front channels"""
        S = math.sqrt(((Izz / 2) - Iyy) / A) + Cyy
        return 2 * S

    def spacing_for_2_girders(self, Iyy, A, Cyy, Izz, flange_width, clear_spacing):
        """Spacing for two girders configuration"""
        front_spacing = self.spacing_front_to_front(Iyy, A, Cyy, Izz)
        return max(front_spacing, flange_width + clear_spacing)

    def tie_plate_back_to_back(self, S, Cyy, bf, g):
        """Tie plate dimensions for back-to-back channels"""
        De = S + 2 * Cyy
        De = max(De, 2 * bf)
        D = De + 2 * g
        L = S + 2 * g
        t = (1 / 50) * (S + 2 * g)
        return De, D, L, t

    def tie_plate_front_to_front(self, S, Cyy, g):
        """Tie plate dimensions for front-to-front channels"""
        De = S - 2 * Cyy
        D = De + 2 * g
        L = S + 2 * g
        t = (1 / 50) * (S + 2 * g)
        return De, D, L, t

    def tie_plate_girders(self, S, bf, g):
        """Tie plate dimensions for girder arrangement"""
        De = S
        De = max(De, 2 * bf)
        D = De + 2 * g
        L = S + 2 * g
        t = (1 / 50) * (S + 2 * g)
        return De, D, L, t

    def initial_lacing_spacing(self, S, g):
        """Initial guess for lacing spacing"""
        return 2 * (S + 2 * g)

    def number_of_lacings(self, L, Dt, L0i):
        """Calculate number of lacings"""
        return int(round((L - 2 * Dt - 80) / L0i + 1))

    def actual_lacing_spacing(self, L, Dt, NL):
        """Actual lacing spacing for given number of lacings"""
        return (L - 2 * Dt - 80) / (NL - 1)

    def lacing_angle_check(self, L0, S, g):
        """Check if lacing angle is within limits (40° to 70°)"""
        angle_deg = math.degrees(math.atan(2 * (S + 2 * g) / L0))
        return 40 <= angle_deg <= 70

    def check_lacing_slenderness(self, L0, rmin, lambda_e):
        """Check if lacing slenderness satisfies limit"""
        slenderness = L0 / rmin
        limit = min(50, 0.7 * lambda_e)
        return slenderness <= limit

    def transverse_shear_in_single_laced(self, AF):
        return 0.025 * AF

    def compressive_force_in_single_laced(self, Vt, theta):
        return Vt / math.sin(math.radians(theta))

    def transverse_shear_in_double_laced(self, AF):
        return 2 * 0.025 * AF

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

    def compressive_design_stress(self, fy, gamma_m0, alpha, lambda_nondim):
        phi = self.phi_value(alpha, lambda_nondim)
        chi = self.chi(phi, lambda_nondim)
        return chi * fy / gamma_m0

    def phi_value(self, alpha, lambda_nondim):
        return 0.5 * (1 + alpha * (lambda_nondim - 0.2) + lambda_nondim ** 2)

    def nondimensional_slenderness(self, fy, fcc):
        return math.sqrt(fy / fcc)

    def euler_buckling_stress(self, E, lambda_e):
        return (math.pi ** 2 * E) / (lambda_e ** 2)

    def chi(self, phi, lambda_nondim):
        return 1 / (phi + math.sqrt(phi ** 2 - lambda_nondim ** 2))

    def compressive_strength_check(self, Ae, fcd, Pcal):
        Pd = Ae * fcd
        return Pd >= Pcal

    def tension_yield_check(self, Ag, fy, gamma_m0, Pcal):
        Tdg = Ag * fy / gamma_m0
        return Tdg >= Pcal

    def tension_rupture_check(self, Anc, fu, gamma_m1, beta, Ag, fy, gamma_m0, Pcal):
        Tdn = (0.9 * Anc * fu / gamma_m1) + (beta * Ag * fy / gamma_m0)
        return Tdn >= Pcal

    def shear_lag_factor(self, w, t, fy, fu, bs, Lc, gamma_m0, gamma_m1):
        beta = 1.4 - 0.076 * (w / t) * (fy / fu) * (bs / Lc)
        beta_max = 0.9 * (fu * gamma_m0) / (fy * gamma_m1)
        beta = min(beta, beta_max)
        beta = max(beta, 0.7)
        return beta

    def bolt_shear_strength(self, fu, nn, Anb, ns, Asb, gamma_mb):
        Vnsb = (fu / math.sqrt(3)) * (nn * Anb + ns * Asb)
        Vdsb = Vnsb / gamma_mb
        return Vdsb

    def bolt_bearing_strength(self, kb, d, t, fu, gamma_mb):
        Vnpb = 2.5 * kb * d * t * fu
        Vdpb = Vnpb / gamma_mb
        return Vdpb

    def bolt_value(self, Vdsb, Vdpb):
        return min(Vdsb, Vdpb)

    def force_on_lacing(self, Vt, N, theta_deg):
        theta_rad = math.radians(theta_deg)
        return 2 * (Vt / N) * (1 / math.tan(theta_rad))

    def number_of_bolts(self, F, Vbv):
        return math.ceil(F / Vbv)

    def weld_strength_fu(self, fu, gamma_mw):
        return fu / (math.sqrt(3) * gamma_mw)

    def weld_design_strength(self, s, fup):
        return 0.7 * s * fup

    def required_weld_length(self, Pcal, fwd):
        return Pcal / fwd
