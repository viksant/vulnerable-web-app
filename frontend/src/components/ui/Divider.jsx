/**
 * Neo-Brutalist Divider component.
 * Default: thick black line. Marquee variant: scrolling repeated text.
 */
export default function Divider({ marquee, text = "", className = "" }) {
  if (marquee) {
    return (
      <div
        className={`overflow-hidden border-t-4 border-b-4 border-black bg-neo-secondary py-2 ${className}`}
      >
        <div className="animate-marquee flex whitespace-nowrap">
          {/* Duplicate text for seamless loop */}
          {Array.from({ length: 20 }, (_, i) => (
            <span
              key={i}
              className="mx-4 font-black text-sm uppercase tracking-widest"
            >
              {text} ★
            </span>
          ))}
        </div>
      </div>
    );
  }

  return <hr className={`border-t-4 border-black ${className}`} />;
}
