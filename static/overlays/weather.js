/* Weather overlay renderer (v4)
 * Renders the full retro TV weather broadcast layout into the virtual channel
 * overlay, matching the /weather standalone page design.
 * Compact: base font-size is set proportional to the container width in JS so
 * every em-based value scales together, making the overlay legible even in a
 * small player without needing to expand it.
 * Endpoint: GET /api/weather
 */
(function () {
  'use strict';
  const TYPE      = 'weather';
  const STYLE_ID  = 'vc-weather-overlay-styles-v4';
  const SVG_ID    = 'vc-weather-overlay-svgs';

  // ── CSS: all sizes in em so they scale with the container-width-driven
  //         font-size injected by render() onto .vc-wx-frame ─────────────────
  const CSS = `
    .vc-wx-frame {
      position: absolute;
      inset: 0;
      /* font-size set dynamically in JS proportional to container width */
      background: linear-gradient(160deg, #1030c8 0%, #0a1a80 40%, #081060 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-wx-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.06) 3px, rgba(0,0,0,0.06) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-wx-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1640d4 50%, #0d2aaa 100%);
      border-bottom: 2px solid #4a70ff;
      padding: 0.28em 0.8em;
      display: flex;
      align-items: center;
      gap: 0.6em;
      flex-shrink: 0;
    }
    .vc-wx-header-title {
      font-size: 1.35em;
      font-weight: 900;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.25em;
    }
    .vc-wx-header-subtitle {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
      margin-left: auto;
    }
    .vc-wx-updated {
      font-size: 0.75em;
      font-weight: 700;
      color: #ffd700;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.15em 0.8em 0;
      flex-shrink: 0;
    }
    .vc-wx-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 2.2fr;
      grid-template-rows: 1fr auto;
      gap: 0.3em;
      padding: 0.3em 0.45em 0.2em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-wx-box {
      background: rgba(10,40,170,0.75);
      border: 1px solid #3058d8;
      border-radius: 3px;
      padding: 0.28em 0.45em;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 6px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
    }
    .vc-wx-box-title {
      font-size: 0.76em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #c8d8ff;
      border-bottom: 1px solid #3058d8;
      padding-bottom: 0.2em;
      margin-bottom: 0.25em;
      white-space: nowrap;
    }
    .vc-wx-current { grid-column: 1; grid-row: 1; }
    .vc-wx-current-icon {
      line-height: 1;
      text-align: center;
      margin: 0.05em 0;
    }
    .vc-wx-current-temp {
      font-size: 2.5em;
      font-weight: 900;
      text-align: center;
      line-height: 1;
      margin: 0.05em 0;
    }
    .vc-wx-current-cond {
      font-size: 0.85em;
      font-weight: 700;
      text-align: center;
      margin-bottom: 0.2em;
    }
    .vc-wx-current-details {
      font-size: 0.72em;
      line-height: 1.5;
      color: #d0e0ff;
      margin-top: auto;
    }
    .vc-wx-today { grid-column: 2; grid-row: 1; }
    .vc-wx-today-cols {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      flex: 1;
      gap: 0;
      height: 100%;
    }
    .vc-wx-period {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.1em 0.25em;
    }
    .vc-wx-period + .vc-wx-period { border-left: 1px solid #3058d8; }
    .vc-wx-period-label {
      font-size: 0.72em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #c8d8ff;
      margin-bottom: 0.1em;
    }
    .vc-wx-period-icon {
      line-height: 1;
      margin: 0.08em 0;
    }
    .vc-wx-period-temp {
      font-size: 1.9em;
      font-weight: 900;
      line-height: 1;
    }
    .vc-wx-period-cond {
      font-size: 0.68em;
      font-weight: 700;
      text-align: center;
      margin-top: 0.1em;
      color: #d0e0ff;
    }
    .vc-wx-extended { grid-column: 1 / -1; grid-row: 2; }
    .vc-wx-extended .vc-wx-box-title { color: #40c0ff; }
    .vc-wx-ext-cols {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
    }
    .vc-wx-ext-day {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.1em 0.25em;
    }
    .vc-wx-ext-day + .vc-wx-ext-day { border-left: 1px solid #3058d8; }
    .vc-wx-ext-dow {
      font-size: 0.76em;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #c8d8ff;
    }
    .vc-wx-ext-icon {
      line-height: 1;
      margin: 0.06em 0;
    }
    .vc-wx-ext-temps {
      font-size: 0.9em;
      font-weight: 900;
    }
    .vc-wx-ext-cond {
      font-size: 0.65em;
      font-weight: 700;
      color: #d0e0ff;
      text-align: center;
    }
    .vc-wx-ticker-bar {
      background: #0a0e2a;
      border-top: 1px solid #4a70ff;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.7em;
    }
    .vc-wx-ticker-label {
      background: #ffd700;
      color: #0a0e2a;
      font-size: 0.75em;
      font-weight: 900;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      padding: 0 0.55em;
      white-space: nowrap;
      height: 100%;
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }
    .vc-wx-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-wx-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.72em;
      font-weight: 700;
      color: #ffd700;
      animation: vc-wx-scroll 28s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-wx-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
    .vc-wx-svg { display: inline-block; vertical-align: middle; }
    .vc-wx-ext-lo { opacity: 0.7; }
    .vc-wx-no-data { color: #90a8f0; padding: 0.4em; }

    /* ── Segment: 5-Day Forecast ─────────────────────────────────── */
    .vc-wx-seg-forecast {
      flex: 1;
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 0.3em;
      padding: 0.3em 0.45em 0.2em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-wx-fc-day {
      background: rgba(10,40,170,0.75);
      border: 1px solid #3058d8;
      border-radius: 3px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 6px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.3em 0.2em;
      overflow: hidden;
    }
    .vc-wx-fc-today {
      border-color: #40c0ff;
      background: rgba(10,60,190,0.85);
    }
    .vc-wx-fc-dow {
      font-size: 0.82em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #c8d8ff;
      margin-bottom: 0.1em;
    }
    .vc-wx-fc-today .vc-wx-fc-dow { color: #40c0ff; }
    .vc-wx-fc-icon { line-height: 1; margin: 0.15em 0; }
    .vc-wx-fc-hi {
      font-size: 1.9em;
      font-weight: 900;
      line-height: 1;
      margin-top: 0.05em;
    }
    .vc-wx-fc-lo {
      font-size: 1.1em;
      font-weight: 700;
      opacity: 0.6;
      line-height: 1;
      margin-bottom: 0.1em;
    }
    .vc-wx-fc-cond {
      font-size: 0.64em;
      font-weight: 700;
      text-align: center;
      color: #d0e0ff;
      margin-top: auto;
      padding: 0 0.1em;
    }

    /* ── Segment: Regional Radar ─────────────────────────────────── */
    .vc-wx-seg-radar {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 0.3em 0.45em 0.15em;
      min-height: 0;
      overflow: hidden;
      gap: 0.2em;
    }
    .vc-wx-radar-img-wrap {
      flex: 1;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background: #000818;
      border: 1px solid #3058d8;
      border-radius: 3px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.5);
      min-height: 0;
      position: relative;
    }
    .vc-wx-radar-img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      display: block;
    }
    .vc-wx-radar-err {
      color: #7090c0;
      font-size: 0.8em;
      font-weight: 700;
      text-align: center;
      padding: 1em;
      display: none;
    }
    .vc-wx-radar-caption {
      font-size: 0.68em;
      font-weight: 700;
      color: #8098c0;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      align-self: flex-end;
    }

    /* ── Segment: Severe Weather Alerts ──────────────────────────── */
    .vc-wx-seg-alerts {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 0.35em 0.45em 0.2em;
      gap: 0.3em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-wx-alert-item {
      background: rgba(140,20,20,0.7);
      border: 1px solid #cc4444;
      border-radius: 3px;
      padding: 0.4em 0.7em;
      display: flex;
      flex-direction: column;
      gap: 0.15em;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      overflow: hidden;
    }
    .vc-wx-alert-item.moderate {
      background: rgba(140,80,10,0.75);
      border-color: #cc8833;
    }
    .vc-wx-alert-item.minor {
      background: rgba(100,100,10,0.75);
      border-color: #bbaa22;
    }
    .vc-wx-alert-header {
      display: flex;
      align-items: center;
      gap: 0.4em;
    }
    .vc-wx-alert-badge {
      font-size: 0.68em;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      padding: 0.12em 0.45em;
      border-radius: 2px;
      flex-shrink: 0;
    }
    .vc-wx-alert-badge.extreme, .vc-wx-alert-badge.severe {
      background: #cc2222;
      color: #fff;
    }
    .vc-wx-alert-badge.moderate {
      background: #cc7711;
      color: #fff;
    }
    .vc-wx-alert-badge.minor {
      background: #aaaa00;
      color: #111;
    }
    .vc-wx-alert-badge.unknown {
      background: #445577;
      color: #ddd;
    }
    .vc-wx-alert-event {
      font-size: 0.84em;
      font-weight: 900;
      letter-spacing: 0.03em;
      color: #ffdddd;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .vc-wx-alert-item.moderate .vc-wx-alert-event { color: #ffe8c0; }
    .vc-wx-alert-item.minor .vc-wx-alert-event    { color: #fffac0; }
    .vc-wx-alert-headline {
      font-size: 0.7em;
      font-weight: 700;
      color: #ffcccc;
      line-height: 1.3;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }
    .vc-wx-alert-item.moderate .vc-wx-alert-headline { color: #ffddb0; }
    .vc-wx-alert-item.minor .vc-wx-alert-headline    { color: #fefaaa; }
    .vc-wx-alert-expires {
      font-size: 0.63em;
      color: #cc9999;
      margin-top: 0.05em;
    }
    .vc-wx-alert-item.moderate .vc-wx-alert-expires { color: #cc9966; }
    .vc-wx-alert-item.minor .vc-wx-alert-expires    { color: #aaaa55; }
    .vc-wx-alerts-source {
      font-size: 0.62em;
      font-weight: 700;
      color: #607090;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      text-align: right;
      padding: 0.1em 0.1em 0;
      flex-shrink: 0;
    }
    .vc-wx-no-alerts {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.4em;
    }
    .vc-wx-no-alerts-icon { font-size: 3.5em; line-height: 1; }
    .vc-wx-no-alerts-title {
      font-size: 1em;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #60d060;
    }
    .vc-wx-no-alerts-sub {
      font-size: 0.72em;
      color: #70a870;
    }

    /* ── Animated Background Layer ──────────────────────────────────── */
    .vc-wx-bg-anim {
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      overflow: hidden;
    }
    /* Keep all weather content above the animated background layer */
    .vc-wx-frame > :not(.vc-wx-bg-anim) {
      position: relative;
      z-index: 1;
    }

    /* Sunny ──────────────────────────────────────────────────────────── */
    .vc-wx-bg-anim.wx-bg-sunny {
      background:
        radial-gradient(ellipse 110% 55% at 50% -8%,
          rgba(255, 210, 0, 0.25) 0%, transparent 55%),
        linear-gradient(180deg, #1838cc 0%, #0a1a80 50%, #081060 100%);
    }
    .vc-wx-bg-anim.wx-bg-sunny::before {
      content: '';
      position: absolute;
      top: -18%; left: 32%;
      width: 36%; height: 55%;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255, 210, 0, 0.28) 0%, transparent 65%);
      animation: vc-wx-sun-pulse 5s ease-in-out infinite;
    }
    @keyframes vc-wx-sun-pulse {
      0%, 100% { opacity: 0.5; transform: scale(1); }
      50%       { opacity: 1;   transform: scale(1.12); }
    }

    /* Partly Cloudy ──────────────────────────────────────────────────── */
    .vc-wx-bg-anim.wx-bg-partly-cloudy {
      background:
        radial-gradient(ellipse 85% 45% at 62% -10%,
          rgba(255, 200, 0, 0.18) 0%, transparent 55%),
        linear-gradient(180deg, #1535cc 0%, #0a1a80 55%, #081060 100%);
    }
    .vc-wx-bg-anim.wx-bg-partly-cloudy::before {
      content: '';
      position: absolute;
      top: 3%; left: -2%;
      width: 65%; height: 28%;
      background:
        radial-gradient(ellipse 50% 60% at 38% 50%,
          rgba(155, 175, 225, 0.14) 0%, transparent 70%);
      animation: vc-wx-cloud-slow1 13s ease-in-out infinite alternate;
    }

    /* Cloudy ─────────────────────────────────────────────────────────── */
    .vc-wx-bg-anim.wx-bg-cloudy {
      background: linear-gradient(180deg, #1a2258 0%, #0d1440 55%, #090e30 100%);
    }
    .vc-wx-bg-anim.wx-bg-cloudy::before {
      content: '';
      position: absolute;
      top: 0%; left: -5%;
      width: 80%; height: 42%;
      background:
        radial-gradient(ellipse 55% 55% at 35% 40%,
          rgba(140, 155, 210, 0.18) 0%, transparent 65%),
        radial-gradient(ellipse 40% 40% at 78% 28%,
          rgba(120, 140, 200, 0.12) 0%, transparent 55%);
      animation: vc-wx-cloud-slow1 14s ease-in-out infinite alternate;
    }
    .vc-wx-bg-anim.wx-bg-cloudy::after {
      content: '';
      position: absolute;
      top: 6%; right: -12%;
      width: 62%; height: 36%;
      background:
        radial-gradient(ellipse 50% 50% at 60% 55%,
          rgba(130, 150, 210, 0.11) 0%, transparent 60%);
      animation: vc-wx-cloud-slow2 19s ease-in-out infinite alternate;
    }
    @keyframes vc-wx-cloud-slow1 {
      from { transform: translateX(0); }
      to   { transform: translateX(5%); }
    }
    @keyframes vc-wx-cloud-slow2 {
      from { transform: translateX(0); }
      to   { transform: translateX(-6%); }
    }

    /* Thunderstorm ───────────────────────────────────────────────────── */
    .vc-wx-bg-anim.wx-bg-thunderstorm {
      background: linear-gradient(180deg, #0e1530 0%, #070d20 65%, #050910 100%);
    }
    .vc-wx-bg-anim.wx-bg-thunderstorm::before {
      content: '';
      position: absolute;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 50% at 50% 18%,
          rgba(80, 90, 130, 0.22) 0%, transparent 65%);
    }
    .vc-wx-lightning-flash {
      position: absolute;
      inset: 0;
      background: rgba(200, 210, 255, 0.06);
      animation: vc-wx-lightning-flash 7s steps(1) infinite;
      pointer-events: none;
    }
    @keyframes vc-wx-lightning-flash {
      0%, 88%, 90.6%, 92.6%, 94%, 100% { opacity: 0; }
      89%, 90%   { opacity: 1;   }
      91%, 92%   { opacity: 0.7; }
      93%, 93.6% { opacity: 0.4; }
    }

    /* Foggy ──────────────────────────────────────────────────────────── */
    .vc-wx-bg-anim.wx-bg-foggy {
      background: linear-gradient(180deg, #18202e 0%, #0e1620 65%, #080e18 100%);
    }
    .vc-wx-bg-anim.wx-bg-foggy::before {
      content: '';
      position: absolute;
      top: 8%; left: -12%;
      width: 125%; height: 32%;
      background: linear-gradient(90deg,
        transparent 0%,
        rgba(155, 170, 200, 0.12) 25%,
        rgba(160, 175, 205, 0.16) 55%,
        rgba(155, 170, 200, 0.12) 78%,
        transparent 100%);
      border-radius: 50%;
      animation: vc-wx-fog-drift1 22s linear infinite alternate;
    }
    .vc-wx-bg-anim.wx-bg-foggy::after {
      content: '';
      position: absolute;
      top: 42%; left: -18%;
      width: 135%; height: 28%;
      background: linear-gradient(90deg,
        transparent 0%,
        rgba(140, 155, 185, 0.09) 22%,
        rgba(148, 163, 192, 0.13) 55%,
        rgba(140, 155, 185, 0.09) 82%,
        transparent 100%);
      border-radius: 50%;
      animation: vc-wx-fog-drift2 30s linear infinite alternate;
    }
    @keyframes vc-wx-fog-drift1 {
      from { transform: translateX(0); }
      to   { transform: translateX(12%); }
    }
    @keyframes vc-wx-fog-drift2 {
      from { transform: translateX(0); }
      to   { transform: translateX(-10%); }
    }

    /* Canvas-based backgrounds (rain, snow, windy) */
    .vc-wx-bg-canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 0;
      pointer-events: none;
    }
    .vc-wx-bg-anim.wx-bg-rain,
    .vc-wx-bg-anim.wx-bg-snow,
    .vc-wx-bg-anim.wx-bg-windy {
      background: linear-gradient(180deg, #0e1a48 0%, #081030 55%, #050820 100%);
    }

    /* Reduced motion: disable all background animations */
    @media (prefers-reduced-motion: reduce) {
      .vc-wx-bg-anim,
      .vc-wx-bg-anim::before,
      .vc-wx-bg-anim::after,
      .vc-wx-lightning-flash {
        animation: none !important;
        transition: none !important;
      }
      .vc-wx-bg-canvas { display: none; }
    }
  `;

  // ── SVG icon defs (same symbols as weather.html) ─────────────────────────
  const SVG_DEFS = `
    <svg id="${SVG_ID}" width="0" height="0" style="position:absolute;overflow:hidden">
      <defs>
        <symbol id="vc-icon-sunny" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="13" fill="#ffd700" stroke="#ffb300" stroke-width="1.5"/>
          <g stroke="#ffd700" stroke-width="2.5" stroke-linecap="round">
            <line x1="32" y1="4"  x2="32" y2="11"/>
            <line x1="32" y1="53" x2="32" y2="60"/>
            <line x1="4"  y1="32" x2="11" y2="32"/>
            <line x1="53" y1="32" x2="60" y2="32"/>
            <line x1="12" y1="12" x2="17" y2="17"/>
            <line x1="47" y1="47" x2="52" y2="52"/>
            <line x1="52" y1="12" x2="47" y2="17"/>
            <line x1="17" y1="47" x2="12" y2="52"/>
          </g>
        </symbol>
        <symbol id="vc-icon-partly_cloudy" viewBox="0 0 64 64">
          <circle cx="24" cy="22" r="11" fill="#ffd700" stroke="#ffb300" stroke-width="1.5"/>
          <g stroke="#ffd700" stroke-width="2" stroke-linecap="round">
            <line x1="24" y1="4"  x2="24" y2="9"/>
            <line x1="24" y1="35" x2="24" y2="38"/>
            <line x1="6"  y1="22" x2="11" y2="22"/>
            <line x1="37" y1="22" x2="42" y2="22"/>
            <line x1="10" y1="10" x2="14" y2="14"/>
            <line x1="34" y1="30" x2="38" y2="34"/>
            <line x1="38" y1="10" x2="34" y2="14"/>
            <line x1="14" y1="30" x2="10" y2="34"/>
          </g>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#d0deff"/>
          <rect x="22" y="28" width="24" height="14" rx="7" fill="#e8eeff"/>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#c0d0f0"/>
        </symbol>
        <symbol id="vc-icon-cloudy" viewBox="0 0 64 64">
          <rect x="8"  y="32" width="48" height="18" rx="9" fill="#c0d0f0"/>
          <rect x="16" y="22" width="32" height="18" rx="9" fill="#d8e4ff"/>
          <rect x="8"  y="32" width="48" height="18" rx="9" fill="#b0c4e8"/>
        </symbol>
        <symbol id="vc-icon-partly_cloudy_night" viewBox="0 0 64 64">
          <path d="M34 8 C24 10 18 20 22 30 C26 40 38 42 46 36 C40 40 28 38 24 28 C20 18 28 8 34 8Z" fill="#c8b44a" stroke="#a89030" stroke-width="1"/>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#d0deff"/>
          <rect x="22" y="28" width="24" height="14" rx="7" fill="#e8eeff"/>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#c0d0f0"/>
        </symbol>
        <symbol id="vc-icon-cloudy_night" viewBox="0 0 64 64">
          <path d="M28 6 C18 8 12 18 16 28 C20 38 32 40 40 34 C34 38 22 36 18 26 C14 16 22 6 28 6Z" fill="#c8b44a" stroke="#a89030" stroke-width="1"/>
          <rect x="8"  y="32" width="48" height="18" rx="9" fill="#b0c4e8"/>
          <rect x="16" y="22" width="32" height="18" rx="9" fill="#c8d8f8"/>
        </symbol>
        <symbol id="vc-icon-rain" viewBox="0 0 64 64">
          <rect x="8"  y="18" width="48" height="16" rx="8" fill="#b0c4e8"/>
          <rect x="16" y="10" width="32" height="16" rx="8" fill="#c8d8f8"/>
          <g stroke="#4488cc" stroke-width="2.5" stroke-linecap="round">
            <line x1="20" y1="40" x2="18" y2="52"/>
            <line x1="32" y1="40" x2="30" y2="52"/>
            <line x1="44" y1="40" x2="42" y2="52"/>
          </g>
        </symbol>
        <symbol id="vc-icon-showers" viewBox="0 0 64 64">
          <circle cx="24" cy="16" r="9"  fill="#ffd700" stroke="#ffb300" stroke-width="1.5"/>
          <rect x="18" y="24" width="32" height="14" rx="7" fill="#b0c4e8"/>
          <rect x="26" y="16" width="20" height="12" rx="6" fill="#c8d8f8"/>
          <g stroke="#4488cc" stroke-width="2.5" stroke-linecap="round">
            <line x1="24" y1="44" x2="22" y2="56"/>
            <line x1="36" y1="44" x2="34" y2="56"/>
            <line x1="48" y1="44" x2="46" y2="56"/>
          </g>
        </symbol>
        <symbol id="vc-icon-thunderstorm" viewBox="0 0 64 64">
          <rect x="8"  y="12" width="48" height="16" rx="8" fill="#8090b0"/>
          <rect x="16" y="6"  width="32" height="14" rx="7" fill="#a0b0c8"/>
          <polygon points="34,28 26,44 32,44 28,58 42,38 36,38" fill="#ffd700"/>
        </symbol>
        <symbol id="vc-icon-drizzle" viewBox="0 0 64 64">
          <rect x="8"  y="18" width="48" height="16" rx="8" fill="#b0c4e8"/>
          <rect x="16" y="10" width="32" height="16" rx="8" fill="#c8d8f8"/>
          <g stroke="#88aadd" stroke-width="2" stroke-linecap="round">
            <line x1="20" y1="40" x2="19" y2="48"/>
            <line x1="28" y1="42" x2="27" y2="50"/>
            <line x1="36" y1="40" x2="35" y2="48"/>
            <line x1="44" y1="42" x2="43" y2="50"/>
          </g>
        </symbol>
        <symbol id="vc-icon-snow" viewBox="0 0 64 64">
          <rect x="8"  y="14" width="48" height="16" rx="8" fill="#b0c4e8"/>
          <rect x="16" y="6"  width="32" height="16" rx="8" fill="#c8d8f8"/>
          <g fill="#d0e8ff">
            <circle cx="20" cy="46" r="3"/>
            <circle cx="32" cy="44" r="3"/>
            <circle cx="44" cy="46" r="3"/>
            <circle cx="26" cy="54" r="2.5"/>
            <circle cx="38" cy="54" r="2.5"/>
          </g>
        </symbol>
        <symbol id="vc-icon-foggy" viewBox="0 0 64 64">
          <rect x="8"  y="12" width="48" height="10" rx="5" fill="#b0bcd0" opacity="0.8"/>
          <rect x="12" y="26" width="40" height="8"  rx="4" fill="#a8b8cc" opacity="0.8"/>
          <rect x="8"  y="38" width="48" height="8"  rx="4" fill="#98a8bc" opacity="0.7"/>
          <rect x="14" y="50" width="36" height="8"  rx="4" fill="#8898ac" opacity="0.6"/>
        </symbol>
      </defs>
    </svg>`;

  const ICON_MAP = {
    sunny:               'vc-icon-sunny',
    partly_cloudy:       'vc-icon-partly_cloudy',
    partly_cloudy_night: 'vc-icon-partly_cloudy_night',
    cloudy:              'vc-icon-cloudy',
    cloudy_night:        'vc-icon-cloudy_night',
    rain:                'vc-icon-rain',
    showers:             'vc-icon-showers',
    thunderstorm:        'vc-icon-thunderstorm',
    drizzle:             'vc-icon-drizzle',
    snow:                'vc-icon-snow',
    foggy:               'vc-icon-foggy',
  };

  // ── Animated Background ───────────────────────────────────────────────────

  // Map bg_condition value → CSS class on .vc-wx-bg-anim
  const BG_CSS_CLASS = {
    sunny:               'wx-bg-sunny',
    partly_cloudy:       'wx-bg-partly-cloudy',
    partly_cloudy_night: 'wx-bg-partly-cloudy',
    cloudy:              'wx-bg-cloudy',
    cloudy_night:        'wx-bg-cloudy',
    thunderstorm:        'wx-bg-thunderstorm',
    foggy:               'wx-bg-foggy',
    rain:                'wx-bg-rain',
    drizzle:             'wx-bg-rain',
    showers:             'wx-bg-rain',
    snow:                'wx-bg-snow',
    windy:               'wx-bg-windy',
  };

  // Canvas-based conditions (particle systems drawn each frame)
  const BG_CANVAS_CONDITIONS = new Set(['rain', 'drizzle', 'showers', 'snow', 'windy']);

  // Particle counts per condition — higher = denser effect
  const BG_PARTICLE_COUNT_SNOW    = 55;
  const BG_PARTICLE_COUNT_WINDY   = 35;
  const BG_PARTICLE_COUNT_DRIZZLE = 45;
  const BG_PARTICLE_COUNT_RAIN    = 65;

  let _bgRafId = null;

  function _prefersReducedMotion() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
    catch (e) { return false; }
  }

  function _cancelBgAnim() {
    if (_bgRafId !== null) { cancelAnimationFrame(_bgRafId); _bgRafId = null; }
  }

  function _runCanvasBg(canvas, condition) {
    if (_prefersReducedMotion()) return;
    const isSnow  = condition === 'snow';
    const isWindy = condition === 'windy';
    const isDrizzle = condition === 'drizzle';
    const COUNT   = isSnow ? BG_PARTICLE_COUNT_SNOW
                           : isWindy   ? BG_PARTICLE_COUNT_WINDY
                           : isDrizzle ? BG_PARTICLE_COUNT_DRIZZLE
                           : BG_PARTICLE_COUNT_RAIN;

    const particles = [];
    function _initP(p) {
      if (!p) p = {};
      p.x = Math.random();
      p.y = isSnow ? Math.random() : (Math.random() - 0.05);
      if (isSnow) {
        p.r  = Math.random() * 2.2 + 0.9;
        p.vy = Math.random() * 0.00075 + 0.0003;
        p.vx = (Math.random() - 0.5) * 0.00025;
        p.a  = Math.random() * 0.45 + 0.2;
        p.wb = Math.random() * Math.PI * 2;
        p.ws = Math.random() * 0.018 + 0.007;
      } else if (isWindy) {
        p.r  = Math.random() * 1.4 + 0.7;
        p.vx = Math.random() * 0.0022 + 0.0009;
        p.vy = (Math.random() - 0.5) * 0.0004;
        p.a  = Math.random() * 0.35 + 0.15;
        p.len = Math.random() * 0.04 + 0.018;
      } else {
        p.r  = isDrizzle ? Math.random() * 0.5 + 0.4 : Math.random() * 0.75 + 0.5;
        p.len = isDrizzle ? Math.random() * 0.04 + 0.03 : Math.random() * 0.065 + 0.05;
        p.vy = Math.random() * 0.003 + (isDrizzle ? 0.0012 : 0.0026);
        p.vx = isDrizzle ? -0.00025 : -0.00075;
        p.a  = Math.random() * 0.32 + (isDrizzle ? 0.12 : 0.2);
      }
      return p;
    }
    for (let i = 0; i < COUNT; i++) particles.push(_initP(null));

    function draw() {
      const el = canvas.parentElement;
      if (!el) return; // detached
      const w = el.offsetWidth, h = el.offsetHeight;
      if (!w || !h) { _bgRafId = requestAnimationFrame(draw); return; }
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w; canvas.height = h;
      }
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, w, h);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const px = p.x * w, py = p.y * h;
        ctx.globalAlpha = p.a;
        if (isSnow) {
          p.wb += p.ws;
          ctx.fillStyle = '#d0e4ff';
          ctx.beginPath();
          ctx.arc(px + Math.sin(p.wb) * 3, py, p.r, 0, Math.PI * 2);
          ctx.fill();
          p.x += p.vx; p.y += p.vy;
          if (p.y > 1.04) { p.x = Math.random(); p.y = -0.02; }
          if (p.x < -0.02 || p.x > 1.02) p.x = Math.random();
        } else if (isWindy) {
          ctx.strokeStyle = 'rgba(190, 215, 255, 0.75)';
          ctx.lineWidth = p.r * 0.5;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(px - p.len * w, py + p.vy * h * 18);
          ctx.stroke();
          p.x += p.vx; p.y += p.vy;
          if (p.x > 1.06) { p.x = -0.04; p.y = Math.random(); }
          if (p.y < 0 || p.y > 1) p.y = Math.random();
        } else {
          ctx.strokeStyle = 'rgba(155, 188, 240, 0.8)';
          ctx.lineWidth = p.r;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(px + p.vx * w * 12, py + p.len * h);
          ctx.stroke();
          p.x += p.vx; p.y += p.vy;
          if (p.y > 1.08) { p.x = Math.random(); p.y = -0.05; }
          if (p.x < -0.06) { p.x = 1.02; p.y = Math.random(); }
        }
      }
      ctx.globalAlpha = 1;
      _bgRafId = requestAnimationFrame(draw);
    }
    _cancelBgAnim();
    _bgRafId = requestAnimationFrame(draw);
  }

  function _applyWeatherBackground(frame, condition) {
    _cancelBgAnim();
    const bgDiv = document.createElement('div');
    bgDiv.className = 'vc-wx-bg-anim';
    const cls = BG_CSS_CLASS[condition];
    if (cls) bgDiv.classList.add(cls);

    if (condition === 'thunderstorm') {
      const flash = document.createElement('div');
      flash.className = 'vc-wx-lightning-flash';
      bgDiv.appendChild(flash);
    }

    if (BG_CANVAS_CONDITIONS.has(condition)) {
      const canvas = document.createElement('canvas');
      canvas.className = 'vc-wx-bg-canvas';
      canvas.style.opacity = condition === 'windy' ? '0.5' : '0.45';
      bgDiv.appendChild(canvas);
      // defer canvas start until it is in the DOM
      requestAnimationFrame(function () { _runCanvasBg(canvas, condition); });
    }

    frame.insertBefore(bgDiv, frame.firstChild);
  }

  function ensureAssets() {
    if (!document.getElementById(STYLE_ID)) {
      const s = document.createElement('style');
      s.id = STYLE_ID;
      s.textContent = CSS;
      document.head.appendChild(s);
    }
    if (!document.getElementById(SVG_ID)) {
      const tmp = document.createElement('div');
      tmp.innerHTML = SVG_DEFS.trim();
      document.body.insertBefore(tmp.firstChild, document.body.firstChild);
    }
  }

  // Font-size scaling: base px = container_width / FONT_SCALE_DIVISOR, clamped
  // to [FONT_MIN_PX, FONT_MAX_PX].  All em values in CSS scale together.
  const FONT_SCALE_DIVISOR = 48;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 13;

  // Icon sizes as multiples of the base font (px)
  const ICON_RATIO_LG  = 3.2;   // current conditions
  const ICON_RATIO_MD  = 2.4;   // today periods
  const ICON_RATIO_SM  = 1.9;   // extended days
  const ICON_RATIO_HDR = 1.4;   // header icon

  function iconSvg(key, size) {
    const sym = ICON_MAP[key] || 'vc-icon-cloudy';
    return `<svg class="vc-wx-svg" width="${size}" height="${size}"><use href="#${sym}"/></svg>`;
  }

  function tempStr(t) {
    return (t != null) ? `${t}°` : '--°';
  }

  function formatLocalTime(isoStr) {
    try {
      return new Date(isoStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (e) { return isoStr; }
  }

  // ── Shared header / ticker helpers ─────────────────────────────────────────

  function headerHtml(subtitle, iconHdr) {
    return `
      <div class="vc-wx-header">
        <div class="vc-wx-header-title">
          <span>RetroIPTV</span>
          ${iconSvg('partly_cloudy', iconHdr)}
          <span>Weather</span>
        </div>
        <div class="vc-wx-header-subtitle">${subtitle}</div>
      </div>`;
  }

  function updatedBarHtml(location, updatedIso) {
    return `<div class="vc-wx-updated">
      <span>${location || ''}</span>
      <span>UPDATED: ${updatedIso ? formatLocalTime(updatedIso) : ''}</span>
    </div>`;
  }

  function tickerHtml(ticks) {
    const tickText = (ticks && ticks.length)
      ? ticks.join(' \u2022 ') + ' \u2022 '
      : 'No active weather alerts \u2022 ';
    return `
      <div class="vc-wx-ticker-bar">
        <div class="vc-wx-ticker-label">Weather Alert:</div>
        <div class="vc-wx-ticker-scroll">
          <span class="vc-wx-ticker-track">${tickText.repeat(3)}</span>
        </div>
      </div>`;
  }

  // ── Segment 0: Current Conditions ─────────────────────────────────────────

  function renderCurrent(data, frame, bp) {
    const now   = data?.now   || {};
    const today = Array.isArray(data?.today)    ? data.today    : [];
    const ext   = Array.isArray(data?.extended) ? data.extended : [];
    const ticks = Array.isArray(data?.ticker)   ? data.ticker   : [];

    const iconLg  = Math.round(bp * ICON_RATIO_LG);
    const iconMd  = Math.round(bp * ICON_RATIO_MD);
    const iconSm  = Math.round(bp * ICON_RATIO_SM);
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);

    const periodCols = today.map(p => `
      <div class="vc-wx-period">
        <div class="vc-wx-period-label">${p.label || ''}</div>
        <div class="vc-wx-period-icon">${iconSvg(p.icon, iconMd)}</div>
        <div class="vc-wx-period-temp">${tempStr(p.temp)}</div>
        <div class="vc-wx-period-cond">${p.condition || ''}</div>
      </div>`).join('');

    const extCols = ext.map(d => `
      <div class="vc-wx-ext-day">
        <div class="vc-wx-ext-dow">${d.dow || ''}</div>
        <div class="vc-wx-ext-icon">${iconSvg(d.icon, iconSm)}</div>
        <div class="vc-wx-ext-temps">${tempStr(d.hi)} <span class="vc-wx-ext-lo">${tempStr(d.lo)}</span></div>
        <div class="vc-wx-ext-cond">${d.condition || ''}</div>
      </div>`).join('');

    const details = [];
    if (now.humidity != null)  details.push(`Humid: ${now.humidity}%`);
    if (now.wind)               details.push(`Wind: ${now.wind}`);
    if (now.feels_like != null) details.push(`Feels Like: ${now.feels_like}°`);

    frame.innerHTML =
      headerHtml('Current Conditions', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      `<div class="vc-wx-body">
        <div class="vc-wx-box vc-wx-current">
          <div class="vc-wx-box-title">Current Conditions</div>
          <div class="vc-wx-current-icon">${iconSvg(now.icon || 'cloudy', iconLg)}</div>
          <div class="vc-wx-current-temp">${tempStr(now.temp)}</div>
          <div class="vc-wx-current-cond">${now.condition || ''}</div>
          <div class="vc-wx-current-details">${details.join('<br>')}</div>
        </div>
        <div class="vc-wx-box vc-wx-today">
          <div class="vc-wx-box-title">Today's Forecast</div>
          <div class="vc-wx-today-cols">${periodCols}</div>
        </div>
        <div class="vc-wx-box vc-wx-extended">
          <div class="vc-wx-box-title">Extended Outlook</div>
          <div class="vc-wx-ext-cols">${extCols || '<div class="vc-wx-no-data">No extended forecast available.</div>'}</div>
        </div>
      </div>` +
      tickerHtml(ticks);
  }

  // ── Segment 1: 5-Day Forecast ──────────────────────────────────────────────

  function renderForecast(data, frame, bp) {
    const five = Array.isArray(data?.five_day) ? data.five_day : [];
    const ticks = Array.isArray(data?.ticker) ? data.ticker : [];
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);
    const iconLg  = Math.round(bp * ICON_RATIO_LG);

    const dayCols = five.map((d, i) => `
      <div class="vc-wx-fc-day${i === 0 ? ' vc-wx-fc-today' : ''}">
        <div class="vc-wx-fc-dow">${d.dow || ''}</div>
        <div class="vc-wx-fc-icon">${iconSvg(d.icon, iconLg)}</div>
        <div class="vc-wx-fc-hi">${tempStr(d.hi)}</div>
        <div class="vc-wx-fc-lo">${tempStr(d.lo)}</div>
        <div class="vc-wx-fc-cond">${d.condition || ''}</div>
      </div>`).join('');

    frame.innerHTML =
      headerHtml('5-Day Forecast', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      `<div class="vc-wx-seg-forecast">
        ${dayCols || '<div class="vc-wx-no-data" style="grid-column:1/-1">No forecast data available.</div>'}
      </div>` +
      tickerHtml(ticks);
  }

  // ── Segment 2: Regional Radar ──────────────────────────────────────────────

  function renderRadar(data, frame, bp) {
    const ticks   = Array.isArray(data?.ticker) ? data.ticker : [];
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);
    const radarUrl = data?.radar_url || '';

    frame.innerHTML =
      headerHtml('Regional Radar', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      `<div class="vc-wx-seg-radar">
        <div class="vc-wx-radar-img-wrap" id="vc-wx-radar-wrap">
          ${radarUrl
            ? `<img class="vc-wx-radar-img" id="vc-wx-radar-img"
                    src="${radarUrl}" alt="Regional Radar"
                    onerror="document.getElementById('vc-wx-radar-img').style.display='none';
                             document.getElementById('vc-wx-radar-err').style.display='block';">
               <div class="vc-wx-radar-err" id="vc-wx-radar-err">Radar Unavailable</div>`
            : `<div class="vc-wx-radar-err" style="display:block">Radar Unavailable &mdash; No location configured</div>`}
        </div>
        <div class="vc-wx-radar-caption">Source: NOAA/NWS</div>
      </div>` +
      tickerHtml(ticks);
  }

  // ── Segment 3: Severe Weather Alerts ──────────────────────────────────────

  function _alertClass(severity) {
    const s = (severity || '').toLowerCase();
    if (s === 'extreme' || s === 'severe') return 'severe';
    if (s === 'moderate') return 'moderate';
    if (s === 'minor') return 'minor';
    return 'unknown';
  }

  function _alertBadgeLabel(severity) {
    const s = (severity || '').toLowerCase();
    if (s === 'extreme')  return 'EXTREME';
    if (s === 'severe')   return 'SEVERE';
    if (s === 'moderate') return 'MODERATE';
    if (s === 'minor')    return 'MINOR';
    return 'ALERT';
  }

  function _fmtExpires(isoStr) {
    if (!isoStr) return '';
    try {
      return 'Expires: ' + new Date(isoStr).toLocaleString([], {
        month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit'
      });
    } catch (e) { return ''; }
  }

  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderAlerts(data, frame, bp) {
    const alerts  = Array.isArray(data?.alerts) ? data.alerts : [];
    const ticks   = Array.isArray(data?.ticker) ? data.ticker : [];
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);
    const iconLg  = Math.round(bp * ICON_RATIO_LG);

    let bodyHtml;
    if (alerts.length) {
      const items = alerts.map(a => {
        const cls      = _alertClass(a.severity);
        const badge    = _alertBadgeLabel(a.severity);
        const event    = a.event    ? _escHtml(a.event)    : '';
        const headline = a.headline ? _escHtml(a.headline) : event;
        const expires  = _fmtExpires(a.expires);
        return `
          <div class="vc-wx-alert-item ${cls}">
            <div class="vc-wx-alert-header">
              <span class="vc-wx-alert-badge ${cls}">${badge}</span>
              <span class="vc-wx-alert-event">${event}</span>
            </div>
            ${headline ? `<div class="vc-wx-alert-headline">${headline}</div>` : ''}
            ${expires  ? `<div class="vc-wx-alert-expires">${expires}</div>`  : ''}
          </div>`;
      }).join('');
      bodyHtml = `
        <div class="vc-wx-seg-alerts">
          ${items}
          <div class="vc-wx-alerts-source">Source: NOAA/NWS</div>
        </div>`;
    } else if (ticks.length) {
      const items = ticks.map(t => `
        <div class="vc-wx-alert-item">
          <div class="vc-wx-alert-header">
            <span class="vc-wx-alert-badge unknown">&#9888;</span>
            <span class="vc-wx-alert-event">${_escHtml(t)}</span>
          </div>
        </div>`).join('');
      bodyHtml = `<div class="vc-wx-seg-alerts">${items}</div>`;
    } else {
      bodyHtml = `
        <div class="vc-wx-seg-alerts">
          <div class="vc-wx-no-alerts">
            <div class="vc-wx-no-alerts-icon">${iconSvg('sunny', iconLg)}</div>
            <div class="vc-wx-no-alerts-title">No Active Severe Weather Alerts</div>
            <div class="vc-wx-no-alerts-sub">${data?.location || 'Local Area'}</div>
          </div>
          <div class="vc-wx-alerts-source">Source: NOAA/NWS</div>
        </div>`;
    }

    frame.innerHTML =
      headerHtml('Severe Weather Alerts', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      bodyHtml +
      tickerHtml(ticks);
  }

  function render(data, root) {
    ensureAssets();
    root.querySelectorAll('.vc-overlay').forEach(e => e.remove());
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-wx-frame';
    frame.id = 'vc-wx-frame';

    const now = data?.now || {};
    // Prefer the API-derived bg_condition (which may reflect an admin override),
    // then fall back to the current icon, and ultimately to 'cloudy' as a safe
    // neutral default that works for the unconfigured / stub state.
    const bgCondition = data?.bg_condition || now.icon || 'cloudy';

    // ── Not configured ──────────────────────────────────────────────────────
    if (now.condition === 'Not Configured') {
      const bp      = Math.max(FONT_MIN_PX, Math.min((root.offsetWidth || 960) / FONT_SCALE_DIVISOR, FONT_MAX_PX));
      const iconLg  = Math.round(bp * ICON_RATIO_LG);
      const iconHdr = Math.round(bp * ICON_RATIO_HDR);
      frame.style.fontSize = bp + 'px';
      frame.innerHTML = `
        <div class="vc-wx-header">
          <div class="vc-wx-header-title">
            <span>RetroIPTV</span>
            ${iconSvg('partly_cloudy', iconHdr)}
            <span>Weather</span>
          </div>
          <div class="vc-wx-header-subtitle">Local Forecast</div>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;
                    justify-content:center;gap:0.5em;padding:1em;text-align:center;">
          <div>${iconSvg('partly_cloudy', iconLg)}</div>
          <div style="font-size:1em;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;
                      color:#90c8ff;">No Location Configured</div>
          <div style="font-size:0.72em;color:#8098c0;max-width:22em;line-height:1.5;">
            Add a Zip Code or Latitude&nbsp;/&nbsp;Longitude in
            Virtual Weather Channel Settings.
          </div>
        </div>
        <div class="vc-wx-ticker-bar">
          <div class="vc-wx-ticker-label">Weather Alert:</div>
          <div class="vc-wx-ticker-scroll">
            <span class="vc-wx-ticker-track">No location configured \u2022 </span>
          </div>
        </div>`;
      _applyWeatherBackground(frame, bgCondition);
      overlay.appendChild(frame);
      root.appendChild(overlay);
      return;
    }

    // Base font-size drives all em values
    const fw  = root.offsetWidth || 960;
    const bp  = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX));
    frame.style.fontSize = bp + 'px';

    // Dispatch to the correct segment renderer (sets frame.innerHTML)
    const segment = (data?.segment != null) ? data.segment : 0;
    if      (segment === 1) { renderForecast(data, frame, bp); }
    else if (segment === 2) { renderRadar(data, frame, bp); }
    else if (segment === 3) { renderAlerts(data, frame, bp); }
    else                    { renderCurrent(data, frame, bp); }

    // Apply animated background after content so insertBefore(firstChild) places
    // it behind all rendered content in DOM order.
    _applyWeatherBackground(frame, bgCondition);

    overlay.appendChild(frame);
    root.appendChild(overlay);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/weather');
  }

  // ── Self-driven cycle timer ────────────────────────────────────────────────
  // Mirrors the on_this_day pattern: after each fetch the client schedules its
  // next OverlayEngine.tick() to fire precisely at the segment boundary using
  // ms_until_next from the API response.  This makes the overlay cycle at the
  // admin-configured rate rather than at the engine's static refreshSeconds.

  const CYCLE_FALLBACK_MS = 60 * 1000;  // fallback if ms_until_next is unavailable
  let _cycleTimer = null;

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  async function fetchDataWithCycling() {
    const data = await fetchData();
    if (_cycleTimer === null) {
      const ms = (data && data.ms_until_next > 0) ? data.ms_until_next : CYCLE_FALLBACK_MS;
      _cycleTimer = setTimeout(advanceAndTick, ms);
    }
    return data;
  }

  function _clearCycleTimer() {
    if (_cycleTimer !== null) {
      clearTimeout(_cycleTimer);
      _cycleTimer = null;
    }
    _cancelBgAnim();
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchDataWithCycling, render });
  window.OverlayEngine.onStop(_clearCycleTimer);
})();
