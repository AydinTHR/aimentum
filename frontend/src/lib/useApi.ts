import { useCallback, useEffect, useRef, useState } from "react";

interface ApiState<T> {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
}

/** Fetch-on-mount with manual reload. Previous data stays visible during a
 * reload so refreshing a screen never blanks it. */
export function useApi<T>(fetcher: () => Promise<T>): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({
    data: undefined,
    error: undefined,
    loading: true,
  });
  const [nonce, setNonce] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let alive = true;
    setState((previous) => ({ ...previous, loading: true }));
    fetcherRef.current().then(
      (data) => {
        if (alive) setState({ data, error: undefined, loading: false });
      },
      (error: unknown) => {
        if (alive) {
          setState((previous) => ({
            data: previous.data,
            error: error instanceof Error ? error.message : "Something went wrong.",
            loading: false,
          }));
        }
      },
    );
    return () => {
      alive = false;
    };
  }, [nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}
