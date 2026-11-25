export type Locale = "en" | "hi";

const DICT: Record<Locale, Record<string, string>> = {
  en: {
    "app.name": "TablePulse",
    "nav.floor": "Live Floor",
    "nav.cameras": "Live Cameras",
    "nav.alerts": "Alerts",
    "nav.waitlist": "Waitlist",
    "nav.analytics": "Analytics",
    "nav.ml_review": "ML Review",
    "nav.cam_settings": "Cameras",
    "nav.alert_rules": "Alert Rules",
    "nav.users": "Users & Audit",
    "nav.system": "System & Privacy",
    "status.live": "Live",
    "status.reconnecting": "Reconnecting...",
    "status.polling": "Polling Fallback",
    "status.ai_paused": "AI Paused — Manual Floor Mode",
    "action.sign_in": "Sign In",
    "action.sign_out": "Sign Out",
    "action.mark_clean": "Mark Clean (Free)",
    "action.mark_served": "Mark Service Attended",
  },
  hi: {
    "app.name": "TablePulse",
    "nav.floor": "लाइव फ्लोर",
    "nav.cameras": "लाइव कैमरे",
    "nav.alerts": "अलर्ट्स",
    "nav.waitlist": "प्रतीक्षा सूची",
    "nav.analytics": "विश्लेषण",
    "nav.ml_review": "ML समीक्षा",
    "nav.cam_settings": "कैमरा सेटिंग्स",
    "nav.alert_rules": "अलर्ट नियम",
    "nav.users": "उपयोगकर्ता व ऑडिट",
    "nav.system": "सिस्टम व गोपनीयता",
    "status.live": "लाइव",
    "status.reconnecting": "पुनः कनेक्ट हो रहा है...",
    "status.polling": "पोलिंग मोड",
    "status.ai_paused": "AI रुका हुआ — मैनुअल मोड",
    "action.sign_in": "साइन इन करें",
    "action.sign_out": "साइन आउट",
    "action.mark_clean": "साफ़ चिह्नित करें (खाली)",
    "action.mark_served": "सेवा पूर्ण चिह्नित करें",
  },
};

export function t(locale: Locale, key: string): string {
  return DICT[locale]?.[key] ?? DICT.en[key] ?? key;
}
