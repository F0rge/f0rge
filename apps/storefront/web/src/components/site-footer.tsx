import Link from "next/link";
import { contactDetails, currentCustomerPolicies } from "@/lib/customer-policies";
import { Wordmark } from "./wordmark";

export function SiteFooter() {
  const contact = contactDetails(currentCustomerPolicies());
  return <footer className="site-footer">
    <div className="footer-main">
      <div className="footer-brand"><Link href="/" className="wordmark" aria-label="DasKasas home"><Wordmark /></Link><p>Furniture for living and dining rooms.</p></div>
      <nav aria-label="Explore DasKasas"><p className="eyebrow">Explore</p><Link href="/shop">All furniture</Link><Link href="/collections">Collections</Link><Link href="/account">Your account</Link><Link href="/bag">Your bag</Link></nav>
      <nav aria-label="Policies" className="footer-policies"><p className="eyebrow">Policies</p><div><Link href="/policies/privacy">Privacy</Link><Link href="/policies/terms">Terms</Link><Link href="/policies/refunds">Refunds</Link><Link href="/policies/returns">Returns</Link><Link href="/policies/delivery">Delivery</Link><Link href="/contact">Contact</Link></div></nav>
      <address className="footer-contact"><p className="eyebrow">Contact</p><dl><dt>Email</dt><dd>{contact.email}</dd><dt>Phone</dt><dd>{contact.phone}</dd><dt>Address</dt><dd>{contact.address}</dd></dl></address>
    </div>
    <div className="footer-bottom"><span>© {new Date().getFullYear()} DasKasas</span><span>Prices in rand, VAT included</span><Link href="/shop">All furniture <span aria-hidden="true">→</span></Link></div>
  </footer>;
}
