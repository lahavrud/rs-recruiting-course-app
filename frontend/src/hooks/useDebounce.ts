import { useEffect, useState } from "react";

/**
 * Returns a debounced copy of `value` that updates only after `delay` ms
 * have passed without further changes. Useful for search inputs.
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debounced;
}
