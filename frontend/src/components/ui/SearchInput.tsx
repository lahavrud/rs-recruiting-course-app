import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useDebounce } from "@/hooks/useDebounce";
import { inputCls } from "@/styles/forms";

interface SearchInputProps {
  /** Initial value, used only for uncontrolled internal state. */
  initialValue?: string;
  /** Fired with the debounced value. */
  onChange: (value: string) => void;
  /** Override the default Hebrew placeholder. */
  placeholder?: string;
  /** Override the debounce delay in ms. Default: 300. */
  delay?: number;
  /** Disable the global `/` keyboard shortcut. */
  disableShortcut?: boolean;
  className?: string;
  ariaLabel?: string;
}

/**
 * Search box with built-in debounce and a global `/` keyboard shortcut to
 * focus. Keeps internal state and only fires `onChange` after the user
 * stops typing.
 */
export default function SearchInput({
  initialValue = "",
  onChange,
  placeholder,
  delay = 300,
  disableShortcut = false,
  className = "",
  ariaLabel,
}: SearchInputProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState(initialValue);
  const debounced = useDebounce(value, delay);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    onChange(debounced);
    // Note: `onChange` deliberately not in deps — caller is expected to
    // memoize their handler if they care about stability.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  useEffect(() => {
    if (disableShortcut) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [disableShortcut]);

  return (
    <input
      ref={inputRef}
      type="search"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder={placeholder ?? t("common.searchPlaceholder")}
      aria-label={ariaLabel ?? t("common.search")}
      className={`${inputCls} ${className}`}
    />
  );
}
