/**
 * Neo-Brutalist Card component.
 * Always border-4 border-black, sharp corners, solid shadow.
 * Optional colored header stripe.
 * Hover lift effect when hoverable prop is true.
 */
export default function Card({
  children,
  header,
  headerColor = "bg-neo-muted",
  shadow = "shadow-neo-md",
  hoverable = false,
  className = "",
  onClick,
  ...props
}) {
  const isClickable = hoverable || !!onClick;

  return (
    <div
      role={isClickable ? "button" : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={isClickable ? (e) => e.key === "Enter" && onClick?.(e) : undefined}
      className={[
        "border-4 border-black bg-white",
        shadow,
        isClickable
          ? "cursor-pointer hover:-translate-y-1 hover:shadow-neo-lg transition-all duration-200 ease-out"
          : "",
        className,
      ].join(" ")}
      {...props}
    >
      {header && (
        <div
          className={`border-b-4 border-black px-4 py-3 font-black text-sm uppercase tracking-widest ${headerColor}`}
        >
          {header}
        </div>
      )}
      {children}
    </div>
  );
}
