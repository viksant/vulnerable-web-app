import { forwardRef } from "react";

/**
 * Neo-Brutalist Input component.
 * Focus indicator: background turns yellow (bg-neo-secondary).
 * No border-radius, always sharp corners.
 */
const Input = forwardRef(function Input(
  { label, className = "", ...props },
  ref,
) {
  return (
    <div className="w-full">
      {label && (
        <label className="mb-1 block text-sm font-bold uppercase tracking-widest">
          {label}
        </label>
      )}
      {props.type === "textarea" ? (
        <textarea
          ref={ref}
          className={[
            "w-full border-4 border-black bg-white font-bold text-lg",
            "placeholder:text-black/40",
            "focus:bg-neo-secondary focus:shadow-neo-sm focus:outline-none",
            "focus:ring-2 focus:ring-black focus:ring-offset-2",
            "min-h-[56px] p-3",
            className,
          ].join(" ")}
          {...props}
          type={undefined}
        />
      ) : (
        <input
          ref={ref}
          className={[
            "h-14 w-full border-4 border-black bg-white px-4 font-bold text-lg",
            "placeholder:text-black/40",
            "focus:bg-neo-secondary focus:shadow-neo-sm focus:outline-none",
            "focus:ring-2 focus:ring-black focus:ring-offset-2",
            className,
          ].join(" ")}
          {...props}
        />
      )}
    </div>
  );
});

export default Input;
