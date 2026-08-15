import ThemeToggle from './ThemeToggle'

export default function Header() {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <div>
          <h1>Airport Investment Intelligence</h1>
          <span className="sub">US terminal expansion signals · BTS T-100</span>
        </div>
      </div>
      <ThemeToggle />
    </header>
  )
}
