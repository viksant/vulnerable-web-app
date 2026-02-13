import { useState } from "react";
import Button from "./ui/Button";

/**
 * Neo-Brutalist coupon code input with inline apply button.
 *
 * @param {object} props
 * @param {function} props.onApply - Called with the coupon code string.
 */
export default function CouponInput({ onApply }) {
  const [code, setCode] = useState("");
  const [isApplying, setIsApplying] = useState(false);

  async function handleApply(e) {
    e.preventDefault();
    if (!code.trim()) return;
    setIsApplying(true);
    try {
      await onApply(code);
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <form onSubmit={handleApply} className="flex gap-0">
      <input
        type="text"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        placeholder="COUPON CODE"
        className="h-14 flex-1 border-4 border-r-0 border-black bg-white px-4 font-bold text-lg uppercase placeholder:text-black/40 focus:bg-neo-secondary focus:outline-none"
      />
      <Button
        type="submit"
        variant="secondary"
        className="h-14 border-4 border-black"
        disabled={isApplying}
      >
        {isApplying ? "..." : "APPLY"}
      </Button>
    </form>
  );
}
