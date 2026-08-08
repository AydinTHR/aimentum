/** Hand-drawn 24px stroke icons, sized by the parent via className. */

interface IconProps {
  className?: string;
}

function base(className: string | undefined) {
  return {
    className: className ?? "size-5",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
}

export function SunIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M22 12h-2.5M4.5 12H2M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8M18.4 18.4l-1.8-1.8M7.4 7.4 5.6 5.6" />
    </svg>
  );
}

export function TargetIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function BookIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M12 5.5C10.5 4 8.3 3.5 5.5 3.5c-.8 0-1.5.1-2 .2V19c.5-.1 1.2-.2 2-.2 2.8 0 5 .5 6.5 2 1.5-1.5 3.7-2 6.5-2 .8 0 1.5.1 2 .2V3.7c-.5-.1-1.2-.2-2-.2-2.8 0-5 .5-6.5 2Z" />
      <path d="M12 5.5v15.3" />
    </svg>
  );
}

export function GearIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M19.4 13.5a7.6 7.6 0 0 0 0-3l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-2.6-1.5L14 2.5h-4L9.6 5a7.6 7.6 0 0 0-2.6 1.5l-2.4-1-2 3.4 2 1.6a7.6 7.6 0 0 0 0 3l-2 1.6 2 3.4 2.4-1a7.6 7.6 0 0 0 2.6 1.5l.4 2.5h4l.4-2.5a7.6 7.6 0 0 0 2.6-1.5l2.4 1 2-3.4Z" />
    </svg>
  );
}

export function MicIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3.5" />
    </svg>
  );
}

export function StopIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="m5 12.5 4.5 4.5L19 7" />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function BellIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M6 9.5a6 6 0 0 1 12 0c0 4 1.5 5.5 2 6.5H4c.5-1 2-2.5 2-6.5Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </svg>
  );
}

export function ShareIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M12 3v11M8.5 6 12 3l3.5 3" />
      <path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1" />
    </svg>
  );
}
