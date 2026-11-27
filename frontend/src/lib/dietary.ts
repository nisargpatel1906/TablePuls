const DIETARY_LABELS: Record<string, { en: string; hi: string }> = {
  VEG: { en: "Veg", hi: "शाकाहारी" },
  NON_VEG: { en: "Non-Veg", hi: "मांसाहारी" },
  VEGAN: { en: "Vegan", hi: "वीगन" },
  GLUTEN_FREE: { en: "Gluten-Free", hi: "ग्लूटेन-फ्री" },
  DAIRY_FREE: { en: "Dairy-Free", hi: "डेयरी-फ्री" },
  NUT_FREE: { en: "Nut-Free", hi: "नट-फ्री" },
  SPICY_MILD: { en: "Mild", hi: "हल्का तीखा" },
  SPICY_MEDIUM: { en: "Medium", hi: "मध्यम तीखा" },
  SPICY_HOT: { en: "Hot", hi: "तीखा" },
  CHEF_SPECIAL: { en: "Chef's Special", hi: "शेफ स्पेशल" },
};

/** Formats a canonical dietary enum tag into a human-readable badge label. */
export function formatDietaryTag(tag: string, locale: "en" | "hi" = "en"): string {
  const entry = DIETARY_LABELS[tag];
  if (entry) return entry[locale];
  return tag.replaceAll("_", " ");
}
