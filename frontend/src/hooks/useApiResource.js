import { useEffect, useState } from "react";

export function useApiResource(resource) {
  const [state, setState] = useState({ data: null, error: "", loading: true });

  useEffect(() => {
    let active = true;
    setState((current) => ({ ...current, error: "", loading: true }));

    resource()
      .then((data) => {
        if (active) {
          setState({ data, error: "", loading: false });
        }
      })
      .catch((error) => {
        if (active) {
          setState({ data: null, error: error.message, loading: false });
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
