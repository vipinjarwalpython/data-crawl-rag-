import React from 'react';

/**
 * 3D Holographic and Specular Icons
 * High-definition vector icons with metallic bevels, radial lighting,
 * and multi-layer ambient glows for a luxury AI aesthetic.
 */

export function Icon3DBot({ size = 36, glow = true }) {
  return (
    <div
      className={`icon-3d-wrapper ${glow ? 'glow-indigo' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ filter: 'drop-shadow(0 4px 12px rgba(99, 102, 241, 0.45))' }}
      >
        <defs>
          <linearGradient id="botSphere" x1="6" y1="6" x2="42" y2="42" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#818cf8" />
            <stop offset="45%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#312e81" />
          </linearGradient>
          <linearGradient id="botHighlight" x1="12" y1="8" x2="36" y2="24" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
          <radialGradient id="eyeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#67e8f9" />
            <stop offset="60%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#0891b2" />
          </radialGradient>
        </defs>

        {/* Outer Ring */}
        <circle cx="24" cy="24" r="22" stroke="url(#botHighlight)" strokeWidth="1.5" strokeOpacity="0.4" />
        
        {/* Main 3D Sphere */}
        <circle cx="24" cy="24" r="18" fill="url(#botSphere)" />
        <ellipse cx="24" cy="14" rx="12" ry="6" fill="url(#botHighlight)" />

        {/* Eyes Visor */}
        <rect x="14" y="20" width="20" height="8" rx="4" fill="#090d16" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
        
        {/* Glowing Eyes */}
        <circle cx="19" cy="24" r="2.5" fill="url(#eyeGlow)" style={{ filter: 'drop-shadow(0 0 6px #22d3ee)' }} />
        <circle cx="29" cy="24" r="2.5" fill="url(#eyeGlow)" style={{ filter: 'drop-shadow(0 0 6px #22d3ee)' }} />

        {/* Antenna Orb */}
        <path d="M24 6V2" stroke="url(#botHighlight)" strokeWidth="2" strokeLinecap="round" />
        <circle cx="24" cy="2" r="2" fill="#38bdf8" style={{ filter: 'drop-shadow(0 0 5px #38bdf8)' }} />
      </svg>
    </div>
  );
}

export function Icon3DCrawler({ size = 36, glow = true }) {
  return (
    <div
      className={`icon-3d-wrapper ${glow ? 'glow-violet' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ filter: 'drop-shadow(0 4px 12px rgba(168, 85, 247, 0.45))' }}
      >
        <defs>
          <linearGradient id="orbGrad" x1="8" y1="8" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#c084fc" />
            <stop offset="50%" stopColor="#9333ea" />
            <stop offset="100%" stopColor="#581c87" />
          </linearGradient>
          <linearGradient id="specular" x1="14" y1="10" x2="34" y2="26" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.75" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* 3D Core */}
        <circle cx="24" cy="24" r="16" fill="url(#orbGrad)" />
        <ellipse cx="24" cy="15" rx="10" ry="5" fill="url(#specular)" />

        {/* Orbital Network Rings */}
        <ellipse cx="24" cy="24" rx="21" ry="8" stroke="#e879f9" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.8" transform="rotate(-25 24 24)" />
        <ellipse cx="24" cy="24" rx="21" ry="8" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="4 2" opacity="0.7" transform="rotate(35 24 24)" />

        {/* Floating Satellites */}
        <circle cx="9" cy="18" r="2.5" fill="#f472b6" style={{ filter: 'drop-shadow(0 0 6px #f472b6)' }} />
        <circle cx="39" cy="30" r="2.5" fill="#38bdf8" style={{ filter: 'drop-shadow(0 0 6px #38bdf8)' }} />
        <circle cx="24" cy="24" r="4" fill="#ffffff" style={{ filter: 'drop-shadow(0 0 8px #ffffff)' }} />
      </svg>
    </div>
  );
}

export function Icon3DDatabase({ size = 32, glow = true }) {
  return (
    <div
      className={`icon-3d-wrapper ${glow ? 'glow-emerald' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ filter: 'drop-shadow(0 4px 12px rgba(16, 185, 129, 0.4))' }}
      >
        <defs>
          <linearGradient id="dbDisk" x1="10" y1="12" x2="38" y2="36" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#34d399" />
            <stop offset="60%" stopColor="#059669" />
            <stop offset="100%" stopColor="#064e3b" />
          </linearGradient>
          <linearGradient id="dbRim" x1="12" y1="10" x2="36" y2="18" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0.1" />
          </linearGradient>
        </defs>

        {/* Tier 3 (Bottom) */}
        <path d="M10 28C10 32.4 16.3 36 24 36C31.7 36 38 32.4 38 28V33C38 37.4 31.7 41 24 41C16.3 41 10 37.4 10 33V28Z" fill="url(#dbDisk)" opacity="0.9" />
        <ellipse cx="24" cy="28" rx="14" ry="4" stroke="url(#dbRim)" strokeWidth="1" />

        {/* Tier 2 (Middle) */}
        <path d="M10 18C10 22.4 16.3 26 24 26C31.7 26 38 22.4 38 18V23C38 27.4 31.7 31 24 31C16.3 31 10 27.4 10 23V18Z" fill="url(#dbDisk)" />
        <ellipse cx="24" cy="18" rx="14" ry="4" stroke="url(#dbRim)" strokeWidth="1" />

        {/* Tier 1 (Top Disc) */}
        <ellipse cx="24" cy="11" rx="14" ry="5" fill="url(#dbDisk)" stroke="url(#dbRim)" strokeWidth="1.5" />
        <ellipse cx="24" cy="10" rx="9" ry="2.5" fill="#a7f3d0" opacity="0.6" style={{ filter: 'blur(1px)' }} />

        {/* Activity Indicator Lights */}
        <circle cx="15" cy="21" r="1.5" fill="#6ee7b7" style={{ filter: 'drop-shadow(0 0 4px #6ee7b7)' }} />
        <circle cx="15" cy="31" r="1.5" fill="#6ee7b7" style={{ filter: 'drop-shadow(0 0 4px #6ee7b7)' }} />
      </svg>
    </div>
  );
}

export function Icon3DSparkles({ size = 28 }) {
  return (
    <div style={{ width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ filter: 'drop-shadow(0 0 8px rgba(250, 204, 21, 0.6))' }}
      >
        <defs>
          <linearGradient id="starGrad" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#fef08a" />
            <stop offset="50%" stopColor="#eab308" />
            <stop offset="100%" stopColor="#ca8a04" />
          </linearGradient>
        </defs>
        {/* Main 4-point Star */}
        <path
          d="M16 2C16 9.7 9.7 16 2 16C9.7 16 16 22.3 16 30C16 22.3 22.3 16 30 16C22.3 16 16 9.7 16 2Z"
          fill="url(#starGrad)"
        />
        {/* Specular Core */}
        <circle cx="16" cy="16" r="3" fill="#ffffff" style={{ filter: 'drop-shadow(0 0 6px #ffffff)' }} />
      </svg>
    </div>
  );
}

export function Icon3DShield({ size = 28 }) {
  return (
    <div style={{ width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ filter: 'drop-shadow(0 2px 10px rgba(56, 189, 248, 0.5))' }}
      >
        <defs>
          <linearGradient id="shieldGrad" x1="6" y1="4" x2="26" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="60%" stopColor="#0284c7" />
            <stop offset="100%" stopColor="#0369a1" />
          </linearGradient>
        </defs>
        <path
          d="M16 3L6 7.5V15C6 21.5 10.3 27.5 16 29C21.7 27.5 26 21.5 26 15V7.5L16 3Z"
          fill="url(#shieldGrad)"
          stroke="rgba(255,255,255,0.4)"
          strokeWidth="1"
        />
        <path
          d="M16 5V27C20.5 25.6 24 20.6 24 15V8.5L16 5Z"
          fill="#ffffff"
          opacity="0.18"
        />
        <path
          d="M12 15L15 18L21 11"
          stroke="#ffffff"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}
