import { useRef, useEffect } from "react";
import * as d3 from "d3";

export function useD3(
  renderFn: (svg: d3.Selection<SVGSVGElement, unknown, null, undefined>) => void,
  deps: React.DependencyList
) {
  const ref = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (ref.current) {
      const svg = d3.select(ref.current);
      renderFn(svg);
      return () => {
        svg.selectAll("*").remove();
      };
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return ref;
}
