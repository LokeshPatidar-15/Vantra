import ChartArt from "./ChartArt";
import { ActivityIcon, HistoryIcon, LayersIcon, TrendIcon } from "./icons";

// Optional photo background. Leave it empty to use the drawn gold chart.
// To use a photo: save it as frontend/public/login-bg.jpg and set "/login-bg.jpg" below.
const BACKGROUND_IMAGE = "";

const FEATURES = [
  { label: "Backtesting Strategies", icon: <HistoryIcon size={22} /> },
  { label: "Market Analysis", icon: <TrendIcon size={22} /> },
  { label: "Real-time Data", icon: <ActivityIcon size={22} /> },
  { label: "Multi-Asset Support", icon: <LayersIcon size={22} /> },
];

// Shared shell for the login and signup pages. `children` is the form.
export default function AuthLayout({ title, subtitle, children }) {
  const pageStyle = BACKGROUND_IMAGE
    ? {
        backgroundImage: `linear-gradient(90deg, rgba(8,11,17,0.94) 0%, rgba(8,11,17,0.6) 55%, rgba(8,11,17,0.92) 100%), url(${BACKGROUND_IMAGE})`,
      }
    : undefined;

  return (
    <div className="auth-page" style={pageStyle}>
      {!BACKGROUND_IMAGE && <ChartArt />}

      <div className="auth-shell">
        <section className="auth-hero">
          <div className="hero-brand">
            <div className="brand-wordmark">Vantra</div>
            <div className="brand-tagline">TRADE SMARTER</div>
            <div className="hero-rule" />
            <p className="hero-copy">Smarter tools. Better analysis.<br />Stronger decisions.</p>
          </div>

          <div className="hero-features">
            {FEATURES.map((feature) => (
              <div className="feature" key={feature.label}>
                <div className="feature-icon">{feature.icon}</div>
                <div className="feature-label">{feature.label}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="auth-panel">
          <div className="auth-card">
            <h1 className="auth-title">{title}</h1>
            {subtitle && <p className="auth-subtitle">{subtitle}</p>}
            {children}
          </div>
        </section>
      </div>
    </div>
  );
}
