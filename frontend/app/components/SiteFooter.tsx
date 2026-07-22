export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div className="footer-brand"><strong>NUTRIFIT</strong><p>Nutrition &amp; Performance</p><small>Fuel Your Body. Elevate Your Performance.</small></div>
        <div className="footer-links"><strong>Navigation</strong><a href="#catalogue">Produits</a><a href="/login">Se connecter</a><a href="/register">Creer un compte</a></div>
        <div className="footer-links"><strong>Services</strong><span>Livraison partout au Maroc</span><span>Paiement a la livraison</span><span>Paiement par carte en mode test</span></div>
        <div className="footer-links"><strong>Contact</strong><a href="mailto:support@nutrifit.ma">support@nutrifit.ma</a><span>Lundi - Samedi</span><span>09:00 - 18:00</span></div>
      </div>
      <div className="shell footer-bottom"><span>© 2026 NUTRIFIT. Tous droits reserves.</span><span>Complements alimentaires · Informations transparentes</span></div>
    </footer>
  );
}
