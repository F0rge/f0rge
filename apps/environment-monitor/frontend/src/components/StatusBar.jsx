import React from 'react';

function StatusBar({ connectionStatus, lastUpdate }) {
  const statusText = connectionStatus === 'connected' ? 'Online' : connectionStatus === 'error' ? 'Offline' : 'Connecting';
  const statusVariant = connectionStatus === 'connected' ? 'success' : connectionStatus === 'error' ? 'danger' : 'secondary';

  return (
    <footer className="footer d-flex flex-wrap flex-items-center flex-justify-between border-top pt-3 f6 color-fg-muted">
      <span className={`Label Label--${statusVariant}`}>{statusText}</span>
      {lastUpdate && (
        <span className="text-mono">
          {new Date(lastUpdate).toLocaleString()}
        </span>
      )}
      <a href="/api/download-data" className="Button Button--secondary Button--small" title="Download CSV (press E)">
        <span className="Button-content"><span className="Button-label">Export</span></span>
      </a>
    </footer>
  );
}

export default StatusBar;