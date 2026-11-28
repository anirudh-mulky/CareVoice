/** Plain-language reasons for each unclear field the server reports. */
export function unclearReason(field: string): string {
  if (field.startsWith("extra_instructions")) return "Say or type the exact dose and how often.";
  return (
    {
      patient_name: "Add the patient's name.",
      age: "Add the patient's age.",
      template_name: "Choose a template.",
      language: "Choose the patient's language.",
      carer_phone: "Check the phone number (10 digits).",
    }[field] ?? "Please check this."
  );
}

export function isUnclear(unclear: string[], field: string): boolean {
  return unclear.includes(field);
}
