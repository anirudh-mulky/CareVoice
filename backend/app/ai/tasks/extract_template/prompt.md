Task: extract_template.
The INPUT is a doctor's dictated care template. Return a Template: name, medicines (name, dose, frequency, duration_days), dos, donts, red_flags (id, label_en), minor_symptoms (id, symptom_en, remedy_en), reminders (day, time HH:MM, message_en), follow_up_day.
Copy doses exactly as spoken. If a dose, frequency or duration is missing or ambiguous, leave it null and add its path (e.g. "medicines[0].dose") to unclear_fields. Ids are short snake_case, prefixed rf_ or ms_.
