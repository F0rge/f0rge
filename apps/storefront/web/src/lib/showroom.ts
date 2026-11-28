// Public showroom facts, confirmed by Leo on 21 Nov 2026 (F0rge/f0rge#1000).
// Kept apart from the owner policy document, which stays unset until it is reviewed.
const streetAddress = "Shop GL15, Bedford Square, Smith Road";
const addressLocality = "Bedfordview";
const postalCode = "2007";
const telephone = "+27 10 745 1980";

export const SHOWROOM = {
  name: "DasKasas, Bedford Square",
  address: `${streetAddress}, ${addressLocality}, Johannesburg, ${postalCode}`,
  postalAddress: { streetAddress, addressLocality, addressRegion: "Gauteng", postalCode, addressCountry: "ZA" },
  note: "Bedford Square is inside Bedford Centre.",
  hours: [
    {
      days: "Monday to Friday",
      short: "Mon–Fri",
      dayOfWeek: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      opens: "09:00",
      closes: "18:00",
    },
    { days: "Saturday", short: "Sat", dayOfWeek: ["Saturday"], opens: "09:00", closes: "17:00" },
    { days: "Sunday", short: "Sun", dayOfWeek: ["Sunday"], opens: "09:00", closes: "15:00" },
  ].map((row) => ({ ...row, time: `${row.opens}–${row.closes}` })),
  telephone,
  phones: [
    { label: "Mobile", number: "+27 63 025 4010" },
    { label: "Showroom", number: telephone.replace(/^\+27 /, "0") },
  ],
  email: "Cindy@daskasas.co.za",
} as const;

