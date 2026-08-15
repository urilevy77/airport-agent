import ThemeToggle from './ThemeToggle'

export default function Header({ onNewChat, canStartNew = false, onExport,
                                 canExport = false, exporting = false,
                                 exportError = null }) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <div>
          <h1>Airport Investment Intelligence</h1>
          <span className="sub">US terminal expansion signals · BTS T-100</span>
        </div>
      </div>
      <div className="header-actions">
        {/* Beside the button that failed, not in the transcript: the download
            simply not arriving is indistinguishable from a slow one. */}
        {exportError
          ? <span className="export-error" role="status">{exportError}</span>
          : null}
        {/* Capturing every chart takes a couple of seconds and the upload runs
            to megabytes, so the button has to look busy while it does — an idle
            one invites a second click and a second export. */}
        <button
          type="button"
          className="export-doc"
          onClick={onExport}
          disabled={!canExport || exporting}
          title="Download this conversation, charts included, as a Word document"
          // The label keeps the word the control is known by while its face
          // changes, so it does not vanish from a screen reader mid-export.
          aria-label={exporting ? 'Export conversation — preparing' : 'Export conversation'}
          aria-busy={exporting}
        >
          {exporting ? 'Preparing…' : 'Export'}
        </button>
        {/* Disabled on an empty conversation: there is nothing to discard, and
            a live button that does nothing invites a click that looks broken. */}
        <button
          type="button"
          className="new-chat"
          onClick={onNewChat}
          disabled={!canStartNew}
          title="Clear this conversation and start a new one"
        >
          New chat
        </button>
        <ThemeToggle />
      </div>
    </header>
  )
}
