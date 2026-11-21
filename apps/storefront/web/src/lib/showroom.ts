// Public showroom facts, confirmed by Leo on 21 Nov 2026 (F0rge/f0rge#1000).
// Kept apart from the owner policy document, which stays unset until it is reviewed.
export const SHOWROOM = {
  name: "DasKasas, Bedford Square",
  address: "Shop GL15, Bedford Square, Smith Road, Bedfordview, Johannesburg, 2007",
  note: "Bedford Square is inside Bedford Centre.",
  hours: [
    { days: "Monday to Friday", short: "Mon–Fri", time: "09:00–18:00" },
    { days: "Saturday", short: "Sat", time: "09:00–17:00" },
    { days: "Sunday", short: "Sun", time: "09:00–15:00" },
  ],
  phones: [
    { label: "Mobile", number: "+27 63 025 4010" },
    { label: "Showroom", number: "010 745 1980" },
  ],
  email: "Cindy@daskasas.co.za",
} as const;

