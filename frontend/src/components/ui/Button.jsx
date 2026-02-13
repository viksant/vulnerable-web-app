/**
 * Neo-Brutalist Button component.
 * Variants: primary (red), secondary (yellow), outline (white), dark (black).
 * Mechanical push-down effect on active state.
 */

const VARIANT_CLASSES = {
  primary: "bg-neo-accent hover:bg-red-400",
  secondary: "bg-neo-secondary hover:bg-yellow-300",
  outline: "bg-white hover:bg-neutral-100",
  dark: "bg-black text-white hover:bg-neutral-900 shadow-neo-white",
};

/**
 * @param {object} props
 * @param {"primary"|"secondary"|"outline"|"dark"} props.variant
 * @param {"sm"|"md"|"lg"} props.size
 * @param {boolean} props.fullWidth
 * @param {React.ReactNode} props.children
 */
export default function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  children,
  className = "",
  ...props
}) {
  const sizeClasses = {
    sm: "h-10 px-4 text-xs shadow-neo-sm",
    md: "h-12 px-6 text-sm shadow-neo-sm",
    lg: "h-14 px-8 text-lg shadow-neo-md",
  };

  return (
    <button
      className={[
        "border-4 border-black font-bold uppercase tracking-wide",
        "active:translate-x-[2px] active:translate-y-[2px] active:shadow-none",
        "transition-all duration-100 ease-out",
        "focus:ring-2 focus:ring-black focus:ring-offset-2",
        fullWidth ? "w-full" : "w-full sm:w-auto",
        VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary,
        sizeClasses[size] || sizeClasses.md,
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </button>
  );
}
