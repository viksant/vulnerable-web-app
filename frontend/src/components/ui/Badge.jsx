/**
 * Neo-Brutalist Badge component.
 * Variants: accent (red), secondary (yellow), muted (violet), dark (black).
 * Optional rounded-full for pill shape, rotation for decorative tilt.
 */

const VARIANT_CLASSES = {
  accent: "bg-neo-accent text-black",
  secondary: "bg-neo-secondary text-black",
  muted: "bg-neo-muted text-black",
  dark: "bg-black text-white",
};

/**
 * @param {object} props
 * @param {"accent"|"secondary"|"muted"|"dark"} props.variant
 * @param {boolean} props.pill - Use rounded-full instead of sharp corners
 * @param {string} props.rotation - Tailwind rotation class (e.g. "rotate-1", "-rotate-2")
 */
export default function Badge({
  variant = "accent",
  pill = false,
  rotation = "",
  children,
  className = "",
  ...props
}) {
  return (
    <span
      className={[
        "inline-block border-4 border-black px-3 py-1 font-black text-sm uppercase tracking-widest shadow-neo-sm",
        pill ? "rounded-full" : "",
        rotation,
        VARIANT_CLASSES[variant] || VARIANT_CLASSES.accent,
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </span>
  );
}
