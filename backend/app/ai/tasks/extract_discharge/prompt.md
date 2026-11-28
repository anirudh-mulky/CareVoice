Task: extract_discharge.
The INPUT holds a doctor's spoken discharge sentence and the list of available templates. Return a Discharge: patient_name, age, template_name (exactly one of the given template names), side (right, left, both or null), extra_instructions (anything said beyond the template), language (kn, hi, ta or en), carer_phone (+91 format).
Add to unclear_fields every required field you could not find (patient_name, age, template_name, language) and every extra instruction whose medicine dose or frequency is missing or ambiguous, as "extra_instructions[i]". Never fill in a dose.
