import Link from "next/link";
import { contactDetails, currentCustomerPolicies } from "@/lib/customer-policies";
import { Wordmark } from "./wordmark";

export function SiteFooter() {
  const contact = contactDetails(currentCustomerPolicies());
  return <footer className="site-footer">
    <div className="footer-main">
      <div className="footer-brand"><Link href="/" className="wordmark" aria-label="Vellano home"><Wordmark /></Link><p>Furniture for<br />everyday life.</p></div>
      <nav aria-label="Explore Vellano"><p className="eyebrow">Explore</p><Link href="/shop">All furniture</Link><Link href="/collections">Collections</Link><Link href="/account">Your account</Link><Link href="/bag">Your bag</Link></nav>
      <nav aria-label="Policies"><p className="eyebrow">Policies</p><Link href="/policies/privacy">Privacy</Link><Link href="/policies/terms">Terms</Link><Link href="/policies/refunds">Refunds</Link><Link href="/policies/returns">Returns</Link><Link href="/policies/delivery">Delivery</Link><Link href="/contact">Contact</Link></nav>
      <address className="footer-contact"><p className="eyebrow">Contact</p><p>{contact.email}</p><p>{contact.phone}</p><p>{contact.address}</p></address>
    </div>
    <div className="footer-bottom"><span>© {new Date().getFullYear()} Vellano</span><span>Make space for everyday life.</span><Link href="/shop">Find your next piece <span aria-hidden="true">↗</span></Link></div>
  </footer>;
}
