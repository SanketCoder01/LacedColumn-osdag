def input_values(self, ui_self=None):
    """
    Returns list of tuples for input values.
    Format: (key, display key, type, values, required, validator"""
    options_list = []
    
    # Module title and name
    options_list.append((KEY_DISP_LACEDCOL, "Laced Column", TYPE_MODULE, [], True, 'No Validator'))

    # Section
    options_list.append(("title_Section ", "Section Details", TYPE_TITLE, None, True, 'No Validator'))
    options_list.append((KEY_SEC_PROFILE, KEY_DISP_SEC_PROFILE, TYPE_COMBOBOX, ['Angle', 'Channel'], True, 'No Validator'))
    options_list.append((KEY_SECSIZE, KEY_DISP_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, ['All', 'Customized'], True, 'No Validator'))

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