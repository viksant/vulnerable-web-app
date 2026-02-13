/**
 * Neo-Brutalist Container wrapper.
 * Centers content with responsive horizontal padding.
 */
export default function Container({ children, className = "" }) {
  return (
    <div className={`mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 ${className}`}>
      {children}
    </div>
  );
}
