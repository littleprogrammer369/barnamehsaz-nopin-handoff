/** Inline SVG logo — no binary asset (04: «لوگوی SVG» + «آیکون‌های SVG» inline). */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg
      className="logo"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      style={{ flex: "none" }}
    >
      <rect x="4" y="4" width="40" height="40" rx="10" fill="#0f9e8e" />
      <path
        d="M14 30 L24 16 L34 30 Z"
        fill="#ffffff"
        opacity="0.95"
      />
      <circle cx="24" cy="27" r="3.2" fill="#14244b" />
      <rect x="12" y="32" width="24" height="3" rx="1.5" fill="#14244b" opacity="0.65" />
    </svg>
  );
}

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  // Compact inline icons used across the shell.
  const paths: Record<string, JSX.Element> = {
    home: <path d="M3 11 12 3l9 8M5 10v10h14V10" />,
    cycles: <path d="M12 4v16m0 0 6-6m-6 6-6-6" />,
    resources: <rect x="4" y="6" width="16" height="14" rx="2" />,
    offerings: <path d="M4 7h16v10H4zM4 11h16" />,
    wizard: <path d="M12 4 4 12h6v8h8v-8h6L12 4Z" />,
    preflight: <path d="M12 3 4 8v4l8 1 8-1V8l-8-5ZM6 15l6 3 6-3" />,
    solve: <path d="M4 12h7m4 0h5M15 9l3 3-3 3" />,
    runs: <path d="M4 6h16v4H4zM4 14h16v4H4z" />,
    audit: <path d="M5 5h10v14H5zM13 9h6v6h-6" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flex: "none" }}
    >
      {paths[name] ?? paths.home}
    </svg>
  );
}
