import { useEffect, useState } from "react";

export function useApiResource(resource) {
  const [state, setState] = useState({ data: null, error: "", errorStatus: null, loading: true });

  useEffect(() => {
    let active = true;
    setState((current) => ({ ...current, error: "", errorStatus: null, loading: true }));

    resource()
      .then((data) => {
        if (active) {
          setState({ data, error: "", errorStatus: null, loading: false });
        }
      })
      .catch((error) => {
        if (active) {
          // `errorStatus` lets a caller distinguish an unauthenticated session
          // (401) from a server or network failure without parsing the message.
          setState({ data: null, error: error.message, errorStatus: error.status ?? null, loading: false });
        }
      });

    return () => {
      active = false;
    };
  }, [resource]);

  return {
    ...state,
    reload: resource,
  };
}
