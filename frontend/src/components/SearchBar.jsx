import { useState } from "react";
import { Search } from "lucide-react";
import Button from "./ui/Button";

/**
 * Neo-Brutalist search bar with large input and adjacent button.
 *
 * @param {object} props
 * @param {function} props.onSearch - Called with the query string.
 * @param {string} props.initialQuery - Pre-fill value.
 */
export default function SearchBar({ onSearch, initialQuery = "" }) {
  const [query, setQuery] = useState(initialQuery);

  function handleSubmit(e) {
    e.preventDefault();
    onSearch(query);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-0">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="SEARCH PRODUCTS..."
        className="h-16 flex-1 border-4 border-r-0 border-black bg-white px-6 font-bold text-xl placeholder:text-black/40 focus:bg-neo-secondary focus:outline-none"
      />
      <Button
        type="submit"
        variant="dark"
        className="h-16 border-4 border-black px-6"
        aria-label="Search"
      >
        <Search className="h-6 w-6" strokeWidth={3} />
      </Button>
    </form>
  );
}
