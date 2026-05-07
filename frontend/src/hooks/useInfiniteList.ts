import { useCallback, useEffect, useReducer, useRef } from "react";

/**
 * Server response shape produced by the backend's `CursorPage[T]` envelope
 * (see `src/core/infrastructure/pagination.py`).
 */
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export type CursorFetcher<T> = (cursor: string | null) => Promise<CursorPage<T>>;

export interface UseInfiniteListResult<T> {
  items: T[];
  isLoading: boolean;
  isFetchingMore: boolean;
  hasMore: boolean;
  error: Error | null;
  /** Attach to a sentinel element at the bottom of the list. */
  sentinelRef: (node: HTMLElement | null) => void;
  /** Re-fetch the first page. Useful after mutations or filter changes. */
  reload: () => void;
  /** Append a single item to the head of the list. */
  prependItem: (item: T) => void;
  /** Replace one matching item. */
  updateItem: (predicate: (item: T) => boolean, next: T) => void;
  /** Remove all items matching a predicate. */
  removeItem: (predicate: (item: T) => boolean) => void;
}

interface State<T> {
  items: T[];
  cursor: string | null;
  hasMore: boolean;
  isLoading: boolean;
  isFetchingMore: boolean;
  error: Error | null;
}

type Action<T> =
  | { type: "reset" }
  | { type: "loadStart" }
  | { type: "loadMoreStart" }
  | { type: "loadEnd"; items: T[]; cursor: string | null; replace: boolean }
  | { type: "loadError"; error: Error }
  | { type: "prepend"; item: T }
  | { type: "update"; predicate: (item: T) => boolean; next: T }
  | { type: "remove"; predicate: (item: T) => boolean };

function reducer<T>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case "reset":
      return {
        items: [],
        cursor: null,
        hasMore: true,
        isLoading: true,
        isFetchingMore: false,
        error: null,
      };
    case "loadStart":
      return { ...state, isLoading: true, error: null };
    case "loadMoreStart":
      return { ...state, isFetchingMore: true, error: null };
    case "loadEnd":
      return {
        ...state,
        items: action.replace ? action.items : [...state.items, ...action.items],
        cursor: action.cursor,
        hasMore: action.cursor != null,
        isLoading: false,
        isFetchingMore: false,
        error: null,
      };
    case "loadError":
      return {
        ...state,
        isLoading: false,
        isFetchingMore: false,
        error: action.error,
      };
    case "prepend":
      return { ...state, items: [action.item, ...state.items] };
    case "update":
      return {
        ...state,
        items: state.items.map((item) => (action.predicate(item) ? action.next : item)),
      };
    case "remove":
      return {
        ...state,
        items: state.items.filter((item) => !action.predicate(item)),
      };
    default:
      return state;
  }
}

const INITIAL: State<unknown> = {
  items: [],
  cursor: null,
  hasMore: true,
  isLoading: true,
  isFetchingMore: false,
  error: null,
};

/**
 * Cursor-paginated infinite list driven by an `IntersectionObserver` sentinel.
 *
 * Memoize your fetcher with `useCallback` and depend on filter values — the
 * hook resets and refetches whenever the fetcher identity changes.
 *
 * Returns `sentinelRef` for a bottom-of-list element; the hook attaches
 * an `IntersectionObserver` to it and pulls the next page when it scrolls
 * into view. Mutation helpers (`prependItem`, `updateItem`, `removeItem`)
 * let callers reflect optimistic updates without a full reload.
 */
export function useInfiniteList<T>(
  fetcher: CursorFetcher<T>,
): UseInfiniteListResult<T> {
  const [state, dispatch] = useReducer(
    reducer as React.Reducer<State<T>, Action<T>>,
    INITIAL as State<T>,
  );

  const fetcherRef = useRef(fetcher);
  const inFlight = useRef(false);
  const stateRef = useRef(state);

  // Sync refs from latest props/state in an effect — never during render.
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const fetchPage = useCallback(
    async (nextCursor: string | null, replace: boolean): Promise<void> => {
      if (inFlight.current) return;
      inFlight.current = true;
      dispatch(replace ? { type: "loadStart" } : { type: "loadMoreStart" });
      try {
        const page = await fetcherRef.current(nextCursor);
        dispatch({
          type: "loadEnd",
          items: page.items,
          cursor: page.next_cursor,
          replace,
        });
      } catch (err) {
        dispatch({
          type: "loadError",
          error: err instanceof Error ? err : new Error(String(err)),
        });
      } finally {
        inFlight.current = false;
      }
    },
    [],
  );

  // Reset + load whenever the fetcher identity changes (filters/page mount).
  useEffect(() => {
    dispatch({ type: "reset" });
    void fetchPage(null, true);
  }, [fetcher, fetchPage]);

  // Observer for the bottom-of-list sentinel. Holds the live observer in a
  // ref so the ref-callback can disconnect cleanly without mutating closure
  // state during render.
  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useCallback(
    (node: HTMLElement | null) => {
      observerRef.current?.disconnect();
      observerRef.current = null;
      if (!node) return;
      const observer = new IntersectionObserver(
        (entries) => {
          if (!entries[0]?.isIntersecting || inFlight.current) return;
          const current = stateRef.current;
          if (current.hasMore && current.cursor != null) {
            void fetchPage(current.cursor, false);
          }
        },
        { rootMargin: "200px 0px" },
      );
      observer.observe(node);
      observerRef.current = observer;
    },
    [fetchPage],
  );

  // Cleanup the observer when the host component unmounts.
  useEffect(
    () => () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
    },
    [],
  );

  const reload = useCallback(() => {
    dispatch({ type: "reset" });
    void fetchPage(null, true);
  }, [fetchPage]);

  const prependItem = useCallback((item: T) => {
    dispatch({ type: "prepend", item });
  }, []);

  const updateItem = useCallback((predicate: (item: T) => boolean, next: T) => {
    dispatch({ type: "update", predicate, next });
  }, []);

  const removeItem = useCallback((predicate: (item: T) => boolean) => {
    dispatch({ type: "remove", predicate });
  }, []);

  return {
    items: state.items,
    isLoading: state.isLoading,
    isFetchingMore: state.isFetchingMore,
    hasMore: state.hasMore,
    error: state.error,
    sentinelRef,
    reload,
    prependItem,
    updateItem,
    removeItem,
  };
}
