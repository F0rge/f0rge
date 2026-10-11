import Link from "next/link";

export function SiteFooter() {
  return <footer className="site-footer">
    <div className="footer-main">
      <div className="footer-brand"><Link href="/" className="wordmark" aria-label="Vellano home">VELLANO</Link><p>Considered pieces.<br />Everyday living.</p></div>
      <nav aria-label="Explore Vellano"><p className="eyebrow">Explore</p><Link href="/shop">All furniture</Link><Link href="/collections">Collections</Link><Link href="/account">Your account</Link><Link href="/bag">Your bag</Link></nav>
      <nav aria-label="Support and policies"><p className="eyebrow">Here to help</p><Link href="/support">Support</Link><Link href="/policies/delivery">Delivery and collection</Link><Link href="/policies/returns">Returns and refunds</Link><Link href="/policies/privacy">Privacy</Link></nav>
    </div>
    <div className="footer-bottom"><span>© {new Date().getFullYear()} Vellano</span><span>A home, thoughtfully yours.</span><Link href="/shop">Find your next piece <span aria-hidden="true">↗</span></Link></div>
  </footer>;
}
