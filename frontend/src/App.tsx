import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  CalendarDays,
  CloudRain,
  FileImage,
  ArrowUpRight,
  ArrowRight,
  Home,
  Leaf,
  MapPin,
  MessageSquareText,
  Newspaper,
  Search,
  ShoppingCart,
  Sprout,
  Sun,
  Warehouse,
  Menu,
  X,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  addTask,
  analyzeCrop,
  screenCropDisease,
  askAssistant,
  getAssistantStatus,
  calculateProfit,
  deleteTask,
  getCalendar,
  getDashboard,
  getDecision,
  getMarketOptions,
  getMarketPrices,
  getMarketTrend,
  getNews,
  getStorage,
  getStorageDetails,
  getWeather,
  getNotifications,
  markNotificationRead,
  updateAuthProfile,
  updateTask,
  signup,
  login,
  logout,
  getAuthUser,
} from './services/api';
import type { CalendarTask, DashboardData, MandiPricesResponse, NewsItem, StorageItem, Weather } from './types';
import { filterAndSortStorage, storageListState } from './storageUtils.ts';
import { shouldSubmitAssistantOnEnter } from './assistantKeyboard.ts';
import { AssistantErrorMessage, AssistantMarkdown } from './assistantMarkdown.ts';
import { authenticatedDisplayName } from './userIdentity.ts';
import { getTranslation, type LanguageCode } from './i18n';
import { FarmToolPage, FarmToolsSection } from './FarmTools';

const navItems = [
  { path: '/dashboard', label: 'nav.dashboard', icon: Home },
  { path: '/dashboard/crop-doctor', label: 'nav.cropDoctor', icon: Leaf },
  { path: '/dashboard/market', label: 'nav.market', icon: BarChart3 },
  { path: '/dashboard/weather', label: 'nav.weather', icon: CloudRain },
  { path: '/dashboard/storage', label: 'nav.storage', icon: Warehouse },
  { path: '/dashboard/calendar', label: 'nav.calendar', icon: CalendarDays },
  { path: '/dashboard/news', label: 'nav.news', icon: Newspaper },
  { path: '/dashboard/assistant', label: 'nav.assistant', icon: MessageSquareText },
];

const translate = (language: LanguageCode, key: string) => getTranslation(language, key);

function AgriMark() {
  return <svg className="agri-mark" viewBox="0 0 32 32" role="img" aria-label="AgriSense sprout and sunrise mark">
    <path d="M6 14a10 10 0 0 1 20 0" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    <path d="M16 25V15m0 5c-4.5 0-7-2.2-7-6 4.8 0 7 2.2 7 6Zm0-3c0-4.4 2.5-7 7-7 0 4.6-2.2 7-7 7Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="16" cy="27" r="1.4" fill="currentColor" />
  </svg>;
}

function App() {
  const [language, setLanguage] = useState<LanguageCode>('en');
  const [user, setUser] = useState<{ id: number; name: string; email: string } | null>(null);
  useEffect(() => {
    const token = sessionStorage.getItem('agrisense_session');
    if (!token) return;
    getAuthUser().then((restoredUser) => {
      if (sessionStorage.getItem('agrisense_session') === token) setUser(restoredUser);
    }).catch(() => {
      if (sessionStorage.getItem('agrisense_session') === token) {
        sessionStorage.removeItem('agrisense_session');
        setUser(null);
      }
    });
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<AuthPage mode="login" onAuthenticated={setUser} />} />
        <Route path="/signup" element={<AuthPage mode="signup" onAuthenticated={setUser} />} />
        <Route path="/dashboard/*" element={<div className="app-shell"><Sidebar language={language} /><main className="content-panel"><TopBar language={language} onLanguageChange={setLanguage} user={user} onLogout={async () => { try { await logout(); } catch { /* local sign-out still clears an expired session */ } finally { sessionStorage.removeItem('agrisense_session'); setUser(null); } }} /><Routes>
            <Route index element={<DashboardPage language={language} user={user} />} />
            <Route path="profile" element={<LoginRequired><ProfilePage key={user?.id ?? 'loading'} user={user} onUserUpdated={setUser} /></LoginRequired>} />
            <Route path="crop-doctor" element={<CropDoctorPage language={language} />} />
            <Route path="market" element={<MarketPage language={language} />} />
            <Route path="weather" element={<WeatherPage language={language} />} />
            <Route path="storage" element={<StoragePage language={language} />} />
            <Route path="calendar" element={<LoginRequired><CalendarPage language={language} /></LoginRequired>} />
            <Route path="news" element={<NewsPage language={language} />} />
            <Route path="assistant" element={<AssistantPage language={language} />} />
            <Route path="notifications" element={<NotificationsPage language={language} />} />
            <Route path="planner" element={<LoginRequired><FarmToolPage key="planner" /></LoginRequired>} />
            <Route path="profit-loss" element={<LoginRequired><FarmToolPage key="profit-loss" /></LoginRequired>} />
            <Route path="crop-journal" element={<LoginRequired><FarmToolPage key="crop-journal" /></LoginRequired>} />
            <Route path="reports" element={<LoginRequired><FarmToolPage key="reports" /></LoginRequired>} />
            <Route path="harvest" element={<LoginRequired><FarmToolPage key="harvest" /></LoginRequired>} />
            <Route path="unit-converter" element={<FarmToolPage key="unit-converter" />} />
            <Route path="knowledge" element={<FarmToolPage key="knowledge" />} />
            <Route path="*" element={<div className="card metric-card"><h2>Page not found</h2><Link className="primary-btn" to="/dashboard">Return to dashboard</Link></div>} />
          </Routes></main></div>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const featureCards = [
    [Leaf, 'Crop Doctor', 'Identify plant species from a photo. Results are identification, not a disease diagnosis.', '/dashboard/crop-doctor'],
    [CloudRain, 'Weather insights', 'Explore forecasts and rainfall conditions from the configured weather source.', '/dashboard/weather'],
    [BarChart3, 'Market & profit', 'Review mandi records when available and calculate sell or store scenarios.', '/dashboard/market'],
    [Warehouse, 'Storage finder', 'Browse facility examples clearly marked as sample information.', '/dashboard/storage'],
    [Newspaper, 'Agriculture news', 'Search agricultural updates from the configured news provider.', '/dashboard/news'],
    [CalendarDays, 'Farm calendar', 'Plan and track crop tasks in the shared demo calendar.', '/dashboard/calendar'],
    [MessageSquareText, 'Ask AgriSense', 'Ask an agricultural question using available farm context.', '/dashboard/assistant'],
    [Home, 'Farm dashboard', 'See available weather, crop, market and planning information together.', '/dashboard'],
  ] as const;
  return <div className="landing-page">
    <header className="landing-nav"><Link to="/" className="landing-brand"><span className="brand-badge"><AgriMark/></span><span>AgriSense <em>AI</em></span></Link>
      <button className="landing-menu-button" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X/> : <Menu/>}</button>
      <nav className={menuOpen ? 'landing-links open' : 'landing-links'}><a href="#features" onClick={() => setMenuOpen(false)}>Features</a><a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works</a><a href="#about" onClick={() => setMenuOpen(false)}>About</a><Link to="/login">Log in</Link><Link className="landing-signup" to="/signup">Sign up</Link></nav>
    </header>
    <main>
      <section className="landing-hero"><div className="landing-hero-copy"><span className="landing-kicker"><Sprout size={16}/> Practical tools for everyday farming</span><h1>Smarter farming.<br/><span>Better decisions.</span><br/>Healthier harvests.</h1><p>Crop identification, weather insights, market information, and farm planning tools in one easy-to-use place.</p><div className="landing-actions"><Link className="landing-primary" to="/signup">Get started <ArrowUpRight size={18}/></Link><a className="landing-secondary" href="#features">Explore features <ArrowRight size={17}/></a></div><small>Information depends on available data and provider access. See source labels in each tool.</small></div><div className="landing-illustration" aria-label="Illustration of green crop rows beneath a golden sunrise" role="img"><div className="sun-disc"/><div className="field-line line-one"/><div className="field-line line-two"/><div className="field-line line-three"/><div className="sprout-art"><Sprout size={88}/></div><span className="illustration-label">GROW WITH GOOD INFORMATION</span></div></section>
      <section className="landing-section" id="features"><div className="landing-section-heading"><span className="landing-kicker">TOOLS FOR YOUR FARM</span><h2>Useful information, in one place</h2><p>Choose a tool to explore. Availability and data sources are identified inside each feature.</p></div><div className="landing-feature-grid">{featureCards.map(([Icon, title, body, path]) => <Link to={path} className="landing-feature" key={title}><span className="landing-feature-icon"><Icon size={22}/></span><h3>{title}</h3><p>{body}</p><span className="landing-feature-link">Explore tool <ArrowUpRight size={15}/></span></Link>)}</div></section>
      <section className="landing-how" id="how-it-works"><span className="landing-kicker">HOW IT WORKS</span><h2>Start with what you know.<br/>Use the data that is available.</h2><div className="how-steps"><div><b>01</b><h3>Choose a farm tool</h3><p>Open a module for crops, weather, markets, planning, or questions.</p></div><div><b>02</b><h3>Review the source</h3><p>Live provider results, farmer inputs, and sample data are labelled in context.</p></div><div><b>03</b><h3>Make your own decision</h3><p>Use the information as guidance. AgriSense does not replace local agricultural advice.</p></div></div></section>
      <section className="landing-about" id="about"><div><span className="landing-kicker">BUILT FOR CLEARER FARM DECISIONS</span><h2>Technology that stays grounded in the field.</h2></div><p>AgriSense AI brings agricultural tools together in a single responsive application. Some integrations require provider credentials or current data access. The platform labels limitations and does not promise outcomes, yields, or diagnoses.</p></section>
      <section className="landing-cta"><div><span className="landing-kicker">EXPLORE AGRISENSE AI</span><h2>Make your next farm decision with more context.</h2></div><Link className="landing-primary" to="/dashboard">Open the dashboard <ArrowUpRight size={18}/></Link></section>
    </main><footer className="landing-footer"><Link to="/" className="landing-brand"><AgriMark/> AgriSense AI</Link><span>Practical agricultural information. Clear about its sources.</span><Link to="/login">Account</Link></footer>
  </div>;
}

function LoginRequired({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return sessionStorage.getItem('agrisense_session')
    ? children
    : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}

function AuthPage({ mode, onAuthenticated }: { mode: 'login' | 'signup'; onAuthenticated: (user: { id: number; name: string; email: string }) => void }) {
  const isSignup = mode === 'signup';
  const [name, setName] = useState(''); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError('');
    if (isSignup && password !== confirm) { setError('Passwords do not match.'); return; }
    if (isSignup && !/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{12,128}$/.test(password)) { setError('Use at least 12 characters with upper and lowercase letters, a number, and a symbol.'); return; }
    setLoading(true);
    try { const result = isSignup ? await signup(name, email, password) : await login(email, password); sessionStorage.setItem('agrisense_session', result.access_token); onAuthenticated(result.user); const requestedPath = (location.state as { from?: unknown } | null)?.from; navigate(typeof requestedPath === 'string' && requestedPath.startsWith('/dashboard/') ? requestedPath : '/dashboard'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Account request failed. Please try again.'); }
    finally { setLoading(false); }
  };
  return <div className="auth-page"><Link to="/" className="landing-brand auth-brand"><span className="brand-badge"><AgriMark/></span>AgriSense <em>AI</em></Link><div className="auth-panel"><span className="landing-kicker">YOUR FARM, YOUR TOOLS</span><h1>{isSignup ? 'Create your account' : 'Welcome back'}</h1><p className="muted">{isSignup ? 'Create an account to access your AgriSense profile.' : 'Sign in to your AgriSense account.'}</p><form onSubmit={submit}>
    {isSignup && <div className="field"><label htmlFor="auth-name">Full name</label><input id="auth-name" autoComplete="name" required maxLength={100} value={name} onChange={e => setName(e.target.value)}/></div>}
    <div className="field"><label htmlFor="auth-email">Email address</label><input id="auth-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)}/></div>
    <div className="field"><label htmlFor="auth-password">Password</label><div className="password-input"><input id="auth-password" type={showPassword ? 'text' : 'password'} autoComplete={isSignup ? 'new-password' : 'current-password'} required minLength={isSignup ? 12 : 1} maxLength={128} value={password} onChange={e => setPassword(e.target.value)}/><button type="button" onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'}</button></div>{isSignup && <small>At least 12 characters, with uppercase, lowercase, a number, and a symbol.</small>}</div>
    {isSignup && <div className="field"><label htmlFor="auth-confirm">Confirm password</label><input id="auth-confirm" type={showPassword ? 'text' : 'password'} autoComplete="new-password" required value={confirm} onChange={e => setConfirm(e.target.value)}/></div>}
    {error && <div className="auth-error" role="alert">{error}</div>}<button className="landing-primary auth-submit" disabled={loading}>{loading ? 'Please wait…' : isSignup ? 'Create account' : 'Log in'}</button>
    </form><p className="auth-switch">{isSignup ? 'Already have an account?' : 'New to AgriSense AI?'} <Link to={isSignup ? '/login' : '/signup'}>{isSignup ? 'Log in' : 'Create an account'}</Link></p><p className="auth-note">Calendar tasks you add are private to your account. Existing example records and other farm information are shared demonstration data.</p></div></div>;
}

function Sidebar({ language }: { language: LanguageCode }) {
  return (
    <aside className="sidebar">
      <Link to="/" className="brand">
        <div className="brand-badge"><AgriMark /></div>
        <div className="brand-text">AgriSense AI</div>
      </Link>
      <nav className="sidebar-nav">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink key={path} to={path} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Icon size={17} />
            {translate(language, label)}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

function TopBar({ language, onLanguageChange, user, onLogout }: { language: LanguageCode; onLanguageChange: (lang: LanguageCode) => void; user: { name: string } | null; onLogout: () => void }) {
  const location = useLocation();
  return (
    <header className="topbar">
      <h1>{translate(language, 'dashboard.whatShould')}</h1>
      <div className="controls">
        {user ? <><Link className="topbar-user" to="/dashboard/profile" aria-label={`Edit profile for ${authenticatedDisplayName(user.name)}`}>{authenticatedDisplayName(user.name)}</Link><button className="ghost-btn" type="button" onClick={onLogout}>Log out</button></> : <Link className="ghost-btn topbar-login" to="/login" state={{ from: location.pathname }}>Log in</Link>}
        <select className="select" value={language} onChange={(e) => onLanguageChange(e.target.value as LanguageCode)} aria-label="Select language">
          <option value="en">English</option>
          <option value="hi">हिन्दी</option>
          <option value="te">తెలుగు</option>
          <option value="kn">ಕನ್ನಡ</option>
          <option value="ta">தமிழ்</option>
        </select>
      </div>
    </header>
  );
}

function DashboardPage({ language, user }: { language: LanguageCode; user: { name: string } | null }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);

  const load = () => {
    setLoading(true); setError('');
    let active = true;
    getDashboard().then((data) => {
      if (active) {
        setDashboard(data);
        setLoading(false);
      }
    }).catch((reason) => { if (active) { setError(reason instanceof Error ? reason.message : 'Dashboard could not load.'); setLoading(false); } });
    return () => { active = false; };
  };
  useEffect(() => load(), []);

  if (loading) {
    return (
      <div className="page-shell">
        <LoadingSkeleton />
      </div>
    );
  }
  if (!dashboard) return <div className="page-shell"><div className="card metric-card"><p role="alert">{error}</p><button className="primary-btn" onClick={load}>Retry</button></div></div>;

  const weatherToday = dashboard.weather[0];
  const metrics = [
    { label: 'Weather', value: weatherToday.current_temperature == null ? '—' : `${weatherToday.current_temperature}°C`, icon: Sun },
    { label: 'Crop stage · DEMO', value: dashboard.crop.current_stage, icon: Leaf },
    { label: 'Farm size · DEMO', value: `${dashboard.farmer.farm_size} acres`, icon: MapPin },
    { label: 'Market', value: dashboard.market[0]?.price_compatible && dashboard.market[0].price != null ? `₹${dashboard.market[0].price}/${dashboard.market[0].unit}` : dashboard.market[0]?.source_price == null ? '—' : `₹${dashboard.market[0].source_price} (unit unspecified)`, icon: ShoppingCart },
  ];

  return (
    <div className="page-shell">
      <section className="grid-2 dashboard-primary-grid">
        <div className="card hero-card">
          <div className="hero-header">
            <div>
              <div className="muted">{translate(language, 'dashboard.greeting')} {authenticatedDisplayName(user?.name)}</div>
              <div className="muted">Account: {authenticatedDisplayName(user?.name)} · farm and crop records below are DEMO DATA</div>
              <h2 className="big-text">{translate(language, 'dashboard.whatShould')}</h2>
            </div>
            <div className={`decision-badge ${dashboard.decision.recommendation.toLowerCase()}`}>
              {dashboard.decision.recommendation}
            </div>
          </div>
          <div className="split">
            <div>
              <div className="muted">{translate(language, 'dashboard.decision')}</div>
              <h3 style={{ margin: '10px 0 0', fontSize: '2rem' }}>{dashboard.decision.recommendation}</h3>
            </div>
            <div>
              <div className="muted">{translate(language, 'dashboard.confidence')}</div>
              <div style={{ fontSize: '2rem', fontWeight: 800 }}>{dashboard.decision.confidence.toFixed(0)}%</div>
            </div>
          </div>
          <div className="action-row">
            <button className="primary-btn" onClick={() => navigate('/dashboard/market')}>{translate(language, 'common.viewAnalysis')}</button>
            <button className="secondary-btn" onClick={() => navigate('/dashboard/assistant')}>{translate(language, 'common.askAi')}</button>
          </div>
          <ul className="reason-list">
            {dashboard.decision.reasons.map((reason) => (
              <li key={reason}><span className="check">✓</span>{reason}</li>
            ))}
          </ul>
          <div className="muted">{dashboard.decision_data_source} {dashboard.decision.data_date ? `· ${dashboard.decision.data_date}` : ''}</div>
          {dashboard.decision.missing_inputs?.length ? <p className="muted">Missing inputs: {dashboard.decision.missing_inputs.join(', ')}</p> : null}
          {dashboard.decision.status === 'insufficient_data' && <span className="demo-pill">WAIT · INCOMPLETE INPUTS</span>}
          {Object.keys(dashboard.decision.score_breakdown ?? {}).length > 0 && <details><summary>Score breakdown</summary>{Object.entries(dashboard.decision.score_breakdown ?? {}).map(([action, factors]) => <div key={action} className="muted">{action}: {Object.entries(factors).map(([name, value]) => `${name} ${value}`).join(' · ')}</div>)}</details>}
        </div>

        <div className="card list-card dashboard-alerts-card">
          <div className="dashboard-alerts-heading"><h3 className="section-title">{translate(language, 'dashboard.alerts')}</h3><Link to="/dashboard/notifications">View all</Link></div>
          <div className="notification-list">
            {dashboard.notifications.length ? dashboard.notifications.map((item) => (
              <div className="notification-item" key={item.id}>
                <div className="notification-top">
                  <strong>{item.title} {item.data_source && <span className="muted">· {item.data_source}</span>}</strong>
                  <span className={`pill ${item.severity.toLowerCase()}`}>{item.severity}</span>
                </div>
                <div className="muted">{item.message}</div>
              </div>
            )) : <p className="muted">No alerts are currently available.</p>}
          </div>
        </div>
      </section>

      <section className="grid-4 dashboard-metrics">
        {metrics.map(({ label, value, icon: Icon }) => (
          <div key={label} className="card metric-card">
            <div className="label"><Icon size={18} style={{ verticalAlign: 'middle', marginRight: 8 }} />{label}</div>
            <div className="value">{value}</div>
            {label === 'Market' && <div className="muted">{dashboard.market_error ?? dashboard.market[0]?.data_source ?? 'No mandi result'} · {dashboard.market[0]?.date ?? 'arrival date unavailable'} · {dashboard.market[0]?.price_label ?? 'No market price available'}</div>}
          </div>
        ))}
      </section>

      <section className="dashboard-tools" aria-labelledby="dashboard-tools-title">
        <div className="dashboard-tools-heading">
          <div>
            <span className="eyebrow">YOUR FARM, AT A GLANCE</span>
            <h3 id="dashboard-tools-title" className="section-title">Explore your farm tools</h3>
          </div>
          <Sprout size={22} aria-hidden="true" />
        </div>
        <div className="feature-grid">
          {[
            { path: '/dashboard/crop-doctor', label: 'nav.cropDoctor', icon: Leaf, tone: 'leaf' },
            { path: '/dashboard/market', label: 'nav.market', icon: BarChart3, tone: 'harvest' },
            { path: '/dashboard/weather', label: 'nav.weather', icon: CloudRain, tone: 'sky' },
            { path: '/dashboard/storage', label: 'nav.storage', icon: Warehouse, tone: 'earth' },
            { path: '/dashboard/news', label: 'nav.news', icon: Newspaper, tone: 'leaf' },
          ].map(({ path, label, icon: Icon, tone }) => (
            <button className="feature-card" key={path} type="button" onClick={() => navigate(path)}>
              <span className={`feature-icon ${tone}`}><Icon size={20} aria-hidden="true" /></span>
              <span className="feature-label">{translate(language, label)}</span>
              <ArrowUpRight size={17} className="feature-arrow" aria-hidden="true" />
            </button>
          ))}
        </div>
      </section>

      <section className="grid-2">
        <div className="card chart-card">
          <h3 className="section-title">Weather</h3>
          <div className="muted">{dashboard.weather[0]?.data_source ?? 'Forecast source unavailable'}</div>
          <div className="weather-grid">
            {dashboard.weather.map((day) => (
              <div className="weather-box" key={day.date}>
                <strong>{new Date(day.date).toLocaleDateString('en', { month: 'short', day: 'numeric' })}</strong>
                <div className="inline-stat"><span>{day.weather_condition}</span><span>{day.temperature}°C</span></div>
                <div className="inline-stat"><span>Rain</span><span>{day.rainfall_probability}%</span></div>
                {day.current_humidity != null && <div className="inline-stat"><span>Current humidity</span><span>{day.current_humidity}%</span></div>}
              </div>
            ))}
          </div>
        </div>

        <div className="card list-card">
          <h3 className="section-title">{translate(language, 'dashboard.tasks')}</h3>
          <div className="task-list">
            {dashboard.tasks.map((task) => (
              <div className="task-item" key={task.id}>
                <div className="notification-top">
                  <strong>{task.title}</strong>
                  <span className={`pill ${task.priority === 'High' ? 'high' : task.priority === 'Medium' ? 'medium' : 'low'}`}>{task.priority}</span>
                </div>
                <div className="muted">{task.crop} • {task.date} · {task.data_source ?? 'DEMO DATA'}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <FarmToolsSection />
    </div>
  );
}

function MarketPage({ language }: { language: LanguageCode }) {
  const [state, setState] = useState('Karnataka');
  const [commodity, setCommodity] = useState('Tomato');
  const [options, setOptions] = useState<{ states: string[]; commodities: string[] }>({ states: [], commodities: [] });
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState('');
  const [optionsRetry, setOptionsRetry] = useState(0);
  const [prices, setPrices] = useState<MandiPricesResponse | null>(null);
  const [trend, setTrend] = useState<any>(null);
  const [profit, setProfit] = useState<any>(null);
  const [decision, setDecision] = useState<any>(null);
  const [weather, setWeather] = useState<Weather[]>([]);
  const [storageSites, setStorageSites] = useState<StorageItem[]>([]);
  const [quantity, setQuantity] = useState(0);
  const [currentPrice, setCurrentPrice] = useState<number | ''>('');
  const [currentPriceSource, setCurrentPriceSource] = useState('Farmer entered');
  const [expectedPrice, setExpectedPrice] = useState<number | ''>('');
  const [storageCost, setStorageCost] = useState<number | ''>('');
  const [transportCost, setTransportCost] = useState<number | ''>('');
  const [productionCost, setProductionCost] = useState<number | ''>('');
  const [otherExpenses, setOtherExpenses] = useState<number | ''>('');
  const [storageDays, setStorageDays] = useState<number | ''>('');
  const [readiness, setReadiness] = useState<number | ''>('');
  const [demand, setDemand] = useState<number | ''>('');
  const [loading, setLoading] = useState(true);
  const [marketError, setMarketError] = useState('');
  const [trendError, setTrendError] = useState('');
  const [profitError, setProfitError] = useState('');
  const [decisionError, setDecisionError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const rows = prices?.success && Array.isArray(prices.data) ? prices.data : [];
  const hasCommodityOption = options.commodities.includes(commodity);

  useEffect(() => {
    let active = true;
    setOptionsLoading(true);
    setOptionsError('');
    getMarketOptions(state).then((result) => {
      if (active) setOptions({ states: result.states, commodities: result.commodities });
    }).catch((reason) => {
      if (active) setOptionsError(reason instanceof Error ? reason.message : 'Market choices could not load.');
    }).finally(() => { if (active) setOptionsLoading(false); });
    return () => { active = false; };
  }, [state, optionsRetry]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setMarketError('');
    setTrendError('');
    Promise.all([getWeather().catch(() => []), getStorage().catch(() => [])]).then(([weatherData, storageData]) => {
      if (active) { setWeather(weatherData); setStorageSites(storageData); }
    });
    getMarketPrices(state, commodity, refreshKey > 0).then((result) => {
      if (!active) return;
      setPrices(result);
      setLoading(false);
      getMarketTrend(state, commodity).then((trendResult) => {
        if (active) setTrend(trendResult);
      }).catch((reason) => {
        if (active) { setTrend(null); setTrendError(reason instanceof Error ? reason.message : 'Historical prices could not load.'); }
      });
    }).catch((reason) => {
      if (active) {
        setPrices(null);
        setTrend(null);
        setMarketError(reason instanceof Error ? reason.message : 'Mandi prices could not load.');
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [state, commodity, refreshKey]);

  useEffect(() => {
    const costValues = [expectedPrice, storageCost, transportCost, productionCost, otherExpenses];
    const valid = quantity > 0 && currentPrice !== '' && currentPrice >= 0 && storageDays !== '' && storageDays >= 0 && costValues.every((value) => value !== '' && Number.isFinite(value) && value >= 0);
    if (!valid) { setProfit(null); return; }
    let active = true;
    setProfitError('');
    calculateProfit({ crop: commodity, quantity, current_price: currentPrice, expected_selling_price: Number(expectedPrice), transport_cost: Number(transportCost), storage_cost: Number(storageCost), storage_duration_days: Number(storageDays), production_cost: Number(productionCost), other_expenses: Number(otherExpenses) })
      .then((result) => { if (active) setProfit(result); }).catch((reason) => { if (active) { setProfit(null); setProfitError(reason instanceof Error ? reason.message : 'Profit calculation failed.'); } });
    return () => { active = false; };
  }, [commodity, quantity, currentPrice, expectedPrice, storageCost, transportCost, productionCost, otherExpenses, storageDays]);

  useEffect(() => {
    const costValues = [expectedPrice, storageCost, transportCost, productionCost, otherExpenses];
    const invalidScore = [readiness, demand].some((value) => value !== '' && (!Number.isFinite(value) || value < 0 || value > 100));
    if (invalidScore) { setDecision(null); setDecisionError('Crop readiness and demand estimates must be between 0 and 100%.'); return; }
    const valid = rows.length > 0 && quantity > 0 && currentPrice !== '' && currentPrice >= 0 && storageDays !== '' && storageDays >= 0 && costValues.every((value) => value !== '' && Number.isFinite(value) && value >= 0);
    if (!valid) { setDecision(null); setDecisionError(''); return; }
    let active = true;
    setDecisionError('');
    getDecision({
      crop_readiness_score: readiness === '' ? null : readiness,
      current_price: Number(currentPrice),
      price_trend: trend?.trend_available && trend.price_unit === '₹/kg' ? trend.trend_percent : null,
      demand_level: demand === '' ? null : demand,
      rainfall_risk: weather[0]?.rainfall_probability ?? null,
      storage_cost: Number(storageCost),
      storage_availability: storageSites[0] ? storageSites[0].available_capacity / Math.max(storageSites[0].capacity, 1) * 100 : null,
      quantity, transport_cost: Number(transportCost), production_cost: Number(productionCost), other_expenses: Number(otherExpenses),
      expected_future_price: Number(expectedPrice), storage_duration_days: Number(storageDays),
      input_sources: { current_price: currentPriceSource, price_trend: trend?.trend_available && trend.price_unit === '₹/kg' ? trend.data_source : 'MISSING: source unit is not confirmed as ₹/kg', expected_future_price: 'farmer estimate', demand_level: demand === '' ? 'MISSING' : 'farmer estimate', rainfall_risk: weather[0]?.data_source ?? 'MISSING', crop_readiness_score: readiness === '' ? 'MISSING' : 'farmer estimate', storage_availability: storageSites[0]?.data_source ?? 'MISSING', costs: 'farmer input', storage_duration_days: 'farmer input' },
      crop: commodity, location: state,
    }).then((result) => { if (active) setDecision(result); }).catch((reason) => { if (active) { setDecision(null); setDecisionError(reason instanceof Error ? reason.message : 'Decision analysis failed.'); } });
    return () => { active = false; };
  }, [rows.length, state, commodity, trend, weather, storageSites, quantity, currentPrice, currentPriceSource, expectedPrice, storageCost, transportCost, productionCost, otherExpenses, storageDays, readiness, demand]);

  const chartData = (trend?.observations ?? []).slice(0, 30).slice().reverse().map((row: any) => ({ ...row, price: row.price ?? row.modal_price }));
  const formatPrice = (value: unknown) => value == null || value === '' ? '—' : `₹${typeof value === 'number' ? value.toLocaleString('en-IN') : value}`;

  return (
    <div className="page-shell">
      <div className="card chart-card">
        <h3 className="section-title">{translate(language, 'nav.market')}</h3>
        <div className="form-grid mandi-selectors">
          <div className="field"><label htmlFor="mandi-state">State</label><select id="mandi-state" value={state} onChange={(event) => { setState(event.target.value); setRefreshKey(0); }} disabled={optionsLoading || !options.states.length}><option value={state}>{state}</option>{options.states.filter((item) => item !== state).map((item) => <option key={item} value={item}>{item}</option>)}</select></div>
          <div className="field"><label htmlFor="mandi-commodity">Commodity</label><select id="mandi-commodity" value={commodity} onChange={(event) => { setCommodity(event.target.value); setRefreshKey(0); }} disabled={optionsLoading || !options.commodities.length}><option value={commodity}>{commodity}{hasCommodityOption ? '' : ' (not in current options list)'}</option>{options.commodities.filter((item) => item !== commodity).map((item) => <option key={item} value={item}>{item}</option>)}</select></div>
        </div>
        {optionsError && <p className="muted" role="alert">{optionsError} <button className="ghost-btn" type="button" onClick={() => setOptionsRetry((value) => value + 1)}>Retry choices</button></p>}
        {!hasCommodityOption && !optionsLoading && !optionsError && <p className="muted">The provider’s current commodity list does not include “{commodity}”; the price request will show whether records are available for this selection.</p>}
        {loading ? <LoadingSkeleton /> : marketError ? <div className="market-state" role="alert"><p>{marketError}</p><button className="primary-btn" type="button" onClick={() => setRefreshKey((key) => key + 1)}>Retry mandi prices</button></div> : !rows.length ? <div className="market-state"><EmptyState message={`No mandi records were returned for ${commodity} in ${state}.`} /><button className="secondary-btn" type="button" onClick={() => setRefreshKey((key) => key + 1)}>Retry search</button></div> : <>
          {prices?.freshness === 'stale' && <div className="market-freshness-warning" role="alert"><strong>Stale Data</strong><span>{prices.freshness_message} Prices may no longer reflect current mandi conditions.</span></div>}
          {prices?.freshness === 'unknown' && <div className="market-freshness-warning" role="status"><strong>Freshness unknown</strong><span>{prices.freshness_message}</span></div>}
          <div className="muted">{prices?.data_source} · latest arrival {prices?.latest_arrival_date ?? 'date unavailable'} · source fetched {prices?.source_fetched_at ?? 'not provided'} · retrieved {prices?.retrieved_at}{prices?.cached ? ` · cached ${prices.cache_age_seconds}s` : ''}</div>
          <div className="muted">{prices?.unit_status}</div>
          {trendError && <p className="muted" role="alert">Historical trend unavailable: {trendError}</p>}
          {!trend?.trend_available && <div className="muted">{trend?.message ?? 'Insufficient dated records for a trend estimate.'}</div>}
          {trend?.forecast_available && <div className="muted">Estimated future source-price range: {formatPrice(trend.forecast_range.lower)}–{formatPrice(trend.forecast_range.upper)} · {trend.forecast_method} · unit not specified by provider</div>}
          {chartData.length > 0 && <div style={{ height: 260 }}><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" stroke="var(--line)" /><XAxis dataKey="date" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} /><Tooltip /><Line type="monotone" dataKey="price" name="Source modal price (unit unspecified)" stroke="var(--agri-gold)" strokeWidth={3} dot={{ r: 4 }} /></LineChart></ResponsiveContainer></div>}
          <div className="market-records-scroll"><table className="market-record-table"><caption>{rows.length} source records · original values are preserved; conversion appears only where the provider supplies a recognized unit</caption><thead><tr><th>Arrival date</th><th>State</th><th>District</th><th>Market</th><th>Commodity / variety</th><th>Source unit</th><th>Min source price</th><th>Max source price</th><th>Modal source price</th><th>Converted modal (₹/kg when confirmed)</th><th>Source update</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.id ?? `${row.market}-${row.arrival_date}-${index}`}><td>{row.arrival_date || 'Not reported'}</td><td>{row.state || state}</td><td>{row.district || 'Not reported'}</td><td>{row.market || 'Not reported'}</td><td>{row.commodity || commodity}{row.variety ? ` · ${row.variety}` : ''}{row.grade ? ` · ${row.grade}` : ''}</td><td>{row.source_price_unit || 'Not provided by API'}</td><td>{formatPrice(row.min_price)}</td><td>{formatPrice(row.max_price)}</td><td>{formatPrice(row.modal_price)}</td><td>{row.converted_modal_price == null ? 'Not converted' : formatPrice(row.converted_modal_price)}{row.price_compatible && row.converted_modal_price != null && <button type="button" className="ghost-btn" onClick={() => { setCurrentPrice(Number(row.converted_modal_price)); setCurrentPriceSource(`Mandi Price API · ${row.source_price_unit}`); }}>Use in calculator</button>}</td><td>{row.fetched_at || 'Not provided'}</td></tr>)}</tbody></table></div>
        </>}
      </div>

      <div className="grid-2">
        <div className="card metric-card">
          <h3 className="section-title">{translate(language, 'market.profit')}</h3>
          <p className="muted">Mandi prices are not copied into this calculator because the provider response does not specify their unit. Enter a verified selling price in ₹/kg to keep the calculation compatible with the quantity in kg.</p>
          <div className="form-grid">
            <div className="field"><label>Crop</label><input value={commodity} readOnly /></div>
            <div className="field"><label>Quantity (kg)</label><input type="number" min="0.01" step="any" value={quantity || ''} onChange={(event) => setQuantity(Number(event.target.value))} /></div>
            <div className="field"><label>Current price (₹/kg; {currentPriceSource})</label><input type="number" min="0" step="any" value={currentPrice} onChange={(event) => { setCurrentPrice(event.target.value === '' ? '' : Number(event.target.value)); setCurrentPriceSource('Farmer entered'); }} /></div>
            <div className="field"><label>Expected selling price (₹/kg)</label><input type="number" min="0" step="any" value={expectedPrice || ''} onChange={(event) => setExpectedPrice(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Production cost (₹ total)</label><input type="number" min="0" step="any" value={productionCost} onChange={(event) => setProductionCost(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Transport cost (₹ total)</label><input type="number" min="0" step="any" value={transportCost} onChange={(event) => setTransportCost(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Storage cost (₹ per day)</label><input type="number" min="0" step="any" value={storageCost} onChange={(event) => setStorageCost(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Storage duration (days)</label><input type="number" min="0" step="any" value={storageDays} onChange={(event) => setStorageDays(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Other expenses (₹ total)</label><input type="number" min="0" step="any" value={otherExpenses} onChange={(event) => setOtherExpenses(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Crop readiness (%)</label><input type="number" min="0" max="100" value={readiness} onChange={(event) => setReadiness(event.target.value === '' ? '' : Number(event.target.value))} /></div>
            <div className="field"><label>Demand estimate (%)</label><input type="number" min="0" max="100" value={demand} onChange={(event) => setDemand(event.target.value === '' ? '' : Number(event.target.value))} /></div>
          </div>
          {quantity < 0 || (currentPrice !== '' && currentPrice < 0) || [expectedPrice, storageCost, transportCost, productionCost, otherExpenses, storageDays].some((value) => value !== '' && (!Number.isFinite(value) || value < 0)) ? <p role="alert" className="muted">Enter finite, nonnegative prices and costs, a positive quantity, and a nonnegative storage duration.</p> : null}
          {profitError && <p role="alert" className="muted">{profitError}</p>}
          {profit && <div className="report-row" style={{ marginTop: 18 }}><div className="small-stat"><div className="muted">Store revenue estimate</div><strong>₹{profit.revenue.toFixed(0)}</strong></div><div className="small-stat"><div className="muted">Store expenses estimate</div><strong>₹{profit.expenses.toFixed(0)}</strong></div><div className="small-stat"><div className="muted">Store profit / loss estimate</div><strong>₹{profit.net_profit.toFixed(0)}</strong></div><div className="small-stat"><div className="muted">Store profit %</div><strong>{profit.profit_percentage.toFixed(1)}%</strong></div></div>}
        </div>
        <div className="card metric-card">
          <h3 className="section-title">Sell vs Store Simulator</h3>
          <div className="report-row"><div className="small-stat"><div className="muted">Sell now</div><strong>{profit ? `₹${profit.sell_now_profit.toFixed(0)}` : '—'}</strong></div><div className="small-stat"><div className="muted">Store {storageDays} days</div><strong>{profit ? `₹${profit.store_profit.toFixed(0)}` : '—'}</strong></div></div>
          {decision && <div style={{ marginTop: 18 }}><div className={`decision-badge ${decision.recommendation.toLowerCase()}`}>{decision.recommendation} {decision.status === 'insufficient_data' ? '· INCOMPLETE INPUTS' : ''}</div>{decision.status !== 'insufficient_data' && <div className="muted" style={{ marginTop: 8 }}>Confidence: {decision.confidence.toFixed(0)}%</div>}{decision.missing_inputs?.length > 0 && <div className="muted">Missing: {decision.missing_inputs.join(', ')}</div>}<div className="muted">{decision.data_source} · {decision.data_date ?? 'date unavailable'}</div><ul className="reason-list">{decision.reasons.map((reason: string) => <li key={reason}><span className="check">✓</span>{reason}</li>)}</ul></div>}
          {decisionError && <p role="alert" className="muted">{decisionError}</p>}
        </div>
      </div>
    </div>
  );
}
function ProfilePage({ user, onUserUpdated }: {
  user: { id: number; name: string; email: string } | null;
  onUserUpdated: (user: { id: number; name: string; email: string }) => void;
}) {
  const [name, setName] = useState(authenticatedDisplayName(user?.name));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setSaved(false);
    if (!name.trim()) {
      setError('Enter a name for your account.');
      return;
    }
    setLoading(true);
    try {
      const updated = await updateAuthProfile(name);
      onUserUpdated(updated);
      setName(authenticatedDisplayName(updated.name));
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Profile could not be updated. Please retry.');
    } finally {
      setLoading(false);
    }
  };

  return <div className="page-shell"><section className="card metric-card profile-card">
    <h2 className="section-title">Your profile</h2>
    <p className="muted">This name comes from your authenticated AgriSense account. Farm and crop records on the dashboard are still demonstration data.</p>
    <form onSubmit={submit}>
      <div className="field"><label htmlFor="profile-name">Name</label><input id="profile-name" autoComplete="name" maxLength={100} value={name} onChange={(event) => { setName(event.target.value); setSaved(false); }} /></div>
      <div className="field"><label htmlFor="profile-email">Email</label><input id="profile-email" value={user?.email ?? ''} readOnly /></div>
      {error && <p role="alert" className="auth-error">{error}</p>}
      {saved && <p role="status" className="muted">Profile name updated.</p>}
      <button className="primary-btn" type="submit" disabled={loading}>{loading ? 'Saving…' : 'Save name'}</button>
    </form>
  </section></div>;
}

function WeatherPage({ language }: { language: LanguageCode }) {
  const [weather, setWeather] = useState<Weather[]>([]);
  const [risk, setRisk] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const applyWeather = (data: Weather[]) => {
    setWeather(data);
    const probabilities = data.slice(0, 3).map((day) => day.rainfall_probability).filter((value): value is number => value != null);
    const rainfall = probabilities.length ? Math.max(...probabilities) : null;
    const current = data[0];
    const alerts = [] as Array<{ type: string; severity: string; message: string }>;
    if (rainfall != null && rainfall >= 70) alerts.push({ type: 'rain', severity: 'High', message: `Rain probability reaches ${rainfall}% in the next three forecast days.` });
    if (current?.current_temperature != null && current.current_temperature >= 35) alerts.push({ type: 'heat', severity: 'Medium', message: `Current temperature is ${current.current_temperature}°C.` });
    if (current?.wind_kmh != null && current.wind_kmh >= 35) alerts.push({ type: 'wind', severity: 'Medium', message: `Current wind speed is ${current.wind_kmh} km/h.` });
    setRisk({ alerts, data_source: current?.data_source, risk_level: rainfall == null ? 'UNKNOWN' : rainfall >= 75 ? 'HIGH' : rainfall >= 50 ? 'MODERATE' : 'LOW' });
    setError('');
  };

  useEffect(() => {
    let active = true;
    getWeather().then((data) => { if (active) applyWeather(data); }).catch((reason) => active && setError(reason instanceof Error ? reason.message : 'Weather could not load.')).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (!weather.length) return <div className="page-shell"><div className="card metric-card"><p role="alert">{error || 'No weather data is available.'}</p><button className="primary-btn" onClick={() => { setLoading(true); getWeather().then(applyWeather).catch((e) => setError(e instanceof Error ? e.message : 'Weather could not load.')).finally(() => setLoading(false)); }}>Retry</button></div></div>;

  const current = weather[0];
  const riskLevel = risk?.risk_level ?? (current.rainfall_probability == null ? 'UNKNOWN' : current.rainfall_probability > 75 ? 'HIGH' : current.rainfall_probability > 50 ? 'MODERATE' : 'LOW');

  return (
    <div className="page-shell">
      <div className="card hero-card">
        <div className="split">
          <div>
            <h3 className="section-title">{translate(language, 'nav.weather')}</h3>
            <div className="big-text">{current.current_temperature == null ? '—' : `${current.current_temperature}°C`}</div>
            <div className="muted">{current.weather_condition}</div>
            <div className="muted">{current.location} · {current.data_source} · {current.observation_time ?? current.forecast_time ?? 'time unavailable'} · {current.data_status ?? 'status unknown'}</div>
          </div>
          <div className={`decision-badge ${riskLevel === 'HIGH' || riskLevel === 'UNKNOWN' ? 'wait' : riskLevel === 'MODERATE' ? 'store' : 'sell'}`}>
            {riskLevel} RISK
          </div>
        </div>
        <div className="weather-grid">
          <div className="weather-box"><div className="muted">Rain probability today</div><strong>{current.rainfall_probability ?? '—'}%</strong></div>
          <div className="weather-box"><div className="muted">Humidity now</div><strong>{current.current_humidity ?? '—'}%</strong></div>
          <div className="weather-box"><div className="muted">Wind now</div><strong>{current.wind_kmh == null ? '—' : `${current.wind_kmh} km/h`}</strong></div>
        </div>
        {risk?.alerts?.map((alert: { type: string; severity: string; message: string }) => <p className="muted" key={alert.type}>{alert.severity}: {alert.message} · {risk.data_source}</p>)}
      </div>

      <div className="card chart-card">
        <h3 className="section-title">7-day forecast · max temperature by day</h3>
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={weather}>
              <defs>
                <linearGradient id="rainGradient" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="var(--leaf)" stopOpacity={0.7} />
                  <stop offset="95%" stopColor="var(--leaf)" stopOpacity={0.1} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Area type="monotone" dataKey="temperature" name="Maximum temperature °C" stroke="var(--agri-gold)" fill="url(#rainGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="weather-grid">
          {weather.map((day) => <div className="weather-box" key={day.date}>
            <strong>{day.date}</strong><div>{day.weather_condition}</div>
            <div className="inline-stat"><span>High / low</span><span>{day.temperature ?? '—'}° / {day.temperature_min ?? '—'}°C</span></div>
            <div className="inline-stat"><span>Rain chance</span><span>{day.rainfall_probability ?? '—'}%</span></div>
            <div className="inline-stat"><span>Rain</span><span>{day.rainfall_mm ?? '—'} mm</span></div>
          </div>)}
        </div>
      </div>
    </div>
  );
}

function StoragePage({ language }: { language: LanguageCode }) {
  const [storage, setStorage] = useState<StorageItem[]>([]);
  const [selectedType, setSelectedType] = useState('All');
  const [locationQuery, setLocationQuery] = useState('');
  const [sortBy, setSortBy] = useState<'distance' | 'price' | 'rating'>('distance');
  const [selectedId, setSelectedId] = useState<number | null>(1);
  const [details, setDetails] = useState<StorageItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState('');
  const [error, setError] = useState('');

  const loadStorage = async () => {
    setLoading(true);
    setError('');
    try {
      const items = await getStorage();
      setStorage(items);
      setSelectedId((current) => items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Storage facilities could not be loaded. Check your connection and retry.');
    } finally {
      setLoading(false);
    }
  };

  const loadDetails = async (id: number) => {
    setDetailsLoading(true);
    setDetailsError('');
    setDetails(null);
    try {
      setDetails(await getStorageDetails(id));
    } catch (reason) {
      setDetailsError(reason instanceof Error ? reason.message : 'Facility details could not be loaded. Retry to try again.');
    } finally {
      setDetailsLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    getStorage().then((items) => {
      if (!active) return;
      setStorage(items);
      setSelectedId((current) => items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
    }).catch((reason) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Storage facilities could not be loaded. Check your connection and retry.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const filtered = useMemo(() => {
    return filterAndSortStorage(storage, locationQuery, selectedType, sortBy);
  }, [storage, locationQuery, selectedType, sortBy]);
  const listState = storageListState(loading, error, filtered.length);

  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0];

  return (
    <div className="page-shell">
      <div className="card metric-card">
        <div className="split storage-heading">
          <h3 className="section-title">{translate(language, 'nav.storage')}</h3>
          <span className="pill medium">SAMPLE LISTINGS</span>
        </div>
        <div className="storage-sample-notice" role="note"><strong>SAMPLE DATA:</strong> Facility information is not verified. Distance, total and available capacity, daily price, and rating are sample values; availability is not live.</div>
        <div className="storage-toolbar">
          <label className="storage-location-search" htmlFor="storage-location-search">Search by location
            <input id="storage-location-search" className="select" type="search" value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="e.g. Bengaluru or Devanahalli" />
          </label>
          <div className="controls storage-filter-controls">
            <select className="select" value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
              <option value="All">All</option>
              <option value="Cold Storage">Cold Storage</option>
              <option value="Warehouse">Warehouse</option>
              <option value="Dry Storage">Dry Storage</option>
            </select>
            <select className="select" value={sortBy} onChange={(e) => setSortBy(e.target.value as 'distance' | 'price' | 'rating')}>
              <option value="distance">Distance</option>
              <option value="price">Price</option>
              <option value="rating">Rating</option>
            </select>
          </div>
        </div>

        <div className="grid-2" style={{ marginTop: 18 }}>
          <div className="storage-list">
            {listState === 'loading' ? [0, 1, 2].map((item) => <div className="storage-skeleton" key={item} role="status" aria-label="Loading storage facilities"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>)
              : listState === 'error' ? <div className="storage-state error-state" role="alert"><strong>Storage facilities could not be loaded</strong><p>{error}</p><button className="primary-btn" type="button" onClick={() => void loadStorage()}>Retry loading facilities</button></div>
                : listState === 'results' ? filtered.map((item) => (
                  <article key={item.id} className={`storage-item${selected?.id === item.id ? ' selected' : ''}`}>
                    <button type="button" className="storage-select" aria-pressed={selected?.id === item.id} onClick={() => { setSelectedId(item.id); setDetails(null); setDetailsError(''); }}>
                      <div className="storage-top"><strong>{item.name}</strong><span className="pill low">{item.storage_type} · {item.data_source ?? 'DEMO DATA'}</span></div>
                      <div className="muted">{item.location}</div>
                      <div className="inline-stat"><span>Capacity · SAMPLE</span><span>{item.available_capacity}/{item.capacity} kg available</span></div>
                      <div className="inline-stat"><span>Distance · SAMPLE</span><span>{item.distance} km</span></div>
                      <div className="inline-stat"><span>Price · SAMPLE</span><span>₹{item.price_per_day}/day</span></div>
                      <div className="inline-stat"><span>Rating · SAMPLE</span><span>★ {item.rating}</span></div>
                    </button>
                    {item.directions_url ? <a className="storage-directions" href={item.directions_url} target="_blank" rel="noopener noreferrer">Get Directions <span aria-hidden="true">↗</span></a> : <span className="muted storage-no-directions">Directions unavailable for this facility.</span>}
                  </article>
                )) : <div className="storage-state"><EmptyState message={storage.length ? 'No facilities match this location and storage type.' : 'No storage facilities are available.'} />{storage.length > 0 && <button className="ghost-btn" type="button" onClick={() => { setLocationQuery(''); setSelectedType('All'); }}>Clear location and type filters</button>}</div>}
          </div>

          {selected && (
            <div className="card metric-card storage-detail-panel">
              <div className="storage-detail-heading"><h3 className="section-title">Selected storage</h3><span className="pill low">DEMO DATA</span></div>
              <div className="big-text" style={{ fontSize: '1.7rem' }}>{selected.name}</div>
              <div className="muted">{selected.location} · sample location</div>
              <div className="report-row" style={{ marginTop: 18 }}>
                <div className="small-stat"><div className="muted">Distance · SAMPLE</div><strong>{selected.distance} km</strong></div>
                <div className="small-stat"><div className="muted">Price/day · SAMPLE</div><strong>₹{selected.price_per_day}</strong></div>
                <div className="small-stat"><div className="muted">Rating · SAMPLE</div><strong>★ {selected.rating}</strong></div>
                <div className="small-stat"><div className="muted">Available · SAMPLE</div><strong>{selected.available_capacity}/{selected.capacity} kg</strong></div>
              </div>
              <div className="action-row">
                <button className="primary-btn" type="button" disabled={detailsLoading} onClick={() => void loadDetails(selected.id)}>{detailsLoading ? 'Loading details…' : 'View Details'}</button>
              </div>
              {detailsLoading && <p className="storage-detail-message" role="status">Loading facility details…</p>}
              {detailsError && <div className="storage-detail-error" role="alert"><p>{detailsError}</p><button className="secondary-btn" type="button" disabled={detailsLoading} onClick={() => void loadDetails(selected.id)}>Retry details</button></div>}
              {details && details.id === selected.id && <div className="storage-detail-result" role="status"><strong>Facility details loaded</strong><p>{details.name} · {details.storage_type} · SAMPLE DATA</p><p>Available capacity: {details.available_capacity}/{details.capacity} kg · SAMPLE DATA</p></div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CalendarPage({ language }: { language: LanguageCode }) {
  const [tasks, setTasks] = useState<CalendarTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [todayString] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  });
  const emptyTask = { title: '', crop: 'Tomato', priority: 'High', date: todayString };
  const [newTask, setNewTask] = useState(emptyTask);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    try { setTasks(await getCalendar()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Calendar could not load.'); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let active = true;
    getCalendar().then((data) => { if (active) { setTasks(data); setError(''); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Calendar could not load.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const handleAddTask = async () => {
    const parsedDate = new Date(`${newTask.date}T00:00:00`);
    if (!newTask.title.trim() || !newTask.crop.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(newTask.date) || Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== newTask.date) { setError('Enter a task title, crop, and valid date.'); return; }
    setError('');
    setSaving(true);
    try {
      if (editingId != null) {
        const existing = tasks.find((item) => item.id === editingId);
        const task = { ...newTask, id: editingId, completed: existing?.completed ?? false, data_source: existing?.data_source } as CalendarTask;
        await updateTask(task); setTasks((prev) => prev.map((item) => item.id === editingId ? task : item));
      } else {
        const created = await addTask({ ...newTask, completed: false } as any); setTasks((prev) => [...prev, created]);
      }
      setEditingId(null); setNewTask(emptyTask);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save task.'); }
    finally { setSaving(false); }
  };

  const toggleTask = async (task: CalendarTask) => {
    try { await updateTask({ ...task, completed: !task.completed }); setTasks((prev) => prev.map((item) => item.id === task.id ? { ...item, completed: !item.completed } : item)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not update task.'); }
  };

  return (
    <div className="page-shell">
      <div className="card metric-card">
        <h3 className="section-title">{translate(language, 'calendar.add')}</h3>
        <div className="form-grid">
          <div className="field"><label>Title</label><input required maxLength={120} value={newTask.title} onChange={(e) => setNewTask({ ...newTask, title: e.target.value })} /></div>
          <div className="field"><label>Crop</label><select value={newTask.crop} onChange={(e) => setNewTask({ ...newTask, crop: e.target.value })}><option>Tomato</option><option>Rice</option><option>Cotton</option></select></div>
          <div className="field"><label>Date</label><input required type="date" value={newTask.date} onChange={(e) => setNewTask({ ...newTask, date: e.target.value })} /></div>
          <div className="field"><label>Priority</label><select value={newTask.priority} onChange={(e) => setNewTask({ ...newTask, priority: e.target.value })}><option>High</option><option>Medium</option><option>Low</option></select></div>
        </div>
        <div className="action-row"><button className="primary-btn" onClick={handleAddTask} disabled={loading || saving}>{saving ? 'Saving…' : editingId != null ? 'Save changes' : 'Add task'}</button>{editingId != null && <button className="secondary-btn" onClick={() => { setEditingId(null); setNewTask(emptyTask); }}>Cancel</button>}</div>
        {error && <p role="alert" className="muted">{error}</p>}
      </div>

      <div className="card list-card">
        <h3 className="section-title">Upcoming tasks</h3>
          <div className="task-list">
            {loading ? <LoadingSkeleton /> : error ? <div role="alert"><p>{error}</p><button className="secondary-btn" type="button" onClick={() => void loadTasks()}>Retry loading calendar</button></div> : !tasks.length ? <EmptyState message="No calendar tasks yet." /> : null}
          {tasks.map((task) => (
            <div key={task.id} className="task-item">
              <div className="notification-top">
                <strong>{task.title}</strong>
                <span className={`pill ${task.priority === 'High' ? 'high' : task.priority === 'Medium' ? 'medium' : 'low'}`}>{task.priority}</span>
              </div>
              <div className="muted">{task.crop} • {task.date} • {task.completed ? 'Completed' : 'Pending'} · {task.data_source ?? 'DEMO DATA'}</div>
              {task.data_source !== 'DEMO DATA' && <div className="action-row">
                <button className="ghost-btn" onClick={() => toggleTask(task)}>{task.completed ? 'Mark pending' : 'Complete task'}</button>
                <button className="secondary-btn" onClick={() => { setEditingId(task.id); setNewTask({ title: task.title, crop: task.crop, priority: task.priority, date: task.date }); }}>Edit</button>
                <button className="secondary-btn" onClick={() => deleteTask(task.id).then(() => setTasks((prev) => prev.filter((item) => item.id !== task.id))).catch((reason) => setError(reason.message))}>Delete</button>
              </div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function NewsPage({ language }: { language: LanguageCode }) {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [query, setQuery] = useState('');
  const [languageFilter, setLanguageFilter] = useState('en');
  const [country, setCountry] = useState('');
  const [sortBy, setSortBy] = useState<'publishedAt' | 'relevance'>('publishedAt');
  const [resultQuery, setResultQuery] = useState('');
  const [lastSearch, setLastSearch] = useState<{ query: string; lang: string; country: string; sortBy: 'publishedAt' | 'relevance' } | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const requestInFlight = useRef(false);

  const loadNews = async (search: string, filters: { lang: string; country: string; sortBy: 'publishedAt' | 'relevance' }) => {
    const trimmed = search.trim().replace(/\s+/g, ' ');
    if (!trimmed) { setError('Enter a topic to search Agri News.'); return; }
    if (trimmed.length > 200) { setError('Search terms must be 200 characters or fewer.'); return; }
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setLastSearch({ query: trimmed, ...filters });
    setLoading(true);
    setError('');
    setHasSearched(true);
    try {
      const results = await getNews(trimmed, filters);
      setNews(results);
      setResultQuery(trimmed);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Agri News could not be loaded. Check your connection and retry.');
    } finally {
      requestInFlight.current = false;
      setLoading(false);
    }
  };

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadNews(query, { lang: languageFilter, country, sortBy });
  };
  const retrySearch = () => { if (lastSearch) void loadNews(lastSearch.query, lastSearch); };
  const suggestedSearches = ['agriculture India', 'crop disease', 'monsoon farming', 'wheat prices', 'irrigation', 'organic farming'];

  return (
    <div className="page-shell agri-news-page">
      <section className="news-hero card">
        <div className="news-hero-copy">
          <span className="news-eyebrow"><Newspaper size={16} /> AGRISENSE · NEWS</span>
          <h2>{translate(language, 'nav.news')}</h2>
          <p>Find agriculture stories from news publishers around the world.</p>
        </div>
        <div className="news-hero-mark" aria-hidden="true"><Newspaper size={34} /></div>
      </section>

      <section className="card news-search-panel" aria-label="Search news">
        <form className="news-search-form" onSubmit={submitSearch}>
          <label className="news-search-box">
            <Search size={19} aria-hidden="true" />
            <input value={query} maxLength={200} onChange={(event) => setQuery(event.target.value)} placeholder="Search agriculture news…" aria-label="Search agriculture news" />
          </label>
          <button className="primary-btn news-search-button" type="submit" disabled={loading}>
            <Search size={17} /> {loading ? 'Searching…' : 'Search'}
          </button>
          <div className="news-filters">
            <label>Language <select className="select" value={languageFilter} onChange={(event) => setLanguageFilter(event.target.value)} disabled={loading}>
              <option value="en">English</option><option value="hi">Hindi</option><option value="ta">Tamil</option><option value="bn">Bengali</option><option value="es">Spanish</option><option value="fr">French</option>
            </select></label>
            <label>Country <select className="select" value={country} onChange={(event) => setCountry(event.target.value)} disabled={loading}>
              <option value="">Any country</option><option value="in">India</option><option value="us">United States</option><option value="gb">United Kingdom</option><option value="au">Australia</option><option value="ca">Canada</option>
            </select></label>
            <label>Sort <select className="select" value={sortBy} onChange={(event) => setSortBy(event.target.value as 'publishedAt' | 'relevance')} disabled={loading}>
              <option value="publishedAt">Newest</option><option value="relevance">Most relevant</option>
            </select></label>
          </div>
        </form>
        <div className="news-suggestions"><span>Try:</span>{suggestedSearches.map((suggestion) => <button type="button" key={suggestion} onClick={() => { setQuery(suggestion); void loadNews(suggestion, { lang: languageFilter, country, sortBy }); }} disabled={loading}>{suggestion}</button>)}</div>
        <p className="news-search-note">English is the default. Choose a country to narrow coverage; otherwise results are worldwide. Free GNews access may be delayed and includes up to 10 articles per search.</p>
      </section>

      {error && <div className="news-error" role="alert"><div><strong>Search could not be completed</strong><p>{error}</p>{news.length > 0 && <span>Previous results for “{resultQuery}” are still shown below.</span>}</div>{lastSearch && <button className="secondary-btn" type="button" onClick={retrySearch} disabled={loading}>Retry search</button>}</div>}

      {loading && <div className="news-results-grid" aria-live="polite" aria-busy="true">{[0, 1, 2].map((item) => <div className="news-card news-card-skeleton" key={item}><div className="skeleton news-skeleton-image" /><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>)}</div>}

      {!loading && !hasSearched && <section className="news-intro-empty"><div className="news-intro-icon"><Search size={24} /></div><h3>Search the latest agriculture coverage</h3><p>Enter a topic or choose a suggested search to get started.</p></section>}

      {!loading && hasSearched && !error && news.length === 0 && <section className="news-intro-empty"><div className="news-intro-icon"><Newspaper size={24} /></div><h3>No matching articles found</h3><p>Try broader keywords, another language, or remove the country filter.</p><div className="news-suggestions">{suggestedSearches.slice(0, 3).map((suggestion) => <button type="button" key={suggestion} onClick={() => { setQuery(suggestion); void loadNews(suggestion, { lang: languageFilter, country, sortBy }); }}>{suggestion}</button>)}</div></section>}

      {news.length > 0 && <section className="news-results-section" aria-live="polite">
        <div className="news-results-heading"><div><span className="news-eyebrow">SEARCH RESULTS</span><h3>{news.length} {news.length === 1 ? 'article' : 'articles'} for “{resultQuery}”</h3></div><span className="news-provider-label"><span className="news-live-dot" /> GNews results</span></div>
        <div className="news-results-grid">{news.map((item) => <NewsArticleCard key={item.id} item={item} />)}</div>
      </section>}
    </div>
  );
}

function NewsArticleCard({ item }: { item: NewsItem }) {
  const [imageFailed, setImageFailed] = useState(false);
  const articleDate = item.date ? new Date(item.date) : null;
  const dateLabel = articleDate && !Number.isNaN(articleDate.getTime())
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(articleDate)
    : item.date;
  return <article className="news-card">
    {item.image && !imageFailed ? <img className="news-card-image" src={item.image} alt="" loading="lazy" onError={() => setImageFailed(true)} /> : <div className="news-card-image news-card-image-empty" aria-hidden="true"><Newspaper size={30} /></div>}
    <div className="news-card-content">
      <div className="news-card-meta"><span>{item.source || 'News source unavailable'}</span>{dateLabel && <time dateTime={item.date || undefined}>{dateLabel}</time>}</div>
      <h4>{item.headline || 'Article title unavailable'}</h4>
      {item.summary && <p>{item.summary}</p>}
      {item.url && <a className="news-read-link" href={item.url} target="_blank" rel="noopener noreferrer">Read full article <ArrowUpRight size={16} /></a>}
    </div>
  </article>;
}

function CropDoctorPage({ language }: { language: LanguageCode }) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [diseaseLoading, setDiseaseLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [diseaseAnalysis, setDiseaseAnalysis] = useState<any>(null);
  const [error, setError] = useState('');
  const [diseaseError, setDiseaseError] = useState('');
  const [organ, setOrgan] = useState('leaf');
  const [progressStep, setProgressStep] = useState(0);
  const [diseaseProgressStep, setDiseaseProgressStep] = useState(0);
  const analysisAbort = useRef<AbortController | null>(null);
  const diseaseAbort = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const identifiedSpecies = analysis?.identified_species;
  const commonPlantName = identifiedSpecies?.common_names?.[0];
  const scientificPlantName = identifiedSpecies?.scientific_name;
  const plantName = commonPlantName || scientificPlantName;
  const progressLabels = [
    'Image selected; client type and size checks passed (server checks file contents)',
    'Preparing image request',
    'Sending to the AgriSense backend; server forwards only after validation',
    'Request started; waiting for the backend and Pl@ntNet response',
    'Processing species candidates and their scores',
    'Preparing results',
  ];

  const cancelRequests = () => {
    analysisAbort.current?.abort();
    diseaseAbort.current?.abort();
    analysisAbort.current = null;
    diseaseAbort.current = null;
    setLoading(false);
    setDiseaseLoading(false);
  };

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;
    cancelRequests();
    setAnalysis(null);
    setDiseaseAnalysis(null);
    setDiseaseError('');
    setProgressStep(0);
    setDiseaseProgressStep(0);
    const total = files.reduce((sum, file) => sum + file.size, 0);
    const validationError = files.length > 5 ? 'Choose at most 5 images of the same plant.'
      : files.some((file) => !['image/jpeg', 'image/png'].includes(file.type)) ? 'Upload JPEG or PNG images only.'
        : files.some((file) => file.size > 10 * 1024 * 1024) || total > 25 * 1024 * 1024 ? 'Each image must be 10 MB or smaller and combined images 25 MB or smaller.' : '';
    if (preview) URL.revokeObjectURL(preview);
    if (validationError) {
      setSelectedFiles([]);
      setPreview(null);
      setError(validationError);
      event.target.value = '';
      return;
    }
    setError('');
    setSelectedFiles(files);
    setPreview(URL.createObjectURL(files[0]));
    setProgressStep(1);
    event.target.value = '';
  };

  const analyze = async () => {
    if (!selectedFiles.length) { setError('Upload a plant image first.'); return; }
    analysisAbort.current?.abort();
    const controller = new AbortController();
    analysisAbort.current = controller;
    setLoading(true);
    setError('');
    setAnalysis(null);
    setProgressStep(2);
    try {
      setProgressStep(3);
      const result = await analyzeCrop(selectedFiles, '', organ, controller.signal, () => setProgressStep(4));
      if (controller.signal.aborted) return;
      setProgressStep(5);
      setAnalysis(result);
      setProgressStep(6);
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Plant identification failed. Please retry.');
    } finally {
      if (analysisAbort.current === controller) {
        analysisAbort.current = null;
        setLoading(false);
      }
    }
  };

  const screenDisease = async () => {
    if (!selectedFiles.length) { setDiseaseError('Upload a plant image first.'); return; }
    diseaseAbort.current?.abort();
    const controller = new AbortController();
    diseaseAbort.current = controller;
    setDiseaseLoading(true);
    setDiseaseError('');
    setDiseaseAnalysis(null);
    setDiseaseProgressStep(2);
    try {
      setDiseaseProgressStep(3);
      const result = await screenCropDisease(selectedFiles, organ, controller.signal, () => setDiseaseProgressStep(4));
      if (controller.signal.aborted) return;
      setDiseaseProgressStep(5);
      setDiseaseAnalysis(result);
      setDiseaseProgressStep(6);
    } catch (reason) {
      if (!controller.signal.aborted) setDiseaseError(reason instanceof Error ? reason.message : 'Disease screening failed. Please retry.');
    } finally {
      if (diseaseAbort.current === controller) {
        diseaseAbort.current = null;
        setDiseaseLoading(false);
      }
    }
  };

  const removeImage = () => {
    cancelRequests();
    analysisAbort.current = null;
    diseaseAbort.current = null;
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setSelectedFiles([]);
    setAnalysis(null);
    setDiseaseAnalysis(null);
    setError('');
    setDiseaseError('');
    setProgressStep(0);
    setDiseaseProgressStep(0);
    if (fileInput.current) fileInput.current.value = '';
  };

  useEffect(() => () => {
    analysisAbort.current?.abort();
    diseaseAbort.current?.abort();
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  return (
    <div className="page-shell">
      <div className="grid-2">
        <div className="card metric-card">
          <h3 className="section-title">{translate(language, 'nav.cropDoctor')}</h3>
          <div className="upload-box">
            {preview ? <img src={preview} alt="Uploaded plant preview" className="preview-image" /> : <div><FileImage size={36} color="var(--primary)" /><p>Select a sharp, well-lit photo showing one plant.</p></div>}
          </div>
          <div className="action-row">
            <label className="primary-btn" style={{ display: 'inline-block', cursor: 'pointer' }}>
              {selectedFiles.length ? 'Replace image' : 'Upload image'}
              <input ref={fileInput} type="file" accept="image/jpeg,image/png" multiple onChange={onFileChange} style={{ display: 'none' }} />
            </label>
            {preview && <button className="secondary-btn" onClick={removeImage}>Remove image{selectedFiles.length > 1 ? 's' : ''}</button>}
          </div>
          {selectedFiles.length > 1 && <p className="muted">{selectedFiles.length} images selected (up to 5).</p>}
          <div className="field"><label>Plant part shown</label><select value={organ} onChange={(e) => { cancelRequests(); setOrgan(e.target.value); setAnalysis(null); setDiseaseAnalysis(null); setError(''); setDiseaseError(''); setProgressStep(0); setDiseaseProgressStep(0); }}><option value="leaf">Leaf</option><option value="flower">Flower</option><option value="fruit">Fruit</option><option value="bark">Bark</option><option value="auto">Detect automatically</option></select></div>
          <p className="muted">Use a sharp, well-lit image of one plant. If you upload multiple photos, they should show the same plant. The selected plant part is sent with each image.</p>
          <div className="action-row"><button className="primary-btn" onClick={analyze} disabled={loading || diseaseLoading || !selectedFiles.length}>{loading ? 'Identifying species…' : 'Analyze crop'}</button></div>
          {loading && <AnalysisProgress step={progressStep} labels={progressLabels} />}
          {error && <div className="analysis-error" role="alert"><p>{error}</p><button className="ghost-btn" onClick={analyze} disabled={loading || !selectedFiles.length}>Retry identification</button></div>}
        </div>

        <div className="card metric-card">
          {loading ? <LoadingSkeleton /> : analysis ? (
            <>
              <h3 className="section-title">Plant identification results</h3>
              <div className="big-text" style={{ fontSize: '1.9rem' }}>{plantName || 'No plant species identified'}</div>
              <div className="decision-badge wait" style={{ marginTop: 12 }}>{plantName ? 'Plant species identified' : 'No plant species identified'}</div>
              {identifiedSpecies && <p className="muted">Pl@ntNet identification score: {identifiedSpecies.score_percent ?? 'Not provided'}{scientificPlantName && scientificPlantName !== plantName ? ` · ${scientificPlantName}` : ''}</p>}
              {analysis?.candidates?.length > 1 && <div className="reason-list"><strong>Other likely matches</strong>{analysis.candidates.slice(1).map((candidate: any, index: number) => <li key={`${candidate.name}-${index}`}>{candidate.name}{candidate.score_percent != null ? ` · ${(candidate.score_percent as number).toFixed(1)}%` : ''}</li>)}</div>}
              {!plantName && <p className="muted">No species candidates were returned. Try a sharp, well-lit image showing one plant.</p>}
              <p className="muted">Plant identification only; this result does not diagnose disease. Source: <a href="https://plantnet.org/" target="_blank" rel="noreferrer">Pl@ntNet</a>.</p>
              <div className="action-row"><button className="secondary-btn" onClick={screenDisease} disabled={loading || diseaseLoading || !selectedFiles.length}>{diseaseLoading ? 'Screening…' : 'Optional disease screening · uses 1 request'}</button></div>
              <p className="muted">Disease screening has limited species and condition coverage, consumes one additional daily request, and is not a diagnosis.</p>
              {diseaseLoading && <AnalysisProgress step={diseaseProgressStep} labels={progressLabels.slice(0, 4).concat(['Processing screening candidates', 'Preparing screening results'])} />}
              {diseaseError && <div className="analysis-error" role="alert"><p>{diseaseError}</p><button className="ghost-btn" onClick={screenDisease} disabled={diseaseLoading || !selectedFiles.length}>Retry screening</button></div>}
              {diseaseAnalysis && <div className="disease-screening-result"><strong>{diseaseAnalysis.status}</strong>{diseaseAnalysis.candidates.length ? <ul>{diseaseAnalysis.candidates.map((candidate: any) => <li key={candidate.eppo_code || candidate.description}>{candidate.description}{candidate.eppo_code ? ` (${candidate.eppo_code})` : ''}{candidate.score_percent != null ? ` · screening match score ${(candidate.score_percent as number).toFixed(1)}%` : ''}</li>)}</ul> : <p>No supported condition matched this image.</p>}<p className="muted">{diseaseAnalysis.disclaimer}</p></div>}
            </>
          ) : loading ? <AnalysisProgress step={progressStep} labels={progressLabels} /> : <EmptyState message="Upload a plant image to identify its likely species. Disease screening is a separate optional request." />}
        </div>
      </div>
      <div className="plantnet-attribution">
        <a href="https://my.plantnet.org/" target="_blank" rel="noreferrer" aria-label="Plant species identification powered by Pl@ntNet">
          <img src="https://my.plantnet.org/images/powered-by-plantnet-light.png" alt="Powered by Pl@ntNet" />
        </a>
        <span>The image-based plant species identification service used is based on the Pl@ntNet recognition API.</span>
      </div>
    </div>
  );
}

function AnalysisProgress({ step, labels }: { step: number; labels: string[] }) {
  const current = Math.max(1, Math.min(step, labels.length));
  return <section className="analysis-progress" aria-label="Image analysis progress" aria-live="polite">
    <div className="progress-indeterminate" aria-hidden="true"><span /></div>
    <p role="status">{step >= labels.length ? 'Analysis complete' : labels[current - 1]}</p>
    <ol>{labels.map((label, index) => <li key={label} className={index + 1 < current || step >= labels.length ? 'complete' : index + 1 === current ? 'current' : ''} aria-current={index + 1 === current && step < labels.length ? 'step' : undefined}>{label}</li>)}</ol>
  </section>;
}

function AssistantPage({ language }: { language: LanguageCode }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([
    { role: 'assistant', text: 'I can help you decide based on crop health, weather and market conditions.' },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [retryQuestion, setRetryQuestion] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [assistantStatus, setAssistantStatus] = useState<{ available: boolean; model: string; data_source: string } | null>(null);

  useEffect(() => { getAssistantStatus().then(setAssistantStatus).catch(() => setAssistantStatus({ available: false, model: 'unknown', data_source: 'DEMO / STATUS UNAVAILABLE' })); }, []);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, loading]);

  const sendQuestion = async (question: string, addUserMessage: boolean) => {
    if (!question.trim() || loading) return;
    if (addUserMessage) {
      setRetryQuestion(question);
      setMessages((prev) => [...prev, { role: 'user', text: question }]);
    }
    setLoading(true);
    setError('');
    try {
      const result = await askAssistant({ message: question, crop: 'Tomato', location: 'Bengaluru', language });
      setMessages((prev) => [...prev, { role: 'assistant', text: `${result.answer}${result.data_source ? `\n${result.data_source}` : ''}` }]);
      setInput('');
      setRetryQuestion('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Assistant request failed. Please retry.'); }
    finally { setLoading(false); }
  };
  const submit = () => sendQuestion(input, !retryQuestion || input.trim() !== retryQuestion.trim());
  const retry = () => sendQuestion(retryQuestion, false);

  return (
    <div className="page-shell assistant-page">
      <div className="card metric-card assistant-panel">
        <h3 className="section-title">{translate(language, 'assistant.title')}</h3>
        {assistantStatus && <p className="demo-pill">{assistantStatus.available ? `AI CONFIGURED · ${assistantStatus.model}` : `DEMO / AI UNAVAILABLE · ${assistantStatus.data_source}`}</p>}
        <p className="muted">Responses use available AgriSense data. Missing prices, weather, or diagnosis details are not inferred.</p>
        <div className="assistant-chat" role="log" aria-label="Assistant conversation" aria-live="polite">
          {messages.map((message, index) => (
            <div key={index} className={`chat-bubble ${message.role}`}>
              {message.role === 'assistant' ? <AssistantMarkdown content={message.text} /> : message.text}
            </div>
          ))}
          {loading && <div className="chat-bubble ai">Analyzing farm data...</div>}
          <div ref={chatEndRef} aria-hidden="true" />
        </div>
        {error && <div role="alert" className="muted"><AssistantErrorMessage message={error} /> <button className="ghost-btn" onClick={retry} disabled={loading || !retryQuestion}>Retry</button></div>}
        <div className="field" style={{ marginTop: 18 }}>
          <textarea aria-label="Your message to AgriSense" aria-describedby="assistant-input-help" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(event) => { if (shouldSubmitAssistantOnEnter(event.key, event.shiftKey, event.nativeEvent.isComposing)) { event.preventDefault(); submit(); } }} rows={4} />
          <small id="assistant-input-help">Press Enter to send. Use Shift+Enter for a new line.</small>
        </div>
        <div className="action-row">
          <button className="primary-btn" onClick={submit} disabled={loading || !input.trim()}>{loading ? 'Sending…' : 'Send'}</button>
        </div>
      </div>
    </div>
  );
}

function NotificationsPage({ language }: { language: LanguageCode }) {
  const [items, setItems] = useState<Array<{ id: number; title: string; message: string; severity: string; timestamp: string; read: boolean; data_source?: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = () => { setLoading(true); setError(''); getNotifications().then(setItems).catch((reason) => setError(reason.message)).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);
  const markRead = async (id: number) => {
    try { await markNotificationRead(id); setItems((prev) => prev.map((item) => item.id === id ? { ...item, read: true } : item)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not update notification.'); }
  };
  return <div className="page-shell"><div className="card list-card"><h3 className="section-title">{translate(language, 'nav.notifications')}</h3>
    {loading ? <LoadingSkeleton /> : error ? <p role="alert">{error} <button className="primary-btn" onClick={load}>Retry</button></p> : items.length ? items.map((item) => <div className="notification-item" key={item.id}>
      <div className="notification-top"><strong>{item.title}</strong><span className={`pill ${item.read ? 'low' : 'high'}`}>{item.read ? 'Read' : 'Unread'}</span></div>
      <div>{item.message}</div><div className="muted">{item.timestamp} · {item.data_source ?? 'DEMO DATA'}</div>
      {!item.read && <button className="ghost-btn" onClick={() => markRead(item.id)}>Mark as read</button>}
    </div>) : <EmptyState message="No notifications." />}
  </div></div>;
}

function LoadingSkeleton() {
  return (
    <div className="page-shell">
      <div className="card metric-card">
        <div className="skeleton" style={{ width: '55%', marginBottom: 12 }} />
        <div className="skeleton" style={{ width: '90%', marginBottom: 12 }} />
        <div className="skeleton" style={{ width: '70%', marginBottom: 12 }} />
        <div className="skeleton" style={{ width: '50%' }} />
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

export default App;
