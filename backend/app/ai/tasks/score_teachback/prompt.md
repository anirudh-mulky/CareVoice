Task: score_teachback.
The INPUT holds the patient's spoken answer (native language and English) to "When should you come back to the hospital?" and the template's red flags. Return mentioned_flag_ids (flags the patient described in any words or language), missed_flag_ids (the rest, in template order) and passed (true when mentioned / total >= pass_threshold).
