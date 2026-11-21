import type { MadeToOrderOffer } from "./medusa";

// One rule for the product page and the listings: an offer counts only while Firstout saw it in the last five minutes.
export function offerFresh(offer: MadeToOrderOffer | null | undefined, now = Date.now()): boolean {
  const observedAt = offer?.observed_at ? Date.parse(offer.observed_at) : NaN;
  return Number.isFinite(observedAt) && now - observedAt <= 5 * 60_000 && observedAt <= now + 60_000;
}

export function offerLive(offer: MadeToOrderOffer | null | undefined, now = Date.now()): offer is MadeToOrderOffer {
  return !!offer && offerFresh(offer, now) && offer.remaining_capacity > 0 && Date.parse(offer.expires_at) > now;
}
